#!/usr/bin/env python3
"""
navamesh_update_server.py — static APK host for phone OTA updates, with Range.

Replaces `python3 -m http.server`, which answers a Range request with 200 and
the whole file. That made every interrupted download restart from byte 0: a
~91 MB APK over the HaLow mesh, refetched in full after any blip. Android's
DownloadManager (see sbapp/farmui/updater.py) resumes on its own, but only when
the server supports Range -- so without this the phone-side retry is wasted.

Serves DIRECTORY read-only over HTTP/1.1 and advertises Accept-Ranges: bytes.
Same port and directory as the unit it replaces; no other behaviour change.

Paths come from the environment so one file serves both the deployment Pi and a
test Pi with a different user:
    NAVAMESH_UPDATES_DIR   (default /home/pi/navamesh-updates)
    NAVAMESH_UPDATES_PORT  (default 8090 -- not 8080, which the map tiles
                            nginx container already uses)
"""
import http.server
import os
import re
import shutil
import sys

DIRECTORY = os.environ.get("NAVAMESH_UPDATES_DIR", "/home/pi/navamesh-updates")
PORT = int(os.environ.get("NAVAMESH_UPDATES_PORT", "8090"))

_RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")


class _Limited:
    """File wrapper that stops after `remaining` bytes.

    SimpleHTTPRequestHandler.copyfile() copies to EOF, which for a 206 would
    send past the end of the requested range.
    """

    def __init__(self, fileobj, remaining):
        self._f = fileobj
        self._remaining = remaining

    def read(self, size=-1):
        if self._remaining <= 0:
            return b""
        if size is None or size < 0 or size > self._remaining:
            size = self._remaining
        chunk = self._f.read(size)
        self._remaining -= len(chunk)
        return chunk

    def close(self):
        self._f.close()


class RangeHandler(http.server.SimpleHTTPRequestHandler):
    # HTTP/1.1 so clients get keep-alive and an honest Content-Length; the base
    # class already sets Content-Length on everything it generates.
    protocol_version = "HTTP/1.1"
    server_version = "NavameshUpdateServer/1.0"

    def __init__(self, *a, **kw):
        kw.setdefault("directory", DIRECTORY)
        super().__init__(*a, **kw)

    def end_headers(self):
        # Advertised on every response, including a plain 200: this is how a
        # client learns it may resume at all.
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def send_head(self):
        rng = self.headers.get("Range")
        if not rng:
            return super().send_head()

        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().send_head()

        m = _RANGE_RE.match(rng.strip())
        if not m:
            return super().send_head()   # unparsable → serve the whole file

        try:
            f = open(path, "rb")
        except OSError:
            self.send_error(404, "File not found")
            return None

        try:
            size = os.fstat(f.fileno()).st_size
            start_s, end_s = m.groups()
            if not start_s and not end_s:
                f.close()
                return super().send_head()
            if not start_s:
                # Suffix form "bytes=-500" — the trailing N bytes.
                start, end = max(0, size - int(end_s)), size - 1
            else:
                start = int(start_s)
                end = int(end_s) if end_s else size - 1

            if start >= size or start > end:
                f.close()
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return None

            end = min(end, size - 1)
            length = end - start + 1
            f.seek(start)
            self.send_response(206)
            self.send_header("Content-Type", self.guess_type(path))
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Content-Length", str(length))
            self.send_header(
                "Last-Modified",
                self.date_time_string(os.fstat(f.fileno()).st_mtime))
            self.end_headers()
            return _Limited(f, length)
        except Exception:
            f.close()
            raise

    def copyfile(self, source, outputfile):
        # shutil handles _Limited fine (it only needs .read); kept explicit so
        # the 206 path is obviously the same copy loop as the 200 path.
        shutil.copyfileobj(source, outputfile)


def main():
    os.chdir(DIRECTORY)
    httpd = http.server.ThreadingHTTPServer(("", PORT), RangeHandler)
    httpd.daemon_threads = True
    print(f"serving {DIRECTORY} on :{PORT} with Range support", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    sys.exit(main())
