import datetime
import email.utils
import html
import logging
import multiprocessing
import os
import re
import shutil
import sys
import time
from http import HTTPStatus
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Optional

import main

MG: multiprocessing.managers.SyncManager = multiprocessing.Manager()
ON_PENDING = MG.list()
ON_WORKING = MG.list()
WORKING_NUM = MG.Value('i', 0)


class RequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    path_match = re.compile(r'^/(jjwxcfont_\w{5})\.json$')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:
        fontname = self.url_checker()
        if fontname:
            self.get_font(fontname)

    def do_HEAD(self) -> None:
        fontname = self.url_checker()
        if fontname:
            self.get_font(fontname)

    def url_checker(self) -> Optional[str]:
        """
        路径检查
        """
        m = re.match(self.path_match, self.path)
        if m:
            fontname = m[1]
            return fontname
        else:
            self.send_error(HTTPStatus.FORBIDDEN)
            return None

    def get_font(self, fontname: str) -> None:
        """
        获取字体（主函数）
        """
        font_path = os.path.join(main.TablesDir, "{}.json".format(fontname))

        if os.path.exists(font_path):
            self.found(font_path)
        else:
            self.not_found(fontname)

    def found(self, font_path: str) -> None:
        """
        发现字体对照表时处理逻辑
        """
        try:
            f = open(font_path, 'rb')
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return None

        try:
            fs = os.fstat(f.fileno())
            if ("If-Modified-Since" in self.headers
                    and "If-None-Match" not in self.headers):
                # compare If-Modified-Since and time of last file modification
                try:
                    ims = email.utils.parsedate_to_datetime(
                        self.headers["If-Modified-Since"])
                except (TypeError, IndexError, OverflowError, ValueError):
                    # ignore ill-formed values
                    pass
                else:
                    if ims.tzinfo is None:
                        # obsolete format with no timezone, cf.
                        # https://tools.ietf.org/html/rfc7231#section-7.1.1.1
                        ims = ims.replace(tzinfo=datetime.timezone.utc)
                    if ims.tzinfo is datetime.timezone.utc:
                        # compare to UTC datetime of last modification
                        last_modif = datetime.datetime.fromtimestamp(
                            fs.st_mtime, datetime.timezone.utc)
                        # remove microseconds, like in If-Modified-Since
                        last_modif = last_modif.replace(microsecond=0)

                        if last_modif <= ims:
                            self.send_response(HTTPStatus.NOT_MODIFIED)
                            self.send_cors_header()
                            self.end_headers()
                            f.close()
                            return None

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(fs[6]))
            self.send_header("Last-Modified", self.date_time_string(int(fs.st_mtime)))
            self.send_header("Cache-Control", "public, max-age=86400")
            self.send_cors_header()
            self.end_headers()

            if self.command != 'HEAD':
                shutil.copyfileobj(f, self.wfile)

            f.close()
        except Exception as e:
            f.close()
            raise e

    def not_found(self, fontname: str) -> None:
        """
        未发现字体对照表时处理逻辑
        """

        # 启用后台抓取解析线程
        if fontname not in ON_PENDING and fontname not in ON_WORKING:
            ON_PENDING.append(fontname)
            self.start_backend()

        # 休眠5秒
        time.sleep(5)

        font_path = os.path.join(main.TablesDir, "{}.json".format(fontname))
        if os.path.exists(font_path):
            self.found(font_path)
        else:
            code = HTTPStatus.NOT_FOUND
            shortmsg, longmsg = self.responses[code]

            self.send_response(code, shortmsg)
            self.send_header("Cache-Control", "public, max-age=600")

            content = (self.error_message_format % {
                'code': code,
                'message': html.escape(shortmsg, quote=False),
                'explain': html.escape(longmsg, quote=False)
            })
            body = content.encode('UTF-8', 'replace')
            self.send_header("Content-Type", self.error_content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_cors_header()
            self.end_headers()

            if self.command != 'HEAD' and body:
                self.wfile.write(body)

    def send_cors_header(self) -> None:
        """
        发送 CORS Header
        https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS
        """
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET")
        self.send_header("Access-Control-Allow-Headers", "Date, Etag, Content-Type, Content-Length")
        self.send_header("Access-Control-Max-Age", "86400")

    def start_backend(self) -> None:
        """
        启动后端识别程序
        """
        logging.info(f"ON_PENDING length： {len(ON_PENDING)}, WORKING_NUM: {WORKING_NUM.value}")
        if WORKING_NUM.value <= multiprocessing.cpu_count() and len(ON_PENDING) != 0:
            for fontname in ON_PENDING:
                if fontname not in ON_WORKING:
                    ON_WORKING.append(fontname)
                    ON_PENDING.remove(fontname)
                    WORKING_NUM.value = WORKING_NUM.value + 1
                    process = multiprocessing.Process(target=self.fetch_font, args=(fontname,))
                    process.start()

    def fetch_font(self, fontname: str) -> None:
        """
        对 main.JJFont 的包装
        """
        try:
            t = time.time()
            main.JJFont(fontname)
            ON_WORKING.remove(fontname)
            WORKING_NUM.value = WORKING_NUM.value - 1
            cost_time = time.time() - t
            logging.info("识别字体 {} 共耗费 {:.2f} 秒。".format(fontname, cost_time))
            self.start_backend()
        except FileNotFoundError:
            WORKING_NUM.value = WORKING_NUM.value - 1


if __name__ == '__main__':
    logging.basicConfig(stream=sys.stdout, format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)

    httpd = ThreadingHTTPServer(('localhost', 23578), RequestHandler)
    print('Serving HTTP on localhost port 23578 (http://localhost:23578/)')
    print('Starting server, use <Ctrl-C> to stop')
    httpd.serve_forever()
