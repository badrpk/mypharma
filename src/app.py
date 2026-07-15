"""MyPharma — pharmacy catalog + refill demo API."""
from __future__ import annotations
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

DRUGS = [
    {"id": "d1", "name": "Paracetamol 500mg", "rx_required": False, "price_pkr": 40},
    {"id": "d2", "name": "Amoxicillin 250mg", "rx_required": True, "price_pkr": 180},
    {"id": "d3", "name": "Vitamin D3", "rx_required": False, "price_pkr": 320},
]
REFILLS: list[dict] = []

class H(BaseHTTPRequestHandler):
    def _json(self, code, obj):
        data = json.dumps(obj, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        p = urlparse(self.path)
        if p.path in ("/", "/health"):
            return self._json(200, {"ok": True, "service": "mypharma", "product": "Pharmacy catalog + refill"})
        if p.path == "/drugs":
            q = parse_qs(p.query)
            term = (q.get("q") or [""])[0].lower()
            items = [d for d in DRUGS if term in d["name"].lower()] if term else DRUGS
            return self._json(200, {"ok": True, "drugs": items})
        if p.path == "/refills":
            return self._json(200, {"ok": True, "refills": REFILLS})
        self._json(404, {"ok": False, "routes": ["/", "/drugs?q=", "/refills"]})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n).decode() or "{}") if n else {}
        if self.path == "/refills":
            drug = next((d for d in DRUGS if d["id"] == body.get("drug_id")), None)
            if not drug:
                return self._json(400, {"ok": False, "error": "unknown drug_id"})
            if drug["rx_required"] and not body.get("rx_code"):
                return self._json(400, {"ok": False, "error": "rx_code required for this medicine"})
            rec = {"id": f"rf_{len(REFILLS)+1}", "drug": drug, "patient": body.get("patient") or "anonymous", "status": "queued"}
            REFILLS.append(rec)
            return self._json(200, {"ok": True, "refill": rec})
        self._json(404, {"ok": False})

    def log_message(self, *a):
        return

def main():
    print("MyPharma http://127.0.0.1:8765  GET /drugs")
    HTTPServer(("127.0.0.1", 8765), H).serve_forever()

if __name__ == "__main__":
    main()
