"""Serves only the dashboard pages from /data.

The data folder also holds tokens, .env files and history JSON, so every
other path returns 404.
"""
import http.server
import os

DATA_DIR = os.environ.get('DATA_DIR', '/data')
PORT = int(os.environ.get('PORT', '8080'))
PAGES = {'/': 'index.html', '/index.html': 'index.html', '/dashboard.html': 'dashboard.html'}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self, head_only=False):
        name = PAGES.get(self.path.split('?', 1)[0])
        try:
            with open(os.path.join(DATA_DIR, name), 'rb') as f:
                body = f.read()
        except (TypeError, OSError):
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def do_HEAD(self):
        self.do_GET(head_only=True)


if __name__ == '__main__':
    print(f'Serving dashboard from {DATA_DIR} on port {PORT}', flush=True)
    http.server.ThreadingHTTPServer(('', PORT), Handler).serve_forever()
