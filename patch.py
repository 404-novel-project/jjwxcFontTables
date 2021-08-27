import json
import os
from typing import Dict

import main

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


def patch(fontname: str, jjFontTableDict: dict[str, str]) -> dict[str, str]:
    """
    对晋江字符对照表进行一些修正。
    """

    def replace(x: str) -> str:
        """
        通用修正
        """
        r = {"杲": "果",
             "曼": "最"}
        rk = r.keys()
        if x in rk:
            return r[x]
        else:
            return x

    def replace_by_dict() -> None:
        """
        字典修正
        """
        if patchDicts.get(fontname):
            r = patchDicts[fontname]
            for i in r:
                jjFontTableDict[i] = r[i]

    replace_by_dict()
    k = jjFontTableDict.keys()
    v = jjFontTableDict.values()
    v_patch = list(map(replace, v))
    return dict(zip(k, v_patch))


def run() -> None:
    """
    主入口，修正 tables 目录下所有结果。
    """
    jsonFlist = list(
        filter(lambda x: x.endswith('.json'), os.listdir(main.TablesDir))
    )
    for fname in jsonFlist:
        fontname = fname.split('.')[0]
        fpath = os.path.join(main.TablesDir, fname)
        with open(fpath, 'r') as f:
            table = json.load(f)
        table = patch(fontname, table)
        main.saveJJFont(fontname, table, main.TablesDir)


if __name__ == '__main__':
    run()
