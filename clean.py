import os
import hashlib

import main


def getFontFileSha1(fontname: str) -> str:
    fontPath = main.getFontPath(fontname)
    with open(fontPath, 'rb') as f:
        sha1 = hashlib.sha1(f.read())
        return sha1.hexdigest()


def getRemoteFontFileSha1(fontname: str) -> str:
    fontContent = main.getFontFile(fontname)
    sha1 = hashlib.sha1(fontContent)
    return sha1.hexdigest()


def compareHash(fontname: str) -> bool:
    hashLocal = getFontFileSha1(fontname)
    try:
        hashRemote = getRemoteFontFileSha1(fontname)
        match = hashLocal == hashRemote
    except FileNotFoundError as e:
        print(main.CRED + 'Font {} not Found on Remote!'.format(fontname))
        match = False
    if match:
        print(main.CGREEN + 'Font: {} consistent!'.format(fontname))
    else:
        print(main.CRED + 'Fontname: {} inconsistent!'.format(fontname))
    return match


def deleteFont(fontname: str) -> None:
    fontPath = main.getFontPath(fontname)
    jsonPath = main.getFontJsonPath(fontname)
    htmpPath = main.getHtmlPath(fontname)
    os.remove(fontPath)
    os.remove(jsonPath)
    os.remove(htmpPath)
    print(main.CRED + 'Font {} has been deleted!'.format(fontname))


if __name__ == '__main__':
    fontnames: list[str] = list(
        map(lambda x: x.replace('.woff2', ''), os.listdir(main.FontsDir))
    )
    for fontname in fontnames:
        m = compareHash(fontname)
        if not m:
            deleteFont(fontname)
