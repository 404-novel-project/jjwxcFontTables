import hashlib
import logging
import os
import sys
from typing import Union

import main


def getFontFileSha1(fontname: str) -> str:
    fontPath = main.getFontPath(fontname)
    with open(fontPath, 'rb') as f:
        sha1 = hashlib.sha1(f.read())
        return sha1.hexdigest()


def getRemoteFontFileSha1(fontname: str) -> Union[str, None]:
    fontContent = main.getFontFile(fontname)
    if fontContent is not None:
        sha1 = hashlib.sha1(fontContent)
        return sha1.hexdigest()
    else:
        return None


def compareHash(fontname: str) -> bool:
    hashLocal = getFontFileSha1(fontname)
    try:
        hashRemote = getRemoteFontFileSha1(fontname)
        if hashRemote is not None:
            match = hashLocal == hashRemote
        else:
            logging.warning(main.CRED + 'Get Font {} from Remote failed!'.format(fontname))
            match = True
    except FileNotFoundError as e:
        logging.warning(main.CRED + 'Font {} not Found on Remote!'.format(fontname))
        match = False
    if match:
        logging.info(main.CGREEN + 'Font: {} consistent!'.format(fontname))
    else:
        logging.warning(main.CRED + 'Fontname: {} inconsistent!'.format(fontname))
    return match


def deleteFont(fontname: str) -> None:
    fontPath = main.getFontPath(fontname)
    jsonPath = main.getFontJsonPath(fontname)
    htmpPath = main.getHtmlPath(fontname)
    try:
        os.remove(fontPath)
        os.remove(jsonPath)
        os.remove(htmpPath)
    except FileNotFoundError as e:
        logging.error(e)
    logging.warning(main.CRED + 'Font {} has been deleted!'.format(fontname))


if __name__ == '__main__':
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)

    fontnames: list[str] = list(
        map(lambda x: x.replace('.woff2', ''), os.listdir(main.FontsDir))
    )
    for fontname in fontnames:
        m = compareHash(fontname)
        if not m:
            deleteFont(fontname)
