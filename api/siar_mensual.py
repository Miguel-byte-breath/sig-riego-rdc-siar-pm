from http.server import BaseHTTPRequestHandler
import json
import math
import os
import requests
from datetime import date
from calendar import monthrange


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
# Encontrar N estaciones más cercanas (principal + apoyos)
# ==========================================================
def nearest_stations(lat, lon, n=6):
    estaciones = load_estaciones()
    ranked = []

    for e in estaciones:
        try:
            lat_e = siar_to_dec(e.get("Latitud"), False)
            lon_e = siar_to_dec(e.get("Longitud"), True)
            dist = haversine_km(lat, lon, lat_e, lon_e)

            ranked.append(
                {
                    "Codigo": e.get("Codigo"),
                    "Estacion": e.get("Estacion"),
                    "dist_km": dist,
                    "lat": lat_e,
                    "lon": lon_e,
                }
            )
        except Exception:
            continue

    ranked.sort(key=lambda x: x["dist_km"])

    if not ranked:
        raise ValueError("No se pudieron cargar estaciones SIAR")

    return ranked[: max(1, n)]

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
# Rangos temporales
# ==========================================================
def build_range_from_fIni(payload):
    """
    Ventana 36 meses (3 años completos cerrados) basada en fIni.
    fIni admite 'YYYY-MM' o 'YYYY-MM-DD'. Si no viene, usa hoy.
    Devuelve (FechaInicial, FechaFinal) en 'YYYY-MM-DD'.
    """
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
    # Fin = último día del mes anterior al mes de referencia
    fecha_final_date = first_of_ref_month.fromordinal(first_of_ref_month.toordinal() - 1)
    # Inicio = 36 meses antes (primer día de mes)
    fecha_inicial_date = _add_months(first_of_ref_month, -36)

    return (
        fecha_inicial_date.strftime("%Y-%m-%d"),
        fecha_final_date.strftime("%Y-%m-%d"),
    )


def build_range_from_ciclo(payload):
    """
    Rango histórico: 3 años anteriores (cerrados) en los meses del ciclo.
    Devuelve (FechaInicial, FechaFinal, mes_inicio, mes_fin).
    """
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

    return FechaInicial, FechaFinal, mes_inicio, mes_fin

# ==========================================================
# Fallback helpers
# ==========================================================
def _fallback_note(idx: int) -> str:
    return "principal" if idx == 0 else f"apoyo #{idx}"


def _is_valid_pack(eto_mensual: dict, pe_mensual: dict) -> bool:
    return (
        isinstance(eto_mensual, dict)
        and isinstance(pe_mensual, dict)
        and len(eto_mensual) > 0
        and len(pe_mensual) > 0
    )
# ==========================================================
# Intentar obtener pack (ETo+Pe) de una estación concreta
# ==========================================================
def fetch_pack_for_station(base_url_data, token, station_code, FechaInicial, FechaFinal, mes_inicio, mes_fin):
    r = requests.get(
        f"{base_url_data}/API/V1/Datos/Mensuales/ESTACION",
        params={
            "Id": station_code,
            "token": token,
            "FechaInicial": FechaInicial,
            "FechaFinal": FechaFinal,
            "DatosCalculados": "true",
        },
        timeout=60,
    )

    if r.status_code != 200:
        return False, {}, {}, {"http_status": r.status_code, "text_head": r.text[:180]}

    try:
        data = r.json().get("datos", [])
    except Exception:
        return False, {}, {}, {"error": "json_parse_error", "text_head": r.text[:180]}

    if not isinstance(data, list) or not data:
        return False, {}, {}, {"error": "no_rows"}

    eto_por_mes = {}
    pe_por_mes = {}
    conteo = {}

    for row in data:
        try:
            mes = int(row.get("Mes"))
        except Exception:
            continue

        if not (mes_inicio <= mes <= mes_fin):
            continue

        eto = row.get("EtPMon")
        pe = row.get("PePMon")

        try:
            eto_v = float(eto) if eto is not None and str(eto).strip() != "" else None
        except Exception:
            eto_v = None
        try:
            pe_v = float(pe) if pe is not None and str(pe).strip() != "" else None
        except Exception:
            pe_v = None

        # Pack completo por fila
        if eto_v is None or pe_v is None:
            continue

        eto_por_mes[mes] = eto_por_mes.get(mes, 0.0) + eto_v
        pe_por_mes[mes] = pe_por_mes.get(mes, 0.0) + pe_v
        conteo[mes] = conteo.get(mes, 0) + 1

    eto_climatologica = {
        mes: round(eto_por_mes[mes] / conteo[mes], 3)
        for mes in eto_por_mes
        if conteo.get(mes, 0) > 0
    }
    pe_climatologica = {
        mes: round(pe_por_mes[mes] / conteo[mes], 3)
        for mes in pe_por_mes
        if conteo.get(mes, 0) > 0
    }

    ok = _is_valid_pack(eto_climatologica, pe_climatologica)
    return ok, eto_climatologica, pe_climatologica, {
        "rows": len(data),
        "months_ok": sorted(list(eto_climatologica.keys())),
    }
# ==========================================================
# Handler Vercel
# ==========================================================
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        _send_json(self, 200, {"ok": True, "route": "GET /api/siar_mensual.py", "mode": "BASE"})

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

            # Estación más cercana (por ahora: una sola; fallback vendrá después)
            candidatas = nearest_stations(lat, lon, n=6)

            # Token SIAR
            token = get_siar_token()

            # Base URL para datos: usa SIAR_BASE_URL si existe, si no el dominio estándar
            base_url_data = os.environ.get("SIAR_BASE_URL") or "https://servicio.mapa.gob.es/siarapi"

            # Elegir modo: BALANCE (ciclo) o DIAGNÓSTICO (fIni)
            has_ciclo = ("cicloIni" in payload) and ("cicloFin" in payload)
            if has_ciclo:
                FechaInicial, FechaFinal, mes_inicio, mes_fin = build_range_from_ciclo(payload)
            else:
                FechaInicial, FechaFinal = build_range_from_fIni(payload)
                mes_inicio, mes_fin = 1, 12

             # ==========================================================
            # Fallback SIAR Mensual (pack completo ETo+Pe)
            # ==========================================================
            estaciones_probadas = []
            pack_ok = False
            eto_climatologica = {}
            pe_climatologica = {}
            estacion_usada = None
            fallback_index = None

            for idx, st in enumerate(candidatas):
                code = st["Codigo"]

                estaciones_probadas.append(
                    {
                        "idx": idx,
                        "Codigo": code,
                        "Estacion": st.get("Estacion"),
                        "dist_km": round(st.get("dist_km", 0.0), 3),
                        "fallbackNote": _fallback_note(idx),
                    }
                )

                ok, eto_tmp, pe_tmp, info = fetch_pack_for_station(
                    base_url_data=base_url_data,
                    token=token,
                    station_code=code,
                    FechaInicial=FechaInicial,
                    FechaFinal=FechaFinal,
                    mes_inicio=mes_inicio,
                    mes_fin=mes_fin,
                )

                estaciones_probadas[-1]["result"] = "ok" if ok else "fail"
                estaciones_probadas[-1]["info"] = info

                if ok:
                    pack_ok = True
                    eto_climatologica = eto_tmp
                    pe_climatologica = pe_tmp
                    estacion_usada = code
                    fallback_index = idx
                    break

            if not pack_ok:
                _send_json(
                    self,
                    200,
                    {
                        "ok": False,
                        "error": "No se pudo obtener un pack completo (EtPMon + PePMon) en ninguna estación (principal + 5 apoyos).",
                        "estacionesProbadas": estaciones_probadas,
                        "FechaInicial": FechaInicial,
                        "FechaFinal": FechaFinal,
                        "mode": "BALANCE" if has_ciclo else "DIAGNOSTICO",
                    },
                )
                return

            _send_json(
                self,
                200,
                {
                    "ok": True,
                    "estacion": estacion_usada,          # compat con frontend
                    "estacionUsada": estacion_usada,
                    "fallbackIndex": fallback_index,
                    "fallbackNote": _fallback_note(fallback_index),
                    "estacionesProbadas": estaciones_probadas,
                    "etoMensual": eto_climatologica,
                    "peMensual": pe_climatologica,
                    "FechaInicial": FechaInicial,
                    "FechaFinal": FechaFinal,
                    "mode": "BALANCE" if has_ciclo else "DIAGNOSTICO",
                },
            )

        except Exception as e:
            _send_json(self, 400, {"ok": False, "error": str(e)})
