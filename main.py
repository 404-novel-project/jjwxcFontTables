#!/usr/bin/env python
import json
import logging
import os
import shutil
import sys
import tempfile
from functools import lru_cache

import imagehash
import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import woff2, ttFont
from jinja2 import Environment, FileSystemLoader, select_autoescape

PWD: str = os.path.abspath(os.path.dirname(__file__))
FontsDir: str = os.path.join(PWD, 'fonts')
TablesDir: str = os.path.join(PWD, 'tables')
DistDir: str = os.path.join(PWD, 'dist')
AssetsDir: str = os.path.join(PWD, "assets")

# Setting
SIZE: int = 228
W, H = (SIZE, SIZE)

# FZFont
FZFontTTFPath: str = os.path.join(AssetsDir, "FZLanTingHei-M-GBK.ttf")
FZFontTTF: ImageFont.FreeTypeFont = ImageFont.truetype(FZFontTTFPath, SIZE, encoding="utf-8")

# FZHashs
FZHashPath: str = os.path.join(AssetsDir, "FZLanTingHei-M-GBK-Hash-Table.json")

# ImageHash
HashSize: int = 16
HashFunc = imagehash.average_hash
HashMeanFunc = np.mean

# Jinja2
Env: Environment = Environment(loader=FileSystemLoader(os.path.join(PWD, 'templates')), autoescape=select_autoescape())

# coorTable
coorTableJsonPath = os.path.join(AssetsDir, "coorTable.json")
with open(coorTableJsonPath, 'r') as frp:
    CoorTable = json.load(frp)
del frp


def mkdir() -> None:
    """
    创建所需文件夹。
    """
    for path in [FontsDir, TablesDir, DistDir, AssetsDir]:
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
    array1 = np.asarray(image1.convert('1'))
    array2 = np.asarray(image2.convert('1'))
    diff_array: np.ndarray = array1 ^ array2
    diff = np.count_nonzero(diff_array) / np.multiply(*diff_array.shape)
    return diff


def listTTF(ttf: ttFont.TTFont) -> list[str]:
    """
    输入字体文件，输出该字体文件下所有字符。
    """
    return list(set(map(lambda x: chr(x), ttf.getBestCmap().keys())))


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


def loadJJFont(fontname: str) -> tuple[ImageFont.FreeTypeFont, ttFont.TTFont]:
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
    return fontTTF, ttf


def getJJimageHashs(fontname: str) -> dict[str, imagehash.ImageHash]:
    """
    获取指定名称晋江字体的ImageHash字典。
    """
    fontTTF, ttf = loadJJFont(fontname)
    keys = listTTF(ttf)
    hashs = list(map(lambda x: HashFunc(draw(x, fontTTF), hash_size=HashSize, mean=HashMeanFunc), keys))
    return dict(zip(keys, hashs))


def patchJJFontResult(fontname: str, jjFontTableDict: dict[str, str]) -> dict[str, str]:
    """
    对自动识别的晋江字符对照表进行一些修正。
    """

    def common_replace(tableDict: dict[str, str]) -> dict[str, str]:
        """
        通用替换
        """

        def replace(x):
            r = {
                "杲": "果",
                "曼": "最",
                "吋": "时"
            }
            rk = r.keys()
            if x in rk:
                return r[x]
            else:
                return x

        k = tableDict.keys()
        v = tableDict.values()
        v_patch = list(map(replace, v))
        return dict(zip(k, v_patch))

    def patch_JI_YI(tableDict: dict[str, str]) -> dict[str, str]:
        """
        修正已己错识
        """

        def cmp_JI_YI(x: str) -> str:
            """
            比较已己
            """
            targetFont = 'jjwxcfont_0055y'
            fontTTF, ttf = loadJJFont(targetFont)
            YI = '\ue09a'
            JI = '\ue13e'

            JJFontTTF, jjTtf = loadJJFont(fontname)
            X_img = draw(x, JJFontTTF)
            YI_img = draw(YI, fontTTF)
            JI_img = draw(JI, fontTTF)
            YI_diff = compare(YI_img, X_img)
            JI_diff = compare(JI_img, X_img)

            if YI_diff < JI_diff:
                return "已"
            else:
                return "己"

        JI_list = list(filter(lambda kvt: kvt[1] == "己", tableDict.items()))
        if len(JI_list) > 1:
            for kv in JI_list:
                k = kv[0]
                v = cmp_JI_YI(k)
                tableDict[k] = v
            return tableDict
        else:
            return tableDict

    _dict = common_replace(jjFontTableDict)
    _dict = patch_JI_YI(_dict)
    return _dict


def matchJJFont(fontname: str) -> dict[str, str]:
    """
    输入晋江字体名称，返回该字体匹配结果。
    """

    def match(jj: str, ihash: imagehash.ImageHash) -> str:
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
                mdiff2 = compare(draw(jj, JJFontTTF), drawFZ(k))
            else:
                if diff <= mdiff:
                    diff2 = compare(draw(jj, JJFontTTF), drawFZ(k))
                    if diff2 < mdiff2:
                        mkey = k
                        mdiff = diff
                        mdiff2 = diff2
        return mkey

    def quickMatch(jj: str, ttf: ttFont.TTFont) -> str:
        """
        通过直接比较字体快速匹配
        """
        FUZZ = 20

        def is_glpyh_similar(a: list[tuple[int, int]], b: list[tuple[int, int]], fuzz: int):
            """
            比较两字符 coor 是否相似。
            来自：https://github.com/fffonion/JJGet/blob/master/scripts/generate_font.py#L37-L45
            """
            if len(a) != len(b):
                return False
            found = True
            for i in range(len(a)):
                if abs(a[i][0] - b[i][0]) > fuzz or abs(a[i][1] - b[i][1]) > fuzz:
                    found = False
                    break
            return found

        jjCoord = getCoord(jj, ttf)
        for stdKey in CoorTable:
            stdCoord = CoorTable[stdKey]
            if is_glpyh_similar(jjCoord, stdCoord, FUZZ):
                return stdKey

    FZhashsdict = getFZImageHashs()
    FZkeys = FZhashsdict.keys()
    FZhashs = FZhashsdict.values()

    JJhashsdict = getJJimageHashs(fontname)
    JJFontTTF, JJttf = loadJJFont(fontname)
    JJkeys = list(JJhashsdict.keys())
    JJhashs = list(JJhashsdict.values())

    logging.info(f'开始识别字体 {fontname}')
    results = {}
    for i in range(len(JJkeys)):
        jjkey = JJkeys[i]
        if jjkey == 'x':
            continue
        jjhash = JJhashs[i]
        mchar = quickMatch(jjkey, JJttf)
        if not mchar:
            logging.info(f'快速匹配失败，开始图形匹配。字体名称：{fontname}，字体编号：{hex(ord(jjkey))}')
            mchar = match(jjkey, jjhash)
            mCoor = getCoord(mchar, JJttf)
            CoorTable[mchar] = mCoor
            saveCoorTable()
        logging.debug("{}\t{}\t{}".format(fontname, ord(jjkey), mchar))
        results[jjkey] = mchar

    results = patchJJFontResult(fontname, results)
    logging.info(f'识别字体 {fontname} 完成。')
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
        htmlTemplate = Env.get_template('font.html.j2')

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
    logging.debug("{}\t{}".format(fontname, 'start!'))
    results = matchJJFont(fontname)
    saveJJFont(fontname, results)
    logging.debug("{}\t{}".format(fontname, 'finished!'))


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

    def saveJSON() -> dict[str, dict[str, str]]:
        """
        将 tables 目录下所有JSON文件打包为单一JSON文件。
        """
        bundleJSON = {}
        for fname in jsonFiles:
            fontname = fname.split('.')[0]
            with open(os.path.join(TablesDir, fname), 'r') as f:
                table: dict[str, str] = json.load(f)
            bundleJSON[fontname] = table

        bundleJSON = dict(sorted(bundleJSON.items(), key=lambda x: x[0].lower()))
        with open(os.path.join(DistDir, 'bundle.json'), 'w') as f:
            json.dump(bundleJSON, f)

        return bundleJSON

    def saveTS(bundleJSON) -> None:
        """
        将 tables 目录下所有JSON文件打包为Typescript模块文件。
        """
        ts = 'export interface jjwxcFontTable {[index: string]: string;} ' \
             'interface jjwxcFontTables {[index: string]: jjwxcFontTable;} ' \
             f'export const jjwxcFontTables: jjwxcFontTables = {json.dumps(bundleJSON)}'
        with open(os.path.join(DistDir, 'bundle.ts'), 'w') as fp:
            fp.write(ts)

    def githubPage() -> None:
        """
        生成 github page 页面
        """
        docsDir = os.path.join(DistDir, 'docs')
        if not os.path.exists(docsDir):
            os.mkdir(docsDir)

        fontnames = list(map(lambda x: x.split('.')[0], jsonFiles))
        fontnames = sorted(fontnames)
        for fontname in fontnames:
            src = os.path.join(TablesDir, f'{fontname}.html')
            dst = os.path.join(docsDir, f'{fontname}.html')
            shutil.copy(src, dst)

        shutil.copy(os.path.join(DistDir, 'bundle.json'), os.path.join(docsDir, 'bundle.json'))
        shutil.copy(os.path.join(DistDir, 'bundle.ts'), os.path.join(docsDir, 'bundle.ts'))

        indexTemplate = Env.get_template('index.html.j2')
        indexText = indexTemplate.render(fontnames=fontnames)
        with open(os.path.join(docsDir, "index.html"), 'w') as f:
            f.write(indexText)

    jsonFiles = list(filter(lambda x: x.endswith('.json'), os.listdir(TablesDir)))
    bundleDict = saveJSON()
    saveTS(bundleDict)
    githubPage()


def getCoord(char: str, ttf: ttFont.TTFont) -> list[tuple[int, int]]:
    """
    获取特定字体，指定字符的 coord
    """
    cmap = ttf.getBestCmap()
    glyf_name = cmap[ord(char)]
    coord = ttf['glyf'][glyf_name].coordinates
    coord_list = list(coord)
    return coord_list


def getCoorTable(fontname: str) -> dict[str, list[tuple[int, int]]]:
    """
    获取指定字体的 coordTable
    """
    with open(os.path.join(TablesDir, f'{fontname}.json'), 'r') as f:
        fontTable = json.load(f)
    _, ttf = loadJJFont(fontname)

    fontTableR = dict(zip(fontTable.values(), fontTable.keys()))
    coordTable = dict(
        zip(
            fontTableR.keys(),
            map(lambda x: getCoord(x, ttf), fontTableR.values())
        )
    )
    return coordTable


def saveCoorTable() -> None:
    """
    保存当前 coordTable
    """
    with open(coorTableJsonPath, 'w') as f:
        json.dump(CoorTable, f)


if __name__ == "__main__":
    import argparse

    logging.basicConfig(stream=sys.stdout, level=logging.INFO)

    parser = argparse.ArgumentParser(description="晋江自定义字体破解辅助工具。")
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

