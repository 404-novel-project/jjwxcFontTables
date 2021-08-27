#!/usr/bin/env python
import json
import logging
import os
import sys
import tempfile
from functools import lru_cache

import imagehash
import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import woff2, ttFont
from jinja2 import Template

PWD: str = os.path.abspath(os.path.dirname(__file__))
FontsDir = os.path.join(PWD, 'fonts')
TablesDir = os.path.join(PWD, 'tables')
DistDir = os.path.join(PWD, 'dist')

# Setting
SIZE: int = 228
W, H = (SIZE, SIZE)

# FZFont
FZFontTTFPath: str = os.path.join(PWD, "assets", "FZLanTingHei-M-GBK.ttf")
FZFontTTF: ImageFont.FreeTypeFont = ImageFont.truetype(FZFontTTFPath, SIZE, encoding="utf-8")

# FZHashs
FZHashPath: str = os.path.join(PWD, "assets", "FZLanTingHei-M-GBK-Hash-Table.json")

# ImageHash
HashSize: int = 16
HashFunc = imagehash.average_hash
HashMeanFunc = np.mean


def mkdir() -> None:
    """
    创建所需文件夹。
    """
    for path in [FontsDir, TablesDir, DistDir]:
        if not os.path.exists(path):
            os.mkdir(path)


mkdir()


def drawFZ(character: str) -> ImageDraw:
    """
    输入字符，输出方正兰亭黑字体绘制结果。
    """
    return draw(character, FZFontTTF)


@lru_cache(maxsize=1024)
def draw(character: str, fontTTF: ImageFont.FreeTypeFont) -> ImageDraw:
    """
    输入字符以及字体文件，输出绘制结果。
    """
    image = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(image)
    offset_w, offset_h = fontTTF.getoffset(character)
    w, h = d.textsize(character, font=fontTTF)
    pos = ((W - w - offset_w) / 2, (H - h - offset_h) / 2)
    d.text(pos, character, "black", font=fontTTF)
    return image


def compare(image1: ImageDraw, image2: ImageDraw) -> float:
    """
    输入两字体图像，输出差异度。
    """
    array1 = np.asarray(image1) / 255
    array2 = np.asarray(image2) / 255
    diff = (array1 - array2).var()
    return diff


def listTTF(ttf: ttFont.TTFont) -> list[str]:
    """
    输入字体文件，输出该字体文件下所有字符。
    """
    chars = []
    for x in ttf["cmap"].tables:
        for y in x.cmap.items():
            char_unicode = chr(y[0])
            chars.append(char_unicode)
    return chars


@lru_cache()
def getFZImageHashs() -> dict[str, imagehash.ImageHash]:
    """
    获取方正兰亭黑字体ImageHash字典。
    """

    def genFZimageHashs():
        """
        生成方正兰亭黑字体ImageHash字典。
        """
        ttf = ttFont.TTFont(FZFontTTFPath)
        chars = listTTF(ttf)

        keys = list(filter(lambda x: 19967 < ord(x) < 40870, chars))
        hashs = list(map(lambda x: HashFunc(drawFZ(x), hash_size=HashSize, mean=HashMeanFunc), keys))
        return dict(zip(keys, hashs))

    def loadFZimageHashs():
        """
        从JSON文件载入方正兰亭黑字体ImageHash字典。
        """
        with open(FZHashPath, 'r') as f:
            _hashsdict_save: dict[str, str] = json.load(f)
        _keys = _hashsdict_save.keys()
        _hashs_str = _hashsdict_save.values()
        _hashs = list(map(lambda x: imagehash.hex_to_hash(x), _hashs_str))

        hashsdict = dict(zip(_keys, _hashs))
        return hashsdict

    def saveFZimageHashs():
        """
        将方正兰亭黑字体ImageHash字典保存为JSON文件。
        """
        hashsdict = genFZimageHashs()
        _keys = hashsdict.keys()
        _hashs = hashsdict.values()

        # save to json
        _hashs_str = list(map(lambda x: str(x), _hashs))
        _hashsdict_save = dict(zip(_keys, _hashs_str))
        with open(FZHashPath, 'w') as f:
            json.dump(_hashsdict_save, f)
        return hashsdict

    if os.path.exists(FZHashPath):
        try:
            return loadFZimageHashs()
        except json.decoder.JSONDecodeError:
            return saveFZimageHashs()
    else:
        return saveFZimageHashs()


def getFontFile(fontname: str) -> bytes:
    """
    请求字体文件
    """
    logging.info("请求字体文件：{}".format(fontname))
    url = "http://static.jjwxc.net/tmp/fonts/{}.woff2?h=my.jjwxc.net".format(fontname)
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:91.0) Gecko/20100101 Firefox/91.0",
        "Accept": "application/font-woff2;q=1.0,application/font-woff;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.5",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
        "Referer": "http://my.jjwxc.net/",
        "Origin": "http://my.jjwxc.net"
    }
    resp = requests.get(url, headers=headers)
    if resp.status_code == 404:
        logging.error("未发现字体文件：{}".format(fontname))
        raise FileNotFoundError
    return resp.content


def saveFontFile(fontname: str) -> bytes:
    """
    请求并保存字体文件
    """
    font = getFontFile(fontname)
    fontPath = os.path.join(FontsDir, "{}.woff2".format(fontname))
    with open(fontPath, 'wb') as f:
        logging.info("正在保存字体：{}".format(fontname))
        f.write(font)
    return font


def getJJimageHashs(fontname: str) -> tuple[dict[str, imagehash.ImageHash], ImageFont.FreeTypeFont]:
    """
    获取指定名称晋江字体的ImageHash字典。
    """
    fontPath = os.path.join(FontsDir, "{}.woff2".format(fontname))
    if not os.path.exists(fontPath):
        try:
            saveFontFile(fontname)
        except FileNotFoundError as e:
            raise e

    with tempfile.TemporaryFile() as tmp:
        woff2.decompress(fontPath, tmp)
        tmp.seek(0)
        fontTTF = ImageFont.truetype(tmp, SIZE - 5, encoding="utf-8")
        ttf = ttFont.TTFont(tmp)

    keys = listTTF(ttf)
    hashs = list(map(lambda x: HashFunc(draw(x, fontTTF), hash_size=HashSize, mean=HashMeanFunc), keys))
    return dict(zip(keys, hashs)), fontTTF


def matchJJFont(fontname: str) -> dict[str, str]:
    """
    输入晋江字体名称，返回该字体匹配结果。
    """

    def match(key: str, ihash: imagehash.ImageHash) -> str:
        """
        输入晋江字符以及晋江字符所对应ImageHash，返回最匹配的普通字符。
        """
        diffs = list(map(lambda fzhash: fzhash - ihash, FZhashs))
        diffs_dict = dict(zip(FZkeys, diffs))

        mkey = None
        mdiff = None
        mdiff2 = None
        for k in diffs_dict:
            diff = diffs_dict[k]
            if mkey is None:
                mkey = k
                mdiff = diff
                mdiff2 = compare(draw(key, JJFontTTF), drawFZ(k))
            else:
                if diff <= mdiff:
                    diff2 = compare(draw(key, JJFontTTF), drawFZ(k))
                    if diff2 < mdiff2:
                        mkey = k
                        mdiff = diff
                        mdiff2 = diff2
        return mkey

    def patch(jjFontTableDict: dict[str, str]) -> dict[str, str]:
        """
        对自动识别的晋江字符对照表进行一些修正。
        """

        def replace(x):
            r = {
                "杲": "果",
                "曼": "最"
            }
            rk = r.keys()
            if x in rk:
                return r[x]
            else:
                return x

        k = jjFontTableDict.keys()
        v = jjFontTableDict.values()
        v_patch = list(map(replace, v))
        return dict(zip(k, v_patch))

    FZhashsdict = getFZImageHashs()
    FZkeys = FZhashsdict.keys()
    FZhashs = FZhashsdict.values()

    JJhashsdict, JJFontTTF = getJJimageHashs(fontname)
    JJkeys = list(JJhashsdict.keys())
    JJhashs = list(JJhashsdict.values())

    results = {}
    for i in range(len(JJkeys)):
        jjkey = JJkeys[i]
        if jjkey == 'x':
            continue
        jjhash = JJhashs[i]
        mchar = match(jjkey, jjhash)
        logging.info("{}\t{}\t{}".format(fontname, ord(jjkey), mchar))
        results[jjkey] = mchar

    results = patch(results)
    return results


def saveJJFont(fontname: str, tablesDict: dict[str, str], tablesFolderPath: str = TablesDir) -> None:
    """
    将晋江字体对照表保存为JSON文件、HTML文件。
    """

    def saveJSON() -> None:
        """
        将晋江字体对照表保存为JSON文件。
        """
        fontJsonPath = os.path.join(tablesFolderPath, fontname + '.json')
        with open(fontJsonPath, 'w') as f:
            json.dump(tablesDict, f, sort_keys=True, indent=4)

    def saveHTML() -> None:
        """
        将晋江字体对照表保存为HTML文件。
        """
        # noinspection PyPep8
        htmlTemplate = Template('''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <meta http-equiv="Content-Type" content="text/html;charset=UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="referrer" content="no-referrer" />
    <title>{{ fontname }}</title>
    <style>
    body {
        background-color: #f0f0f2;
        margin: 0;
        padding: 0;
        font-family: -apple-system, system-ui, BlinkMacSystemFont, "Segoe UI",
        "Open Sans", "Helvetica Neue", Helvetica, Arial, sans-serif;
    }
    div.main {
        width: 600px;
        margin: 5em auto;
        padding: 2em;
        background-color: #fdfdff;
        border-radius: 0.5em;
        box-shadow: 2px 3px 7px 2px rgba(0, 0, 0, 0.02);
    }
    .jjfont {
        font-family: {{ fontname }}, 'Microsoft YaHei', PingFangSC-Regular, HelveticaNeue-Light, 'Helvetica Neue Light', sans-serif !important;;
    }
    @font-face {
        font-family: {{ fontname }};
        src: url('http://static.jjwxc.net/tmp/fonts/{{ fontname }}.woff2?h=my.jjwxc.net') format('woff2');
    }
    </style>
</head>
<body>
    <div class="main">
        <h1>{{ fontname }}</h1>
        <div>
            <table>
            <thead>
                <tr>
                <th>晋江字符（编码）</th>
                <th>晋江字符（渲染）</th>
                <th>通用字符</th>
                </tr>
            </thead>
            <tbody>
                {% for jjdict in jjdicts %}
                <tr>
                <td>{{ jjdict.ord|e }}</td>
                <td class="jjfont">{{ jjdict.jjcode|e }}</td>
                <td>{{ jjdict.unicode|e }}</td>
                </tr>
                {% endfor %}
            </tbody>
            </table>
        </div>
    </div>
</body>
</html>''')

        jjdicts = []
        for k in tablesDict:
            jjdict = {'ord': str(hex(ord(k))).replace('0x', 'U+'), 'jjcode': k, 'unicode': tablesDict[k]}
            jjdicts.append(jjdict)

        htmlText = htmlTemplate.render(fontname=fontname, jjdicts=jjdicts)

        htmlPath = os.path.join(tablesFolderPath, fontname + '.html')
        with open(htmlPath, 'w') as f:
            f.write(htmlText)

    saveJSON()
    saveHTML()


def JJFont(fontname: str) -> None:
    """
    自动识别指定名称的字体文件。
    """
    logging.info("{}\t{}".format(fontname, 'start!'))
    results = matchJJFont(fontname)
    saveJJFont(fontname, results)
    logging.info("{}\t{}".format(fontname, 'finished!'))


def matchAll() -> None:
    """
    自动识别 fonts 目录下所有 woff2 文件。
    """
    flist = os.listdir(FontsDir)
    fontnames = list(map(lambda x: x.split('.')[0], flist))

    import multiprocessing
    pool = multiprocessing.Pool()
    for fontname in fontnames:
        pool.apply_async(JJFont, (fontname,))
    pool.close()
    pool.join()


def matchNew() -> None:
    """
    自动识别 fonts 目录下未被识别的字体文件。
    """
    fontList = set(
        map(lambda x: x.split('.')[0],
            filter(lambda x: x.endswith('.woff2'), os.listdir(FontsDir))
            )
    )
    fontJsonList = set(
        map(lambda x: x.split('.')[0],
            filter(lambda x: x.endswith('.json'), os.listdir(TablesDir))
            )
    )
    newFonts = fontList.difference(fontJsonList)

    import multiprocessing
    pool = multiprocessing.Pool()
    for fontname in newFonts:
        pool.apply_async(JJFont, (fontname,))
    pool.close()
    pool.join()


def bundle() -> None:
    """
    将 tables 目录下所有JSON文件打包为单一JSON文件以及Typescript模块文件。
    """

    def saveTS() -> None:
        """
        将 tables 目录下所有JSON文件打包为Typescript模块文件。
        """
        ts = 'export const jjwxcFontTables: jjwxcFontTables = ' + json.dumps(bundleDict)
        with open(os.path.join(DistDir, 'bundle.ts'), 'w') as fp:
            fp.write(ts)

    jsonFiles = list(filter(lambda x: x.endswith('.json'), os.listdir(TablesDir)))

    bundleDict = {}
    for fname in jsonFiles:
        fontname = fname.split('.')[0]
        with open(os.path.join(TablesDir, fname), 'r') as f:
            table = json.load(f)
        bundleDict[fontname] = table

    with open(os.path.join(DistDir, 'bundle.json'), 'w') as f:
        json.dump(bundleDict, f)

    saveTS()


if __name__ == "__main__":
    import argparse

    logging.basicConfig(stream=sys.stdout, level=logging.INFO)

    parser = argparse.ArgumentParser(description="晋江反爬字体破解辅助工具。")
    parser.add_argument('--all', action='store_true', help="匹配所有fonts目录下的woff2字体文件。")
    parser.add_argument('--new', action='store_true', help="匹配fonts目录下新woff2字体。")
    parser.add_argument('--bundle', action='store_true', help="打包tables目录下所有json文件。")
    parser.add_argument('--font', help="匹配指字名称字体文件。 例始：--font jjwxcfont_00gxm")
    args = parser.parse_args()

    if args.all:
        matchAll()
    elif args.new:
        matchNew()
    elif args.bundle:
        bundle()
    elif args.font:
        JJFont(args.font)

