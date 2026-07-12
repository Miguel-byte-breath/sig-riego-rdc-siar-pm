// api/calcular-riego.js
// Endpoint serverless Node.js — motor de riego para integración FertiPRO × SIG Riego Pro
//
// POST /api/calcular-riego
// Body: { lat, lon, cultivo, fecha_ini, fecha_fin, vol_disponible? }
//   cultivo: nombre exacto del catálogo Sativum (e.g. "Patata de consumo")
//   fecha_ini / fecha_fin: ISO 8601 "YYYY-MM-DD"
//   vol_disponible: m³/ha (default 4000)
//
// Response: { ok, cultivo, redistribucion_termica, programacion_semanal[], balance_mensual[] }

'use strict';

const { readFile } = require('fs/promises');
const { join }     = require('path');

// ─── Helpers (portados de index.html) ────────────────────────────────────────

function normalizar(str) {
  return (str || '').toLowerCase()
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .trim();
}

function daysBetweenInclusive(d1, d2) {
  return Math.round((d2 - d1) / 86400000) + 1;
}

function addDays(d, n) {
  const r = new Date(d);
  r.setDate(r.getDate() + n);
  return r;
}

function toISODate(d) {
  return d.toISOString().split('T')[0];
}

function lerp(a, b, t) {
  return a + (b - a) * t;
}

// ─── Curva Kc fenológica (idéntico a index.html::buildKcCurveForCycle) ───────

function buildKcCurveForCycle(cultivo, fIni, fFin) {
  if (!cultivo || cultivo.tipo !== 'fenologico') return [];

  const totalDias = daysBetweenInclusive(fIni, fFin);
  if (!Number.isFinite(totalDias) || totalDias <= 0) return [];

  const pct = cultivo.fases_pct || {};
  let diasIni = Math.round(totalDias * (pct.ini || 0));
  let diasDev = Math.round(totalDias * (pct.dev || 0));
  let diasMid = Math.round(totalDias * (pct.mid || 0));
  let diasFin = Math.round(totalDias * (pct.fin || 0));

  // El residuo por redondeo va a diasMid
  diasMid += totalDias - (diasIni + diasDev + diasMid + diasFin);
  diasIni = Math.max(0, diasIni);
  diasDev = Math.max(0, diasDev);
  diasMid = Math.max(0, diasMid);
  diasFin = Math.max(0, diasFin);

  const kcIni = Number(cultivo.kc?.ini || 0);
  const kcMid = Number(cultivo.kc?.mid || 0);
  const kcFin = Number(cultivo.kc?.fin || 0);

  const curva = [];
  let idx = 0;

  for (let i = 0; i < diasIni; i++, idx++)
    curva.push({ fecha: toISODate(addDays(fIni, idx)), kc: kcIni });

  for (let i = 0; i < diasDev; i++, idx++) {
    const t = diasDev <= 1 ? 1 : i / (diasDev - 1);
    curva.push({ fecha: toISODate(addDays(fIni, idx)), kc: lerp(kcIni, kcMid, t) });
  }

  for (let i = 0; i < diasMid; i++, idx++)
    curva.push({ fecha: toISODate(addDays(fIni, idx)), kc: kcMid });

  for (let i = 0; i < diasFin; i++, idx++) {
    const t = diasFin <= 1 ? 1 : i / (diasFin - 1);
    curva.push({ fecha: toISODate(addDays(fIni, idx)), kc: lerp(kcMid, kcFin, t) });
  }

  // trim / pad
  if (curva.length > totalDias) curva.length = totalDias;
  while (curva.length < totalDias)
    curva.push({ fecha: toISODate(addDays(fIni, curva.length)), kc: kcFin });

  return curva;
}

// Kc medio del mes (idéntico a index.html::getKcMensualParaMes)
function getKcMensual(cultivo, year, month, fIni, fFin) {
  if (!cultivo) return 0;

  if (cultivo.tipo === 'mensual_fijo') {
    // kc es { "1": 0.6, "2": 0.65, ... }
    return Number(cultivo.kc?.[String(month)] || cultivo.kc?.[month] || 0);
  }

  if (cultivo.tipo !== 'fenologico') return 0;

  const curva = buildKcCurveForCycle(cultivo, fIni, fFin);
  const vals = curva
    .filter(d => {
      const dt = new Date(d.fecha);
      return dt.getFullYear() === year && (dt.getMonth() + 1) === month;
    })
    .map(d => d.kc);

  return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0;
}

// ─── Número de semana ISO (idéntico a index.html::getWeekNumber) ─────────────

function getWeekNumber(d) {
  d = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  d.setUTCDate(d.getUTCDate() + 4 - (d.getUTCDay() || 7));
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  return Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
}

function formatDate(d) {
  return `${d.getDate().toString().padStart(2, '0')}/${(d.getMonth() + 1).toString().padStart(2, '0')}`;
}

// ─── Programación semanal con redistribución térmica ─────────────────────────
// Portado de index.html::calcularSemanasCorrelativas con redistribucionTermica=true

function calcularSemanasCorrelativas(mesesCiclo, fIni, fFin) {
  const mapaDiario = {};

  mesesCiclo.forEach(m => {
    const m3MesBase = Number(m.m3RdcAgro != null ? m.m3RdcAgro : (m.m3AsignadoFinal || 0));

    // Rango de días activos del mes dentro del ciclo
    let dIter = new Date(m.anio, m.mesNum - 1, 1);
    const dFinMes = new Date(m.anio, m.mesNum, 0);
    if (dIter < fIni) dIter = new Date(fIni);
    const limite = dFinMes > fFin ? new Date(fFin) : dFinMes;

    const dias = [];
    let tmp = new Date(dIter);
    while (tmp <= limite) { dias.push(new Date(tmp)); tmp.setDate(tmp.getDate() + 1); }
    if (!dias.length) return;

    // Pesos térmicos: ETo interpolado lineal entre mes actual y siguiente
    const etoMes = Number(m.etoDiaria || 0);
    const mSig = mesesCiclo.find(x =>
      x.anio === (m.mesNum === 12 ? m.anio + 1 : m.anio) &&
      x.mesNum === (m.mesNum === 12 ? 1 : m.mesNum + 1)
    );
    const etoSig = mSig ? Number(mSig.etoDiaria || etoMes) : etoMes;
    const diasEnMes = (new Date(m.anio, m.mesNum, 0)).getDate();

    const pesos = dias.map(d => {
      const t = diasEnMes > 1 ? (d.getDate() - 1) / (diasEnMes - 1) : 0;
      return Math.max(0.0001, etoMes + (etoSig - etoMes) * t);
    });

    const sumW = pesos.reduce((a, b) => a + b, 0);
    const m3PorDia = pesos.map(p => m3MesBase * (p / sumW));

    // Agrupación semanal + clamp ±20% respecto al uniforme
    const semanasMes = {};
    for (let k = 0; k < dias.length; k++) {
      const key = `S${getWeekNumber(dias[k])}-${dias[k].getFullYear()}`;
      if (!semanasMes[key]) semanasMes[key] = { dias: 0, val: 0 };
      semanasMes[key].dias += 1;
      semanasMes[key].val  += m3PorDia[k];
    }

    const keys = Object.keys(semanasMes);
    const totalDias = dias.length;
    const minMax = {};
    let sumaClamped = 0;

    keys.forEach(key => {
      const diasSem = semanasMes[key].dias;
      const uniforme = m3MesBase * (diasSem / totalDias);
      const minV = 0.8 * uniforme, maxV = 1.2 * uniforme;
      const val = Math.max(minV, Math.min(maxV, semanasMes[key].val));
      semanasMes[key].val = val;
      minMax[key] = { minV, maxV };
      sumaClamped += val;
    });

    // Reequilibrar residuo manteniendo total mensual
    let residuo = m3MesBase - sumaClamped;
    const ajustar = signo => {
      for (const key of keys) {
        if (Math.abs(residuo) < 1e-6) break;
        const mm = minMax[key];
        const val = semanasMes[key].val;
        const margen = signo > 0 ? mm.maxV - val : val - mm.minV;
        if (margen <= 1e-9) continue;
        const delta = Math.min(Math.abs(residuo), margen) * signo;
        semanasMes[key].val = val + delta;
        residuo -= delta;
      }
    };
    if (residuo > 0) ajustar(+1);
    if (residuo < 0) ajustar(-1);
    if (Math.abs(residuo) > 1e-4) semanasMes[keys[keys.length - 1]].val += residuo;

    // Distribuir de vuelta a días (uniforme dentro de cada semana)
    const porKey = {};
    keys.forEach(key => { porKey[key] = semanasMes[key].val / semanasMes[key].dias; });
    for (let k = 0; k < dias.length; k++) {
      const key = `S${getWeekNumber(dias[k])}-${dias[k].getFullYear()}`;
      mapaDiario[dias[k].toISOString().split('T')[0]] = porKey[key];
    }
  });

  // Agrupar por semana correlativa (ordenado cronológicamente)
  const semanasData = {};
  let iter = new Date(fIni);
  while (iter <= fFin) {
    const key = `S${getWeekNumber(iter)}-${iter.getFullYear()}`;
    const diaStr = iter.toISOString().split('T')[0];
    if (!semanasData[key]) {
      semanasData[key] = { num: getWeekNumber(iter), suma: 0, inicio: new Date(iter), fin: new Date(iter) };
    }
    semanasData[key].suma += (mapaDiario[diaStr] || 0);
    semanasData[key].fin = new Date(iter);
    iter.setDate(iter.getDate() + 1);
  }

  return Object.values(semanasData)
    .sort((a, b) => a.inicio - b.inicio)
    .map(s => ({
      semana:          s.num,
      fecha_ini:       formatDate(s.inicio),
      fecha_fin:       formatDate(s.fin),
      riego_neto_m3ha: Math.round(s.suma),
    }));
}

// ─── Handler ─────────────────────────────────────────────────────────────────

module.exports = async function handler(req, res) {
  // CORS — abierto: sin cookies/credenciales, endpoint ya público (sin API key).
  // Cualquier origen puede llamarlo desde el navegador sin coordinación previa.
  res.setHeader('Access-Control-Allow-Origin',  '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'POST')
    return res.status(405).json({ ok: false, error: 'Método no permitido. Usa POST.' });

  const { lat, lon, cultivo, fecha_ini, fecha_fin, vol_disponible = 4000, origen } = req.body || {};

  if (lat == null || lon == null || !cultivo || !fecha_ini || !fecha_fin) {
    return res.status(400).json({
      ok: false,
      error: 'Parámetros requeridos: lat, lon, cultivo, fecha_ini, fecha_fin',
    });
  }

  try {
    // ── 1. Cargar catálogos ────────────────────────────────────────────────
    // Dos "gemelos digitales" comparten este endpoint: FertiPRO (motor propio,
    // catálogo canónico VisualNacert) y fertipro-api-sativum (catálogo Sativum
    // ITACyL). `origen` ('fertipro'|'sativum') indica cuál llama, para no
    // buscar en el catálogo del otro — evita que un cambio en un catálogo
    // rompa silenciosamente al otro gemelo. Si `origen` no viene (llamadas
    // antiguas), se mantiene el comportamiento combinado de siempre.
    const root = join(__dirname, '..');

    async function loadJsonSafe(filename) {
      try {
        return JSON.parse(await readFile(join(root, filename), 'utf8'));
      } catch (err) {
        // Aviso permanente de bajo coste: antes de la sesión 2026-07-12 un fichero no
        // encontrado se tragaba en silencio (sin dejar rastro en los logs de Vercel),
        // lo que costó una sesión entera de diagnóstico cuando el bundling del Lambda
        // dejó de incluir estos JSON. Con esto, una futura regresión similar se ve
        // directamente en Vercel → Observability → Functions → Logs.
        console.error(`[calcular-riego] ${filename}: no se pudo cargar (${err.code || 'error'})`, err.message);
        if (err.code === 'ENOENT') return []; // fichero todavía no creado (categoría pendiente)
        throw err;
      }
    }

    const [rawFrutales, rawHorticolas, rawLeguminosas, rawExtensivos, rawSativum] = await Promise.all([
      loadJsonSafe('cultivos_frutales.json'),
      loadJsonSafe('cultivos_horticolas.json'),
      loadJsonSafe('cultivos_leguminosas.json'),
      loadJsonSafe('cultivos_extensivos.json'),
      loadJsonSafe('cultivos_sativum.json'),
    ]);

    // Frutales (leñosos): igual que antes, mensual_fijo por defecto — pero
    // sin pisar el `tipo` de entradas que ya lo traen propio (ej. las
    // variantes fenológicas copiadas de Sativum, como Viña vinificación).
    const frutales    = rawFrutales.map(c => ({ tipo: 'mensual_fijo', ...c }));
    const horticolas  = rawHorticolas;   // ya tienen tipo:'fenologico'
    const leguminosas = rawLeguminosas;  // ya tienen tipo:'fenologico'
    const extensivos  = rawExtensivos;   // ya tienen tipo:'fenologico' — incluidas las forrajeras
                                          // plurianuales de heno (Alfalfa, Dactilo, Trifolium, etc.),
                                          // que reutilizan este mismo formato con una única "mid" larga
                                          // que absorbe internamente los cortes/rebrotes del ciclo,
                                          // en vez de un motor de corte dedicado (decisión 2026-07-11,
                                          // ver CLAUDE.md)
    const sativum     = rawSativum;      // ya tienen tipo:'fenologico'

    const catalogoFertipro = [...frutales, ...horticolas, ...leguminosas, ...extensivos];
    const catalogoSativum  = sativum;

    let todosCultivos;
    if (origen === 'sativum')       todosCultivos = catalogoSativum;
    else if (origen === 'fertipro') todosCultivos = catalogoFertipro;
    else                             todosCultivos = [...catalogoFertipro, ...catalogoSativum]; // compatibilidad hacia atrás

    // ── 2. Buscar cultivo (normalizado) ────────────────────────────────────
    const cultivoObj = todosCultivos.find(c => normalizar(c.nombre) === normalizar(cultivo));
    if (!cultivoObj) {
      const ejemplos = todosCultivos.map(c => c.nombre).slice(0, 8).join(', ');
      return res.status(404).json({
        ok: false,
        error: `Cultivo "${cultivo}" no encontrado${origen ? ` en el catálogo ${origen}` : ''}. Ejemplos: ${ejemplos}`,
      });
    }

    // ── 3. Llamar a siar_mensual ───────────────────────────────────────────
    const siarResp = await fetch(
      'https://sig-riego-rdc-siar-pm.vercel.app/api/siar_mensual',
      {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ lat, lon, cicloIni: fecha_ini, cicloFin: fecha_fin }),
      }
    );

    const siarText = await siarResp.text();
    let dataSiar;
    try { dataSiar = JSON.parse(siarText); }
    catch {
      return res.status(502).json({
        ok: false,
        error: `SIAR no devolvió JSON (HTTP ${siarResp.status}): ${siarText.slice(0, 200)}`,
      });
    }

    if (!siarResp.ok || !dataSiar.ok) {
      return res.status(502).json({
        ok: false,
        error: `SIAR error (HTTP ${siarResp.status}): ${dataSiar?.error || siarText.slice(0, 200)}`,
      });
    }

    const { etoMensual, peMensual, pMensual, estacionPorMes = {} } = dataSiar;
    const volV = Number(vol_disponible) || 4000;

    // ── 4. Bucle mensual ───────────────────────────────────────────────────
    const fIni = new Date(fecha_ini);
    const fFin = new Date(fecha_fin);
    const MESES = ['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'];

    const mesesCiclo = [];
    let sumaNHn = 0;
    let iter = new Date(fIni.getFullYear(), fIni.getMonth(), 1);

    while (iter <= fFin) {
      const mIdx = iter.getMonth();
      const anio = iter.getFullYear();
      const mesNum = mIdx + 1;
      const diasMesTotal = new Date(anio, mIdx + 1, 0).getDate();

      const rIni = new Date(Math.max(iter.getTime(), fIni.getTime()));
      const rFin = new Date(Math.min(new Date(anio, mIdx, diasMesTotal).getTime(), fFin.getTime()));
      const nDias = Math.max(0, Math.round((rFin - rIni) / 86400000) + 1);

      if (nDias > 0) {
        const etoDiaria   = etoMensual[mesNum] ? etoMensual[mesNum] / diasMesTotal : 0;
        const kc          = getKcMensual(cultivoObj, anio, mesNum, fIni, fFin);
        const etcMes      = etoDiaria * kc * nDias;

        const peMes       = peMensual[mesNum] || peMensual[String(mesNum)] || 0;
        const peActiva    = (peMes / diasMesTotal) * nDias;

        const pMes        = Number(pMensual?.[mesNum] ?? pMensual?.[String(mesNum)] ?? 0);
        const pActiva     = (pMes / diasMesTotal) * nDias;

        const nhn_m3      = Math.max(0, etcMes - peActiva) * 10;
        sumaNHn          += nhn_m3;

        mesesCiclo.push({
          etiqueta:    `${MESES[mIdx]}-${String(anio).slice(-2)}`,
          mesNum,
          anio,
          diasActivos: nDias,
          etoDiaria,
          kc:          Math.round(kc * 100) / 100,
          etcMm:       etcMes,
          pMm:         pActiva,
          peMm:        peActiva,
          nhn_m3,
          m3RdcAgro:   null,   // se asigna abajo
          m3AsignadoFinal: null,
        });
      }

      iter.setMonth(iter.getMonth() + 1);
    }

    // ── 5. Asignación proporcional por volumen disponible ─────────────────
    const balanceMensual = mesesCiclo.map(m => {
      const m3Asig = sumaNHn > 0 ? (m.nhn_m3 / sumaNHn) * volV : 0;
      m.m3AsignadoFinal = m3Asig;
      m.m3RdcAgro       = m3Asig;   // sin ajuste RDC en esta integración
      // estacionPorMes tiene claves integer en Python → strings en JSON; ambos funcionan en JS
      const stInfo = estacionPorMes[m.mesNum] || estacionPorMes[String(m.mesNum)] || null;
      return {
        mes:          m.etiqueta,
        dias:         m.diasActivos,
        eto_mm_dia:   Math.round(m.etoDiaria * 100) / 100,
        kc:           m.kc,
        etc_mm:       Math.round(m.etcMm * 10) / 10,
        p_mm:         Math.round(m.pMm * 10) / 10,
        pe_mm:        Math.round(m.peMm * 10) / 10,
        nhn_m3ha:     Math.round(m.nhn_m3),
        asignado_m3ha: Math.round(m3Asig),
        estacion:     stInfo?.nombre || null,
        anios_datos:  stInfo?.anios ?? null,
      };
    });

    // ── 6. Programación semanal (redistribución térmica) ──────────────────
    const programacionSemanal = calcularSemanasCorrelativas(mesesCiclo, fIni, fFin);

    // Estación de display: nombre único si todas las filas usan la misma; null si mosaico
    const stationNames = [...new Set(Object.values(estacionPorMes).map(s => s.nombre).filter(Boolean))];
    const estacionDisplay = stationNames.length === 1 ? stationNames[0] : null;

    return res.status(200).json({
      ok:                    true,
      cultivo:               cultivoObj.nombre,
      estacion:              estacionDisplay,
      redistribucion_termica: true,
      programacion_semanal:  programacionSemanal,
      balance_mensual:       balanceMensual,
      meses_sin_datos:       dataSiar.mesesSinDatos || [],
    });

  } catch (err) {
    console.error('[calcular-riego]', err);
    return res.status(500).json({ ok: false, error: err.message });
  }
};
