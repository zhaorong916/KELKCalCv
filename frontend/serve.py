"""简单的 dist 静态文件服务 (SPA fallback) + /api 反向代理到 localhost:8000"""
import http.server
import urllib.request
import urllib.error
import os

DIST = os.path.join(os.path.dirname(__file__), 'dist')
BACKEND = 'http://127.0.0.1:8000'
PORT = 5174

def _mime(path):
    ext = os.path.splitext(path)[1].lower()
    return {
        '.html': 'text/html',
        '.js': 'application/javascript',
        '.mjs': 'application/javascript',
        '.css': 'text/css',
        '.json': 'application/json',
        '.svg': 'image/svg+xml',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.ico': 'image/x-icon',
        '.woff': 'font/woff',
        '.woff2': 'font/woff2',
    }.get(ext, 'application/octet-stream')

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/api'):
            return self._proxy()
        url_path = self.path.split('?')[0]
        file_path = os.path.join(DIST, url_path.lstrip('/'))
        if os.path.isfile(file_path):
            self._serve_file(file_path)
        else:
            # SPA fallback
            self._serve_file(os.path.join(DIST, 'index.html'))

    def do_POST(self):
        if self.path.startswith('/api'):
            return self._proxy()
        self.send_error(404)

    def _serve_file(self, path):
        with open(path, 'rb') as f:
            data = f.read()
        self.send_response(200)
        self.send_header('Content-Type', _mime(path))
        if path.endswith(('.js', '.css', '.html')):
            self.send_header('Cache-Control', 'no-cache')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _proxy(self):
        url = BACKEND + self.path
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            data = self.rfile.read(content_length) if content_length > 0 else None
            req = urllib.request.Request(url, data=data, method=self.command)
            skip = ('host', 'content-length', 'connection', 'accept-encoding')
            for k, v in self.headers.items():
                if k.lower() not in skip:
                    req.add_header(k, v)
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = resp.read()
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() not in ('transfer-encoding', 'connection', 'content-encoding'):
                        self.send_header(k, v)
                self.end_headers()
                self.wfile.write(body)
        except urllib.error.HTTPError as e:
            body = e.read()
            self.send_response(e.code)
            self.send_header('Content-Type', e.headers.get('Content-Type', 'application/json'))
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self.send_response(502)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(f'Proxy error: {e}'.encode())

httpd = http.server.HTTPServer(('0.0.0.0', PORT), Handler)
print(f'Serving dist on http://localhost:{PORT}  (proxy /api -> {BACKEND})')
httpd.serve_forever()
