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
    mins = int(digits[deg_len : deg_len + 2])
    secs = float(digits[deg_len + 2 :]) / 1000.0

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
    r1 = requests.get(
        f"{base_url}/API/V1/Autenticacion/cifrarCadena",
        params={"cadena": nif},
        timeout=30,
    )
    r1.raise_for_status()
    nif_cifrado = r1.text.strip().replace('"', "")

    # 2️⃣ Cifrar password
    r2 = requests.get(
        f"{base_url}/API/V1/Autenticacion/cifrarCadena",
        params={"cadena": password},
        timeout=30,
    )
    r2.raise_for_status()
    password_cifrado = r2.text.strip().replace('"', "")

    # 3️⃣ Obtener token
    r3 = requests.get(
        f"{base_url}/API/V1/Autenticacion/obtenerToken",
        params={"Usuario": nif_cifrado, "Password": password_cifrado},
        timeout=30,
    )
    r3.raise_for_status()

    return r3.text.strip().replace('"', "")



# ==========================================================
# Handler Vercel
# ==========================================================
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        _send_json(
            self,
            200,
            {"ok": True, "route": "GET /api/siar_mensual", "mode": "BASE"},
        )

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)

            # Normalizar entrada JSON (robusto: BOM + espacios)
            text = raw.decode("utf-8", "replace")
            text = text.lstrip("\ufeff").strip()
            payload = json.loads(text)

            lat = float(payload["lat"])
            lon = float(payload["lon"])

            # --- BEGIN: ventana 36 meses (3 años completos cerrados) ---
            def _parse_fini(fini_str):
                if not fini_str:
                    return date.today()
                s = str(fini_str).strip()
                if len(s) == 7 and s[4] == "-":  # YYYY-MM
                    y = int(s[0:4])
                    m = int(s[5:7])
                    return date(y, m, 1)
                y = int(s[0:4])
                m = int(s[5:7])
                d = int(s[8:10])
                return date(y, m, d)

            def _add_months(d, months):
                y = d.year + (d.month - 1 + months) // 12
                m = (d.month - 1 + months) % 12 + 1
                return date(y, m, 1)

            fIni = payload.get("fIni")
            ref = _parse_fini(fIni)

            first_of_ref_month = date(ref.year, ref.month, 1)
            fecha_final_date = first_of_ref_month.fromordinal(first_of_ref_month.toordinal() - 1)
            fecha_inicial_date = _add_months(first_of_ref_month, -36)

            FechaInicial = fecha_inicial_date.strftime("%Y-%m-%d")
            FechaFinal = fecha_final_date.strftime("%Y-%m-%d")
            # --- END: ventana 36 meses ---

           station = nearest_station(lat, lon)
token = get_siar_token()

# ==========================================================
# 1️⃣ Calcular rango histórico correcto (3 años anteriores)
# ==========================================================
from calendar import monthrange

cicloIni = payload["cicloIni"]
cicloFin = payload["cicloFin"]

year_base = int(cicloIni[0:4])
mes_inicio = int(cicloIni[5:7])
mes_fin = int(cicloFin[5:7])

year_ini = year_base - 3
year_fin = year_base - 1

FechaInicial = f"{year_ini}-{mes_inicio:02d}-01"

last_day = monthrange(year_fin, mes_fin)[1]
FechaFinal = f"{year_fin}-{mes_fin:02d}-{last_day:02d}"

# ==========================================================
# 2️⃣ Llamar a SIAR Mensual (DatosCalculados = true)
# ==========================================================
r = requests.get(
    f"{os.environ.get('SIAR_BASE_URL')}/API/V1/Datos/Mensuales/ESTACION",
    params={
        "Estacion": station["Codigo"],
        "FechaInicial": FechaInicial,
        "FechaFinal": FechaFinal,
        "TipoDatos": "Mensuales",
        "DatosCalculados": "true",
        "token": token,
    },
    timeout=60,
)
r.raise_for_status()

data = r.json().get("datos", [])

# ==========================================================
# 3️⃣ Agrupar y promediar EtPMon y PePMon por mes
# ==========================================================
eto_por_mes = {}
pe_por_mes = {}
conteo = {}

for row in data:
    mes = row["Mes"]
    eto = row.get("EtPMon")
    pe = row.get("PePMon")

    if mes_inicio <= mes <= mes_fin:
        eto_por_mes[mes] = eto_por_mes.get(mes, 0) + eto
        pe_por_mes[mes] = pe_por_mes.get(mes, 0) + pe
        conteo[mes] = conteo.get(mes, 0) + 1

eto_climatologica = {
    mes: round(eto_por_mes[mes] / conteo[mes], 3)
    for mes in eto_por_mes
}

pe_climatologica = {
    mes: round(pe_por_mes[mes] / conteo[mes], 3)
    for mes in pe_por_mes
}

# ==========================================================
# 4️⃣ Devolver exactamente lo que necesita el motor actual
# ==========================================================
_send_json(
    self,
    200,
    {
        "ok": True,
        "estacion": station["Codigo"],
        "etoMensual": eto_climatologica,
        "peMensual": pe_climatologica,
    },
)

        except Exception as e:
            _send_json(self, 400, {"ok": False, "error": str(e)})
