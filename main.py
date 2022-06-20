#!/usr/bin/env python
import json
import logging
import os
import shutil
import sys
import tempfile
import time
from functools import lru_cache
from typing import Union

import h2.exceptions
import httpx
import imagehash
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import woff2, ttFont, TTLibError
from jinja2 import Environment, FileSystemLoader, select_autoescape

PWD: str = os.path.abspath(os.path.dirname(__file__))
FontsDir: str = os.path.join(PWD, 'fonts')
TablesDir: str = os.path.join(PWD, 'tables')
DistDir: str = os.path.join(PWD, 'dist')
AssetsDir: str = os.path.join(PWD, "assets")

# Setting
SIZE: int = 228
W, H = (SIZE, SIZE)

# StdFont
StdFontTTFPath: str = os.path.join(AssetsDir, "SourceHanSans.ttc")
StdFontTTF: ImageFont.FreeTypeFont = ImageFont.truetype(StdFontTTFPath, SIZE, index=12, encoding="utf-8")

# StdHashs
StdHashPath: str = os.path.join(AssetsDir, "SourceHanSans.json")

# ImageHash
HashSize: int = 16
HashFunc = imagehash.average_hash
HashMeanFunc = np.mean

# Jinja2
Env: Environment = Environment(loader=FileSystemLoader(os.path.join(PWD, 'templates')), autoescape=select_autoescape())

# coorTable
coorTableJsonPath = os.path.join(AssetsDir, "coorTable.json")
with open(coorTableJsonPath, 'r') as frp:
    CoorTable: [[str, [[int, int]]]] = json.load(frp)
del frp

# print color
# https://stackoverflow.com/questions/287871/how-to-print-colored-text-to-the-terminal
CRED = '\33[31m'
CGREEN = '\33[32m'


def mkdir() -> None:
    """
    创建所需文件夹。
    """
    for path in [FontsDir, TablesDir, DistDir, AssetsDir]:
        if not os.path.exists(path):
            os.mkdir(path)


mkdir()


def drawStd(character: str) -> ImageDraw:
    """
    输入字符，输出参考字体绘制结果。
    """
    return draw(character, StdFontTTF)


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
def getStdImageHashs() -> dict[str, imagehash.ImageHash]:
    """
    获取参考字体ImageHash字典。
    """

    def genStdimageHashs():
        """
        生成参考字体ImageHash字典。
        """
        ttf = ttFont.TTFont(StdFontTTFPath, fontNumber=0)
        chars = listTTF(ttf)

        keys = list(filter(lambda x: 19967 < ord(x) < 40870, chars))
        hashs = list(map(lambda x: HashFunc(drawStd(x), hash_size=HashSize, mean=HashMeanFunc), keys))
        return dict(zip(keys, hashs))

    def loadStdimageHashs():
        """
        从JSON文件载入参考字体ImageHash字典。
        """
        with open(StdHashPath, 'r') as f:
            _hashsdict_save: dict[str, str] = json.load(f)
        _keys = _hashsdict_save.keys()
        _hashs_str = _hashsdict_save.values()
        _hashs = list(map(lambda x: imagehash.hex_to_hash(x), _hashs_str))

        hashsdict = dict(zip(_keys, _hashs))
        return hashsdict

    def saveStdimageHashs():
        """
        将参考字体ImageHash字典保存为JSON文件。
        """
        hashsdict = genStdimageHashs()
        _keys = hashsdict.keys()
        _hashs = hashsdict.values()

        # save to json
        _hashs_str = list(map(lambda x: str(x), _hashs))
        _hashsdict_save = dict(zip(_keys, _hashs_str))
        with open(StdHashPath, 'w') as f:
            json.dump(_hashsdict_save, f)
        return hashsdict

    if os.path.exists(StdHashPath):
        try:
            return loadStdimageHashs()
        except json.decoder.JSONDecodeError:
            return saveStdimageHashs()
    else:
        return saveStdimageHashs()


httpClient: Union[None, httpx.Client] = None


def getFontFile(fontname: str, retry: int = 5) -> Union[bytes, None]:
    """
    请求字体文件
    """
    logging.info("请求字体文件：{}".format(fontname))
    url = "https://static.jjwxc.net/tmp/fonts/{}.woff2?h=my.jjwxc.net".format(fontname)
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:91.0) Gecko/20100101 Firefox/91.0",
        "Accept": "application/font-woff2;q=1.0,application/font-woff;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.5",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
        "Referer": "https://my.jjwxc.net/",
        "Origin": "https://my.jjwxc.net"
    }
    global httpClient
    if httpClient is None:
        httpClient = httpx.Client(headers=headers, http2=True)

    resp: Union[None, httpx.Response] = None
    while retry > 0:
        try:
            resp = httpClient.get(url)

            if resp.status_code == 404:
                logging.error(CRED + "未发现字体文件：{}".format(fontname))
                raise FileNotFoundError

            if 200 <= resp.status_code < 300:
                retry = 0
            else:
                time.sleep(6 - retry)
                retry = retry - 1
        except (httpx.TransportError, h2.exceptions.ProtocolError) as error:
            logging.error(error)
            time.sleep(6 - retry)
            retry = retry - 1

    if resp is not None:
        return resp.content
    else:
        return None


def getFontPath(fontname: str) -> str:
    return os.path.join(FontsDir, "{}.woff2".format(fontname))


def saveFontFile(fontname: str) -> bytes:
    """
    请求并保存字体文件
    """
    font = getFontFile(fontname)
    fontPath = getFontPath(fontname)
    if font is None:
        raise ValueError("fetch fonts failed!")
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
        try:
            woff2.decompress(fontPath, tmp)
            tmp.seek(0)
            fontTTF = ImageFont.truetype(tmp, SIZE, encoding="utf-8")
            ttf = ttFont.TTFont(tmp)
        except TTLibError as e:
            logging.error(e)
            os.remove(fontPath)
            raise e

    return fontTTF, ttf


def getJJimageHashs(fontname: str) -> dict[str, imagehash.ImageHash]:
    """
    获取指定名称晋江字体的ImageHash字典。
    """
    fontTTF, ttf = loadJJFont(fontname)
    keys = listTTF(ttf)
    hashs = list(map(lambda x: HashFunc(draw(x, fontTTF), hash_size=HashSize, mean=HashMeanFunc), keys))
    return dict(zip(keys, hashs))




def matchJJFont(fontname: str) -> dict[str, str]:
    """
    输入晋江字体名称，返回该字体匹配结果。
    """

    def match(jj: str, ihash: imagehash.ImageHash) -> str:
        """
        输入晋江字符以及晋江字符所对应ImageHash，返回最匹配的普通字符。
        """
        diffs = list(map(lambda stdhash: stdhash - ihash, Stdhashs))
        diffs_dict = dict(zip(Stdkeys, diffs))

        mkey = None
        mdiff = None
        mdiff2 = None
        for k in diffs_dict:
            diff = diffs_dict[k]
            if mkey is None:
                mkey = k
                mdiff = diff
                mdiff2 = compare(draw(jj, JJFontTTF), drawStd(k))
            else:
                if diff <= mdiff:
                    diff2 = compare(draw(jj, JJFontTTF), drawStd(k))
                    if diff2 < mdiff2:
                        mkey = k
                        mdiff = diff
                        mdiff2 = diff2
        return mkey

    def quickMatch(jj: str, ttf: ttFont.TTFont) -> Union[str, None]:
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
            for ii in range(len(a)):
                if abs(a[ii][0] - b[ii][0]) > fuzz or abs(a[ii][1] - b[ii][1]) > fuzz:
                    found = False
                    break
            return found

        jjCoord = getCoord(jj, ttf)
        for obj in CoorTable:
            [stdKey, stdCoord] = obj
            if is_glpyh_similar(jjCoord, stdCoord, FUZZ):
                return stdKey
        return None

    Stdhashsdict = getStdImageHashs()
    Stdkeys = Stdhashsdict.keys()
    Stdhashs = Stdhashsdict.values()

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
            logging.info(f'快速匹配失败，开始图形匹配。字体名称：{fontname}，字符编号：{hex(ord(jjkey))}')
            mchar = match(jjkey, jjhash)
            mCoor = getCoord(jjkey, JJttf)
            newCoor = [mchar, mCoor]
            CoorTable.append(newCoor)
            saveCoorTable()
        logging.debug("{}\t{}\t{}".format(fontname, ord(jjkey), mchar))
        results[jjkey] = mchar

    logging.info(f'识别字体 {fontname} 完成。')
    return results


def getFontJsonPath(fontname: str) -> str:
    return os.path.join(TablesDir, fontname + '.json')


def getHtmlPath(fontname: str) -> str:
    return os.path.join(TablesDir, fontname + '.html')


def genJJTableHtml(fontname: str, tablesDict: dict[str, str]):
    """
    生成晋江字体对照表HTML
    """
    htmlTemplate = Env.get_template('font.html.j2')

    jjdicts = []
    for k in tablesDict:
        jjdict = {'ord': str(hex(ord(k))).replace('0x', 'U+'), 'jjcode': k, 'unicode': tablesDict[k]}
        jjdicts.append(jjdict)

    jjdicts.sort(key=lambda x: x['jjcode'])
    htmlText = htmlTemplate.render(fontname=fontname, jjdicts=jjdicts)
    return htmlText


def reGenHtml():
    """
    重新生成 HTML 文件
    """
    fontJsonList = set(
        map(lambda x: x.split('.')[0],
            filter(lambda x: x.endswith('.json'), os.listdir(TablesDir))
            )
    )
    for fontname in fontJsonList:
        with open(getFontJsonPath(fontname), 'r') as f:
            tablesDict = json.load(f)
        htmlText = genJJTableHtml(fontname, tablesDict)
        htmlPath = getHtmlPath(fontname)
        with open(htmlPath, 'w') as f:
            f.write(htmlText)


def saveJJFont(fontname: str, tablesDict: dict[str, str]) -> None:
    """
    将晋江字体对照表保存为JSON文件、HTML文件。
    """

    def saveJSON() -> None:
        """
        将晋江字体对照表保存为JSON文件。
        """
        fontJsonPath = getFontJsonPath(fontname)
        with open(fontJsonPath, 'w') as f:
            json.dump(tablesDict, f, sort_keys=True, indent=4)

    def saveHTML() -> None:
        """
        将晋江字体对照表保存为HTML文件。
        """
        htmlText = genJJTableHtml(fontname, tablesDict)
        htmlPath = getHtmlPath(fontname)
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
        fontTable = dict[str, str]
        for fname in jsonFiles:
            fontname = fname.split('.')[0]
            with open(os.path.join(TablesDir, fname), 'r') as f:
                table: fontTable = json.load(f)
            bundleJSON[fontname] = table

        # noinspection PyTypeChecker
        bundleJSON = dict(
            sorted(bundleJSON.items(), key=lambda x: x[0].lower())
        )
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
        json.dump(CoorTable, f, ensure_ascii=False)


if __name__ == "__main__":
    import argparse

    logging.basicConfig(stream=sys.stdout, level=logging.INFO)

    parser = argparse.ArgumentParser(description="晋江自定义字体破解辅助工具。")
    parser.add_argument('--all', action='store_true', help="匹配所有fonts目录下的woff2字体文件。")
    parser.add_argument('--new', action='store_true', help="匹配fonts目录下新woff2字体。")
    parser.add_argument('--bundle', action='store_true', help="打包tables目录下所有json文件。")
    parser.add_argument('--rehtml', action='store_true', help="重新生成HTML文件")
    parser.add_argument('--font', help="匹配指字名称字体文件。 例始：--font jjwxcfont_00gxm")
    args = parser.parse_args()

    if args.all:
        matchAll()
    elif args.new:
        matchNew()
    elif args.bundle:
        bundle()
    elif args.rehtml:
        reGenHtml()
    elif args.font:
        JJFont(args.font)
