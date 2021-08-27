import datetime
import email.utils
import html
import time
import logging
import multiprocessing
import os
import re
import shutil
import sys
from http import HTTPStatus
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Optional

import main


class RequestHandler(BaseHTTPRequestHandler):
    server_version = "jjwxcHTTP"
    protocol_version = "HTTP/1.1"

    path_match = re.compile(r'^/(jjwxcfont_\w{5})\.json$')
    manager = multiprocessing.Manager()
    ON_WORKING = manager.list()

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
            self.send_header("Cache-Control", "public, max-age=21600")
            self.send_cors_header()
            self.end_headers()

            if self.command != 'HEAD':
                shutil.copyfileobj(f, self.wfile)

            f.close()
        except Exception:
            f.close()
            raise

    def not_found(self, fontname: str) -> None:
        """
        未发现字体对照表时处理逻辑
        """
        code = HTTPStatus.NOT_FOUND
        shortmsg, longmsg = self.responses[code]

        self.log_error("code %d, message %s", code, shortmsg)
        self.send_response(code, shortmsg)
        self.send_header('Connection', 'close')

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

        # 启用后台抓取解析线程
        if fontname not in self.ON_WORKING:
            self.ON_WORKING.append(fontname)
            process = multiprocessing.Process(target=self.fetch_font, args=(self, fontname,))
            process.start()

    def send_cors_header(self) -> None:
        """
        发送 CORS Header
        https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS
        """
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET")
        self.send_header("Access-Control-Allow-Headers", "Date, Etag, Content-Type, Content-Length")
        self.send_header("Access-Control-Max-Age", "86400")

    @staticmethod
    def fetch_font(self, fontname: str) -> None:
        """
        对 main.JJFont 的包装
        """
        try:
            t = time.time()
            main.JJFont(fontname)
            self.ON_WORKING.remove(fontname)
            cost_time = time.time() - t
            logging.info("识别字体 {} 共耗费 {:.2f} 秒。".format(fontname, cost_time))
        except FileNotFoundError:
            pass


if __name__ == '__main__':
    logging.basicConfig(stream=sys.stdout, format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)

    httpd = ThreadingHTTPServer(('localhost', 23578), RequestHandler)
    print('Serving HTTP on localhost port 23578 (http://localhost:23578/)')
    print('Starting server, use <Ctrl-C> to stop')
    httpd.serve_forever()
