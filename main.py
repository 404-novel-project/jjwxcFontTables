#!/usr/bin/env python
import json
import os
from functools import lru_cache
from typing import Dict

import imagehash
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import woff2, ttFont
from fs.memoryfs import MemoryFS
from jinja2 import Template

PWD = os.path.abspath(os.path.dirname(__file__))
MEM = MemoryFS()

# Setting
SIZE = 228
W, H = (SIZE, SIZE)

# FZFont
FZFontTTFPath = os.path.join(PWD, "assets", "FZLanTingHei-M-GBK.ttf")
FZFontTTF = ImageFont.truetype(FZFontTTFPath, SIZE, encoding="utf-8")

# FZHashs
FZHashPath = os.path.join(PWD, "assets", "FZLanTingHei-M-GBK-Hash-Table.json")

# ImageHash
HashSize = 16
HashFunc = imagehash.average_hash
HashMeanFunc = np.mean


def drawFZ(character):
    return draw(character, FZFontTTF)


@lru_cache(maxsize=1024)
def draw(character, fontTTF):
    image = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(image)
    offset_w, offset_h = fontTTF.getoffset(character)
    w, h = d.textsize(character, font=fontTTF)
    pos = ((W - w - offset_w) / 2, (H - h - offset_h) / 2)
    d.text(pos, character, "black", font=fontTTF)
    return image


def compare(image1, image2):
    array1 = np.asarray(image1) / 255
    array2 = np.asarray(image2) / 255
    diff = (array1 - array2).var()
    return diff


def listTTF(ttf):
    chars = []
    for x in ttf["cmap"].tables:
        for y in x.cmap.items():
            char_unicode = chr(y[0])
            chars.append(char_unicode)
    return chars


@lru_cache()
def getFZImageHashs():
    def genFZimageHashs():
        ttf = ttFont.TTFont(FZFontTTFPath)
        chars = listTTF(ttf)

        keys = list(filter(lambda x: 19967 < ord(x) < 40870, chars))
        hashs = list(map(lambda x: HashFunc(drawFZ(x), hash_size=HashSize, mean=HashMeanFunc), keys))
        return dict(zip(keys, hashs))

    def loadFZimageHashs():
        with open(FZHashPath, 'r') as f:
            _hashsdict_save: Dict = json.load(f)
        _keys = _hashsdict_save.keys()
        _hashs_str = _hashsdict_save.values()
        _hashs = list(map(lambda x: imagehash.hex_to_hash(x), _hashs_str))

        hashsdict = dict(zip(_keys, _hashs))
        return hashsdict

    def saveFZimageHashs():
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
        except BaseException as e:
            return saveFZimageHashs()
    else:
        return saveFZimageHashs()


def getJJimageHashs(fontname):
    fontPath = os.path.join(PWD, "fonts", fontname + ".woff2")
    if not os.path.exists(fontPath):
        raise FileNotFoundError

    fname = fontname + '.ttf'
    with MEM.open(fname, 'wb') as fw:
        woff2.decompress(fontPath, fw)
    with MEM.open(fname, 'rb') as fr:
        fontTTF = ImageFont.truetype(fr, SIZE - 5, encoding="utf-8")
        ttf = ttFont.TTFont(fr)

    keys = listTTF(ttf)
    hashs = list(map(lambda x: HashFunc(draw(x, fontTTF), hash_size=HashSize, mean=HashMeanFunc), keys))
    return dict(zip(keys, hashs)), fontTTF


def matchJJFont(fontname):
    def match(jjkey, jjhash, JJFont, FZkeys, FZhashs):
        diffs = list(map(lambda fzhash: fzhash - jjhash, FZhashs))
        diffs_dict = dict(zip(FZkeys, diffs))

        mkey = None
        mdiff = None
        mdiff2 = None
        for k in diffs_dict:
            diff = diffs_dict[k]
            if mkey is None:
                mkey = k
                mdiff = diff
                mdiff2 = compare(draw(jjkey, JJFont), drawFZ(k))
            else:
                if diff <= mdiff:
                    diff2 = compare(draw(jjkey, JJFont), drawFZ(k))
                    if diff2 < mdiff2:
                        mkey = k
                        mdiff = diff
                        mdiff2 = diff2
        return mkey

    def patch(jjFontTableDict: Dict):
        def replace(x):
            r = {"杲": "果",
                 "曼": "最"}
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

    JJhashsdict, JJFont = getJJimageHashs(fontname)
    JJkeys = list(JJhashsdict.keys())
    JJhashs = list(JJhashsdict.values())

    results = {}
    for i in range(len(JJkeys)):
        jjkey = JJkeys[i]
        if jjkey == 'x':
            continue
        jjhash = JJhashs[i]
        mchar = match(jjkey, jjhash, JJFont, FZkeys, FZhashs)
        print(fontname, ord(jjkey), mchar)
        results[jjkey] = mchar

    results = patch(results)
    return results


def saveJJFont(fontname, tablesDict, tablesFolderPath=os.path.join(PWD, "tables")):
    def saveJSON(fontname, tablesDict):
        fontJsonPath = os.path.join(tablesFolderPath, fontname + '.json')
        with open(fontJsonPath, 'w') as f:
            json.dump(tablesDict, f, sort_keys=True, indent=4)

    def saveHTML(fontname, tablesDict):
        htmlTemplate = Template('''
<!DOCTYPE html>
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
</html>
        ''')

        jjdicts = []
        for k in tablesDict:
            jjdict = {}
            jjdict['ord'] = str(hex(ord(k))).replace('0x', 'U+')
            jjdict['jjcode'] = k
            jjdict['unicode'] = tablesDict[k]
            jjdicts.append(jjdict)

        htmlText = htmlTemplate.render(fontname=fontname, jjdicts=jjdicts)

        htmlPath = os.path.join(tablesFolderPath, fontname + '.html')
        with open(htmlPath, 'w') as f:
            f.write(htmlText)

    saveJSON(fontname, tablesDict)
    saveHTML(fontname, tablesDict)


def JJFont(fontname):
    print(fontname, 'start!')
    results = matchJJFont(fontname)
    saveJJFont(fontname, results)
    print(fontname, 'finished!')


def matchAll():
    fontFolder = os.path.join(PWD, 'fonts')
    flist = os.listdir(fontFolder)
    fontnames = list(map(lambda x: x.split('.')[0], flist))

    import multiprocessing
    pool = multiprocessing.Pool()
    for fontname in fontnames:
        pool.apply_async(JJFont, (fontname,))
    pool.close()
    pool.join()


def bundle():
    def saveTS():
        ts1 = '''interface jjwxcFontTable {
  [index: string]: string;
}
interface jjwxcFontTables {
  [index: string]: jjwxcFontTable;
}

export function replaceJjwxcCharacter(fontName: string, inputText: string) {
  let outputText = inputText;
  const jjwxcFontTable = jjwxcFontTables[fontName];
  if (jjwxcFontTable) {
    for (const jjwxcCharacter in jjwxcFontTable) {
      const normalCharacter = jjwxcFontTable[jjwxcCharacter];
      outputText = outputText.replaceAll(jjwxcCharacter, normalCharacter);
    }
    outputText = outputText.replaceAll("\u200c", "");
  }
  return outputText;
}\n\n'''
        ts2 = 'const jjwxcFontTables: jjwxcFontTables = ' + json.dumps(bundle)
        with open(os.path.join(distFolder, 'bundle.ts'), 'w') as f:
            f.write(ts1 + ts2)

    distFolder = os.path.join(PWD, 'dist')
    tablesFolder = os.path.join(PWD, 'tables')
    jsonFiles = list(filter(lambda x: x.endswith('.json'), os.listdir(tablesFolder)))

    if not os.path.exists(distFolder):
        os.mkdir(distFolder)

    bundle = {}
    for fname in jsonFiles:
        fontname = fname.split('.')[0]
        with open(os.path.join(tablesFolder, fname), 'r') as f:
            table = json.load(f)
        bundle[fontname] = table

    with open(os.path.join(distFolder, 'bundle.json'), 'w') as f:
        json.dump(bundle, f)

    saveTS()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="晋江反爬字体破解辅助工具。")
    parser.add_argument('--all', action='store_true', help="匹配所有fonts目录下的woff2字体文件。")
    parser.add_argument('--bundle', action='store_true', help="打包tables目录下所有json文件。")
    parser.add_argument('--font', help="匹配指字名称字体文件。 例始：--font jjwxcfont_00gxm")
    args = parser.parse_args()

    if args.all:
        matchAll()
    elif args.bundle:
        bundle()
    elif args.font:
        JJFont(args.font)
