import json
import os

import main


def run() -> None:
    """
    修正 tables 目录下所有结果。
    """
    jsonFlist = list(
        filter(lambda x: x.endswith('.json'), os.listdir(main.TablesDir))
    )
    for fname in jsonFlist:
        fontname = fname.split('.')[0]
        fpath = os.path.join(main.TablesDir, fname)
        with open(fpath, 'r') as f:
            table = json.load(f)
        table = main.patchJJFontResult(fontname, table)
        main.saveJJFont(fontname, table, main.TablesDir)


if __name__ == '__main__':
    run()
