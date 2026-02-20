from http.server import BaseHTTPRequestHandler
import json
import math
import os
import requests
from datetime import date


# ==========================================================
# Util: enviar respuesta JSON
# ==========================================================
def _send_json(handler, status_code, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


# ==========================================================
# Conversión coordenadas SIAR DMS → decimal
# ==========================================================
def siar_to_dec(coord, is_lon):
    coord = (coord or "").strip()
    if not coord:
        raise ValueError("Coordenada vacía")

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


# ==========================================================
# Distancia Haversine (km)
# ==========================================================
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    )

    return 2 * R * math.asin(math.sqrt(a))


# ==========================================================
# Cargar estaciones SIAR
# ==========================================================
def load_estaciones():
    here = os.path.dirname(__file__)
    fp = os.path.abspath(os.path.join(here, "..", "estaciones_siar.json"))

    with open(fp, "r", encoding="utf-8") as f:
        data = json.load(f)

    arr = data.get("datos", data)

    if not isinstance(arr, list):
        raise ValueError("Formato estaciones_siar.json inválido")

    return arr


# ==========================================================
# Encontrar estación más cercana
# ==========================================================
def nearest_station(lat, lon):
    estaciones = load_estaciones()
    best = None

    for e in estaciones:
        try:
            lat_e = siar_to_dec(e.get("Latitud"), False)
            lon_e = siar_to_dec(e.get("Longitud"), True)

            dist = haversine_km(lat, lon, lat_e, lon_e)

            if best is None or dist < best["dist_km"]:
                best = {
                    "Codigo": e.get("Codigo"),
                    "Estacion": e.get("Estacion"),
                    "dist_km": dist,
                    "lat": lat_e,
                    "lon": lon_e,
                }

        except Exception:
            continue

    if not best:
        raise ValueError("No se pudo determinar estación más cercana")

    return best
# ==========================================================
# Obtener token SIAR
# ==========================================================
def get_siar_token():
    base_url = os.environ.get("SIAR_BASE_URL")
    nif = os.environ.get("SIAR_NIF")
    password = os.environ.get("SIAR_PASSWORD")

    if not base_url or not nif or not password:
        raise ValueError("Faltan variables de entorno SIAR")

    # 1️⃣ Cifrar NIF
    r1 = requests.get(f"{base_url}/API/V1/Autenticacion/CifrarUsuario",
                      params={"Usuario": nif})
    r1.raise_for_status()
    nif_cifrado = r1.text.strip().replace('"', '')

    # 2️⃣ Cifrar Password
    r2 = requests.get(f"{base_url}/API/V1/Autenticacion/CifrarPassword",
                      params={"Password": password})
    r2.raise_for_status()
    password_cifrado = r2.text.strip().replace('"', '')

    # 3️⃣ Obtener token
    r3 = requests.get(f"{base_url}/API/V1/Autenticacion/ObtenerToken",
                      params={
                          "Usuario": nif_cifrado,
                          "Password": password_cifrado
                      })
    r3.raise_for_status()

    token = r3.text.strip()

    return token


# ==========================================================
# Handler Vercel
# ==========================================================
class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        _send_json(self, 200, {
            "ok": True,
            "route": "GET /api/siar_mensual",
            "mode": "BASE"
        })

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b"{}"
            payload = json.loads(raw.decode("utf-8"))

            lat = float(payload["lat"])
            lon = float(payload["lon"])

            station = nearest_station(lat, lon)
            token = get_siar_token()


            _send_json(self, 200, {
                "ok": True,
                "estacion": station,
                "token_preview": token[:20] + "..."
            })


        except Exception as e:
            _send_json(self, 400, {
                "ok": False,
                "error": str(e)
            })
