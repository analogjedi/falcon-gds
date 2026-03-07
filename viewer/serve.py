from __future__ import annotations

import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


VIEWER_ROOT = Path(__file__).resolve().parent
REPO_ROOT = VIEWER_ROOT.parent


class ViewerHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str | None = None, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)

    def translate_path(self, path: str) -> str:
        request_path = unquote(urlparse(path).path)
        if request_path in {"", "/"}:
          return str(VIEWER_ROOT / "index.html")
        if request_path.startswith("/glb/"):
          relative = request_path.removeprefix("/glb/")
          return str(REPO_ROOT / "output" / "glb" / relative)
        return str(VIEWER_ROOT / request_path.lstrip("/"))

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer(("127.0.0.1", port), lambda *args, **kwargs: ViewerHandler(*args, directory=str(VIEWER_ROOT), **kwargs))
    print(f"Serving viewer at http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server")


if __name__ == "__main__":
    main()
