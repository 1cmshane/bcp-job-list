#!/usr/bin/env python3
"""
Big City Products - Job List Cloud Server
Reads PORT from environment (required by Railway/Render/Fly.io).
Set ACCESS_PASSWORD env var to require a password (optional but recommended).
"""

import json
import os
import threading
import hashlib
import base64
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
HTML_FILE  = os.path.join(BASE_DIR, 'BCP_JobList.html')
DATA_FILE  = os.path.join(BASE_DIR, 'data', 'bcp_data.json')
os.makedirs(os.path.join(BASE_DIR, 'data'), exist_ok=True)
PORT       = int(os.environ.get('PORT', 5000))
PASSWORD   = os.environ.get('ACCESS_PASSWORD', '')   # empty = no password

file_lock  = threading.Lock()


# ── helpers ──────────────────────────────────────────────────────────────────

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def save_data(data):
    with file_lock:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

def check_auth(handler):
    """Returns True if no password set, or if correct Basic-Auth header present."""
    if not PASSWORD:
        return True
    auth = handler.headers.get('Authorization', '')
    if auth.startswith('Basic '):
        try:
            decoded = base64.b64decode(auth[6:]).decode('utf-8')
            _, pwd = decoded.split(':', 1)
            return pwd == PASSWORD
        except Exception:
            pass
    return False

def require_auth(handler):
    handler.send_response(401)
    handler.send_header('WWW-Authenticate', 'Basic realm="BCP Job List"')
    handler.send_header('Content-Type', 'text/plain')
    handler.end_headers()
    handler.wfile.write(b'Unauthorised')


# ── request handler ──────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        if args and str(args[1]) not in ('200', '304'):
            super().log_message(format, *args)

    def send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def send_html(self):
        try:
            with open(HTML_FILE, 'rb') as f:
                body = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'BCP_JobList.html not found.')

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_GET(self):
        if not check_auth(self):
            require_auth(self)
            return
        path = urlparse(self.path).path
        if path in ('/', '/index.html'):
            self.send_html()
        elif path == '/api/data':
            self.send_json(200, load_data())
        elif path == '/health':
            self.send_json(200, {'status': 'ok'})
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if not check_auth(self):
            require_auth(self)
            return
        path = urlparse(self.path).path
        if path == '/api/data':
            length = int(self.headers.get('Content-Length', 0))
            body   = self.rfile.read(length)
            try:
                data = json.loads(body.decode('utf-8'))
                save_data(data)
                self.send_json(200, {'ok': True})
            except Exception as e:
                self.send_json(400, {'ok': False, 'error': str(e)})
        else:
            self.send_response(404)
            self.end_headers()


# ── main ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', PORT), Handler)
    print(f'BCP Job List server running on port {PORT}')
    if PASSWORD:
        print(f'Password protection: ON')
    else:
        print(f'Password protection: OFF  (set ACCESS_PASSWORD env var to enable)')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
