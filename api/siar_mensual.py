from http.server import BaseHTTPRequestHandler
import json
import math
import os
from datetime import datetime
import requests

# =========================
# CONFIGURACIÓN
# =========================

SIAR_BASE_URL = os.environ.get("SIAR_BASE_URL", "https://servicio.mapa.gob.es/siarapi")
SIAR_NIF = os.environ.get("SIAR_NIF", "").strip()
SIAR_PASSWORD = os.environ.get("SIAR_PASSWORD", "").strip()

_cached_token = None


# =========================
# UTILIDADES
# =========================

def _strip_wrapping_quotes(s: str) -> str:
    s = (s or "").strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        s = s[1:-1]
    return s.strip()


def _siar_cifrar_cadena(cadena: str) -> str:
    url = f"{SIAR_BASE_URL}/API/V1/Autenticacion/cifrarCadena"
    r = requests.get(url, params={"cadena": cadena}, timeout=30)
    r.raise_for_status()
    return _strip_wrapping_quotes(r.text)


def _siar_invalidate_token():
    global _cached_token
    _cached_token = None


def _siar_obtener_token() -> str:
    global _cached_token

    if _cached_token:
        return _cached_token

    if not SIAR_NIF or not SIAR_PASSWORD:
        raise ValueError("Faltan SIAR_NIF o SIAR_PASSWORD en ENV")

    u_enc = _siar_cifrar_cadena(SIAR_NIF)
    p_enc = _siar_cifrar_cadena(SIAR_PASSWORD)

    url = f"{SIAR_BASE_URL}/API/V1/Autenticacion/obtenerToken"
    r = requests.get(url, params={"Usuario": u_enc, "Password": p_enc}, timeout=30)
    r.raise_for_status()

    token = _strip_wrapping_quotes(r.text)

    if not token:
        raise ValueError("Token vacío")

    _cached_token = token
    return token


def siar_to_dec(coord: str, is_lon: bool) -> float:
    coord = coord.strip()
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


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))


def load_estaciones():
    here = os.path.dirname(__file__)
    fp = os.path.abspath(os.path.join(here, "..", "estaciones_siar.json"))
    with open(fp, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("datos", [])


def nearest_station(lat, lon):
    estaciones = load_estaciones()
    best = None

    for e in estaciones:
        try:
            lat_e = siar_to_dec(e["Latitud"], False)
            lon_e = siar_to_dec(e["Longitud"], True)
            d = haversine_km(lat, lon, lat_e, lon_e)

            if best is None or d < best["dist_km"]:
                best = {
                    "Codigo": e["Codigo"],
                    "Estacion": e["Estacion"],
                    "dist_km": d
                }
        except Exception:
            continue

    return best


def fetch_mensuales(codigo, anio_ref):
from datetime import date  # arriba en imports (si no lo tienes)

fecha_ini = f"{anio_ref - 2}-01-01"

hoy = date.today().isoformat()               # "YYYY-MM-DD"
fin_teorico = f"{anio_ref}-12-31"
fecha_fin = min(fin_teorico, hoy)            # evita pedir futuro a SiAR


    token = _siar_obtener_token()

    url = f"{SIAR_BASE_URL}/API/V1/Datos/Mensuales/ESTACION"

    params = {
        "Id": codigo,
        "FechaInicial": fecha_ini,
        "FechaFinal": fecha_fin,
        "DatosCalculados": "true",
        "token": token
    }

    r = requests.get(url, params=params, timeout=30)

    if r.status_code in (401, 403):
        _siar_invalidate_token()
        token = _siar_obtener_token()
        params["token"] = token
        r = requests.get(url, params=params, timeout=30)

    r.raise_for_status()
    return r.json().get("datos", [])


def climatologia(datos, anio_ref):
    ventana = {anio_ref - 2, anio_ref - 1, anio_ref}
    acc = {m: {"et": [], "p": []} for m in range(1, 13)}

    for r in datos:
        anio = r.get("Año") or r.get("Anio")
        mes = r.get("Mes")

        if anio in ventana and mes in acc:
            if isinstance(r.get("EtPMon"), (int, float)):
                acc[mes]["et"].append(r["EtPMon"])
            if isinstance(r.get("Precipitacion"), (int, float)):
                acc[mes]["p"].append(r["Precipitacion"])

    salida = []
    for mes in range(1, 13):
        et_list = acc[mes]["et"]
        p_list = acc[mes]["p"]

        salida.append({
            "mes": mes,
            "EtPMon": sum(et_list)/len(et_list) if et_list else 0,
            "Precipitacion": sum(p_list)/len(p_list) if p_list else 0
        })

    return salida


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body)

            lat = float(data["lat"])
            lon = float(data["lon"])
            fIni = data["fIni"]

            anio_ref = datetime.strptime(fIni[:10], "%Y-%m-%d").year

            est = nearest_station(lat, lon)
            datos = fetch_mensuales(est["Codigo"], anio_ref)
            clima = climatologia(datos, anio_ref)

            response = {
                "ok": True,
                "estacion": est,
                "climatologia": clima,
                "ventana": [anio_ref - 2, anio_ref - 1, anio_ref]
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

        except Exception as e:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode())
