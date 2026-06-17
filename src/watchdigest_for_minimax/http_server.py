"""支持 Range Request 的简单 HTTP server。

minimax 服务端会发 Range Request 下载大文件。
Python 的 http.server 不支持 Range，所以自己写一个。
"""

from __future__ import annotations

import http.server
import io
import os
import re
import socketserver
import threading
from pathlib import Path
from typing import BinaryIO


class RangeHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """支持 Range Request 的 handler。"""

    def send_head(self) -> BinaryIO | None:
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().send_head()
        if not os.path.exists(path):
            self.send_error(404, "File not found")
            return None

        ctype = self.guess_type(path)
        with open(path, "rb") as f:
            fs = os.fstat(f.fileno())
            file_size = fs.st_size
            range_header = self.headers.get("Range")

            if range_header:
                m = re.search(r"bytes=(\d+)-(\d*)", range_header)
                if m:
                    start = int(m.group(1))
                    end = int(m.group(2)) if m.group(2) else file_size - 1
                    end = min(end, file_size - 1)
                    length = end - start + 1
                    f.seek(start)
                    self.send_response(206)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                    self.send_header("Content-Length", str(length))
                    self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
                    self.end_headers()
                    return io.BytesIO(f.read(length))

            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(file_size))
            self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
            self.end_headers()
            return io.BytesIO(f.read())


class ReusableTCPServer(socketserver.ThreadingTCPServer):
    """允许端口立即重用。"""

    allow_reuse_address = True


def start_server(
    directory: Path,
    host: str = "0.0.0.0",
    port: int = 41234,
) -> ReusableTCPServer:
    """启动 HTTP server（非阻塞，daemon 线程）。"""
    os.chdir(str(directory))
    server = ReusableTCPServer((host, port), RangeHTTPRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def stop_server(server: ReusableTCPServer) -> None:
    """停止 server。"""
    server.shutdown()
    server.server_close()
