from http.server import BaseHTTPRequestHandler
import json

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        payload = {
            "ok": True,
            "service": "sig-riego-rdc-siar-pm",
            "route": "/api/ping"
        }
        body = json.dumps(payload).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)
        return

    # (Opcional) permitir HEAD sin error
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()
        return
