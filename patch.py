import json
import os
from typing import Dict

import main

tablesFolderPath = os.path.join(main.PWD, 'tables')

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
    },
    "jjwxcfont_000qt": {
        "\uef45": "已"
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


def run():
    jsonFlist = list(
        filter(lambda x: x.endswith('.json'), os.listdir(tablesFolderPath))
    )
    for fname in jsonFlist:
        fontname = fname.split('.')[0]
        fpath = os.path.join(tablesFolderPath, fname)
        with open(fpath, 'r') as f:
            table = json.load(f)
        table = patch(fontname, table)
        main.saveJJFont(fontname, table, tablesFolderPath)


if __name__ == '__main__':
    run()
