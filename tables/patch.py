import json
import os
from typing import Dict

from main import saveJJFont

PWD = os.path.abspath(os.path.dirname(__file__))
tablesFolderPath = PWD

patchDicts = {
    "jjwxcfont_00heq": {
        "\ueae6": "已"
    },
    "jjwxcfont_00huu": {
        "\ue24b": "已"
    },
    "jjwxcfont_00jat": {
        "\ue519": "已"
    },
    "jjwxcfont_00k07": {
        "\ue1de": "已"
    },
    "jjwxcfont_00gv7": {
        "\uea86": "已"
    }
}


def patch(fontname, jjFontTableDict: Dict):
    def replace(x):
        r = {"杲": "果",
             "曼": "最"}
        rk = r.keys()
        if x in rk:
            return r[x]
        else:
            return x

    def replace0():
        if patchDicts.get(fontname):
            r = patchDicts[fontname]
            for i in r:
                jjFontTableDict[i] = r[i]

    replace0()
    k = jjFontTableDict.keys()
    v = jjFontTableDict.values()
    v_patch = list(map(replace, v))
    return dict(zip(k, v_patch))


def main():
    jsonFlist = list(filter(lambda x: x.endswith('.json'), os.listdir(PWD)))
    for fname in jsonFlist:
        fontname = fname.split('.')[0]
        with open(fname, 'r') as f:
            table = json.load(f)
        table = patch(fontname, table)
        saveJJFont(fontname, table, PWD)


if __name__ == '__main__':
    main()
