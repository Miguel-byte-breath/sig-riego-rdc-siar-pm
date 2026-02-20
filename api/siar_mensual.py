from http.server import BaseHTTPRequestHandler
import json
import math
import os

# ---------- util JSON response ----------
def _send_json(h, status: int, payload: dict):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    h.send_response(status)
    h.send_header("Content-Type", "application/json; charset=utf-8")
    h.send_header("Cache-Control", "no-store")
    h.end_headers()
    h.wfile.write(body)

# ---------- SIAR coord to decimal ----------
def siar_to_dec(coord: str, is_lon: bool) -> float:
    coord = (coord or "").strip()
    hemi = coord[-1].upper()
    digits = coord[:-1]

    if is_lon:
        deg_len = 2 if digits.startswith("00") else 3
    else:
        deg_len = 2

    deg = int(digits[0:deg_len])
    mins = int(digits[deg_len:deg_len + 2])
    secs = float(digits[deg_len + 2:]) / 1000.0

    dec = deg + (mins / 60.0) + (secs / 3600.0)
    if hemi in ("W", "S"):
        dec = -dec
    return dec

def haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))

def load_estaciones():
    here = os.path.dirname(__file__)
    fp = os.path.abspath(os.path.join(here, "..", "estaciones_siar.json"))
    with open(fp, "r", encoding="utf-8") as f:
        data = json.load(f)
    arr = data.get("datos", data)
    if not isinstance(arr, list):
        raise ValueError("Formato estaciones_siar.json inválido")
    return arr

def nearest_station(lat, lon):
    estaciones = load_estaciones()
    best = None
    for e in estaciones:
        try:
            lat_e = siar_to_dec(e.get("Latitud"), False)
            lon_e = siar_to_dec(e.get("Longitud"), True)
            d = haversine_km(lat, lon, lat_e, lon_e)
            if (best is None) or (d < best["dist_km"]):
                best = {
                    "Codigo": e.get("Codigo"),
                    "Estacion": e.get("Estacion"),
                    "dist_km": d,
                    "lat": lat_e,
                    "lon": lon_e
                }
        except Exception:
            continue
    if not best or not best.get("Codigo"):
        raise ValueError("No se pudo determinar estación más cercana")
    return best

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # pequeño diagnóstico
        _send_json(self, 200, {"ok": True, "route": "GET /api/siar_mensual", "mode": "BASE"})
        return

      def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b"{}"
            payload = json.loads(raw.decode("utf-8"))

            lat = float(payload["lat"])
            lon = float(payload["lon"])

            est = nearest_station(lat, lon)

            _send_json(self, 200, {
                "ok": True,
                "route": "POST /api/siar_mensual",
                "estacion": est
            })

        except Exception as e:
            _send_json(self, 400, {
                "ok": False,
                "error": str(e)
            })

