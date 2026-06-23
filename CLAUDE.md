# SIG Riego Pro (SIAR Edition) — CLAUDE.md

Briefing técnico para arrancar una sesión de trabajo sin contexto previo.

## Qué es esto

SPA de planificación estacional del riego agrícola. Calcula el balance hídrico mensual (ETc − Pe) usando datos oficiales SIAR (MAPA) y distribuye el resultado en programación semanal. Desplegada en Vercel (https://sig-riego-rdc-siar-pm.vercel.app).

Integrable con FertiPRO (https://fertipro.vercel.app) vía la API pública `window.calcularBalanceAPI`.

## Stack

- **Frontend:** HTML5 + ES6 puro, sin framework
- **Gráficas:** Chart.js
- **Exportación:** SheetJS (XLSX)
- **Backend:** Vercel serverless Python en `/api/`
- **Clima:** SIAR MAPA — EtPMon (ETo oficial), PePMon (Pe oficial), P mensual

## Estructura de ficheros

```
index.html               — SPA completa (2322 líneas). Motor de cálculo, UI y API pública
api/
  siar_mensual.py        — proxy SIAR: devuelve ETo, Pe, P mensuales para lat/lon y rango anual
  ping.py                — health check
cultivos.json            — 25 leñosos/perennes en formato mensual_fijo (Kc por mes 1-12)
cultivos_horticolas.json — 40 hortícolas en formato fenologico (Kc_ini/mid/end + fases_pct)
cultivos_sativum.json    — 207 cultivos catálogo Sativum ITACyL (irrigation > 0), formato fenologico,
                           nombres exactos del API, Kc FAO-56 Rev.1 (2025) + fases_pct derivadas de días
                           de fase reales (Lini/Ldev/Lmid/Llate). Grupos: Cereals(24), Forage_legume(11),
                           Forage_mix_legume_grass(27), Forage_non_legume(29), Horticultural(49),
                           Industrial(16), Legumes(2), Mixed(3), Pulses(11), Trees(29), Tubers_roots(6).
                           Excluidos irrigation=0: Sorgo grano, Quinoa, 4 pastizales, Trufa, Barbecho,
                           Yeros grano (9 cultivos). Creado sesión 21 2026-06-23.
estaciones_siar.json     — catálogo de estaciones SIAR con lat/lon (para fallback por proximidad)
vercel.json              — builds: api/*.py (Python) + *.html + *.json (static)
                           PENDIENTE: añadir { "src": "api/*.js", "use": "@vercel/node" } para calcular-riego.js
```

## Formato catálogos Kc

### mensual_fijo (cultivos.json — leñosos actuales)
```json
{ "nombre": "Naranjo", "kc": { "1": 0.6, "2": 0.65, ..., "12": 0.6 } }
```
Sin campo `tipo`. El motor detecta por ausencia de `tipo` que es mensual_fijo.

### fenologico (cultivos_horticolas.json — referencia para cultivos_sativum.json)
```json
{
  "nombre": "Alcachofa",
  "tipo": "fenologico",
  "fases_pct": { "ini": 0.2, "dev": 0.2, "mid": 0.4, "fin": 0.2 },
  "kc": { "ini": 0.7, "mid": 1.05, "fin": 0.85 }
}
```
`fases_pct` debe sumar exactamente 1.0. El motor interpola linealmente entre Kc_ini → Kc_mid → Kc_end.

## API pública — window.calcularBalanceAPI

Función expuesta en `window` desde `index.html` (línea 2224). Permite llamar al motor de cálculo
desde código externo (FertiPRO vía iframe/serverless) sin depender del formulario HTML.

### Contrato (validado en producción con Naranjo, Kc mensual_fijo):

**Request:**
```js
window.calcularBalanceAPI({
  lat:            39.443557,
  lon:           -0.740434,
  cultivo:        "Naranjo",      // nombre exacto del catálogo (normalizar: sin tildes, lowercase)
  fecha_ini:      "2026-03-01",   // ISO 8601
  fecha_fin:      "2026-10-31",
  vol_disponible:  4000            // m³/ha, opcional (default 4000)
})
```

**Response (ok):**
```json
{
  "ok": true,
  "redistribucion_termica": true,
  "programacion_semanal": [
    { "semana": 10, "fecha_ini": "02/03", "fecha_fin": "08/03", "riego_neto_m3ha": 34 }
  ],
  "balance_mensual": [
    { "mes": "mar-26", "dias": 31, "eto_mm_dia": 2.77, "kc": 0.70,
      "etc_mm": 60, "p_mm": 77.5, "pe_mm": 40.9, "nhn_m3ha": 190, "asignado_m3ha": 162 }
  ]
}
```

**Response (error):**
```json
{ "ok": false, "error": "Cultivo \"Trigo\" no encontrado en catálogo. Ejemplos: ..." }
```

### Funcionamiento interno:
- Busca el cultivo en `cultivosData` con `normalizar()` (sin tildes, lowercase, trim)
- Llama `calcularPlanRiego({ skipAemet: true, apiParams: {...} })`
- Modo API salta la lectura del DOM; usa los params directamente
- Llama `POST /api/siar_mensual` para obtener ETo/Pe/P
- Redistribución térmica siempre activa en modo API
- Devuelve JSON estructurado en lugar de renderizar tablas/gráficos

### Limitación actual (sesión 21 — parcialmente resuelta):
`cultivosData` solo contiene cultivos de `cultivos.json` (25 leñosos, nombres distintos de Sativum)
y `cultivos_horticolas.json` (40 hortícolas). Los cultivos Sativum (cereales, leguminosas,
industriales, etc.) y los leñosos con nombre Sativum exacto (Limonero ≠ Limón) NO se encuentran.
`cultivos_sativum.json` ya existe (207 cultivos, creado sesión 21).
**Pendiente: cargarlo en `index.html` en variable separada `cultivosSativumData` (~6 líneas).**

## Plan de integración FertiPRO × sig-riego (sesión 21 — 2026-06-23)

### Arquitectura decidida: serverless HTTP endpoint

```
FertiPRO frontend
  → /api/plan-riego.js  (proxy Node.js en FertiPRO, mismo patrón que sativum-algo.js)
    → /api/calcular-riego.js  (nuevo endpoint Node.js en sig-riego)
      → POST /api/siar_mensual  (Python, ya existente)
      → Kc calculation  (lógica extraída de index.html, puro JS sin DOM)
      → devuelve el JSON del contrato
```

**Ventajas vs iframe+postMessage:** sin complejidad cross-origin, las credenciales SIAR quedan
en las env vars de sig-riego, funciona como cualquier llamada HTTP.

### Cambios en sig-riego (todos aditivos y reversibles):

1. ✅ **`cultivos_sativum.json`** — 207 cultivos Sativum en formato fenologico, nombres exactos
   del API, Kc FAO-56 Rev.1 (2025) Tablas 6.2/6.3, fases_pct derivadas de días reales por fase.
   Sesión 21 2026-06-23.

2. **`api/calcular-riego.js`** (nuevo) — serverless Node.js:
   - Acepta `{ lat, lon, cultivo, fecha_ini, fecha_fin, vol_disponible }`
   - Lee `cultivos.json` + `cultivos_horticolas.json` + `cultivos_sativum.json`
   - Llama internamente a `/api/siar_mensual` para ETo/Pe/P
   - Implementa lógica Kc (extraída de index.html) en Node.js puro
   - Header CORS: `Access-Control-Allow-Origin: https://fertipro.vercel.app`
   - Devuelve el mismo contrato JSON que `window.calcularBalanceAPI`

3. **`index.html`** (~6 líneas) — `Promise.all` añade `cultivos_sativum.json` en variable
   separada `cultivosSativumData`; `calcularBalanceAPI` busca en ambas variables.
   El dropdown de la UI no cambia.

4. **`vercel.json`** — añadir build `{ "src": "api/*.js", "use": "@vercel/node" }`.

### Cambios en FertiPRO (todos aditivos y reversibles):

5. **`api/plan-riego.js`** (nuevo) — proxy Node.js a `https://sig-riego-rdc-siar-pm.vercel.app/api/calcular-riego`.
   Mismo patrón que `api/sigpac-punto.js`.

6. **`src/components/PlanRiegoModal.jsx`** (nuevo) — modal con tabla semanal + botón PDF.
   Usa `cultivo.name` (Sativum), `fechaInicioCiclo/Fin`, `lat/lon` del recinto activo.

7. **`src/App.jsx`** (~15 líneas) — estado `planRiego`, handler `handleObtenerPlanRiego`,
   botón entre `<MedidasMitigacionPanel />` y el footer.

8. **`src/utils/exportPdf.js`** — función nueva `exportarPlanRiegoPdf` (jsPDF ya instalado).
   Tabla: semana | fechas | m³/ha. Cabecera con cultivo, ciclo, estación SIAR usada.

## Flujo ETo en modo serverless (calcular-riego.js)

`siar_mensual.py` recibe `{ lat, lon, anio }` y devuelve climatología mensual media
de los 3 años anteriores. Para el serverless Node.js, hacer `fetch` interno:
```
POST https://sig-riego-rdc-siar-pm.vercel.app/api/siar_mensual
Body: { lat, lon, anio: new Date(fecha_ini).getFullYear() }
```
Mismo endpoint que usa el frontend hoy.

## Cobertura de cultivos (estado sesión 21)

| Fuente JSON             | Cultivos | Formato       | Nombres Sativum |
|-------------------------|----------|---------------|-----------------|
| cultivos.json           | 25       | mensual_fijo  | ⚠️ Parcial (Naranjo ✓, Limonero ✗) |
| cultivos_horticolas.json| 40       | fenologico    | ✓ Mayoría cubre |
| cultivos_sativum.json   | 207      | fenologico    | ✅ Creado sesión 21 |

**Total catálogo Sativum:** 216 cultivos en 13 grupos (207 con irrigation > 0 → incluidos).
9 excluidos por irrigation = 0: Sorgo grano, Quinoa, 4 pastizales, Trufa, Barbecho blanco, Yeros.
Pendiente wiring: cargar en index.html + calcular-riego.js.

## FAO-56 Rev.1 (2025) — valores Kc de referencia

- Tabla 6.2 (herbáceos): Trigo 0.70/1.15/0.25, Cebada 0.30/1.10/0.25, Maíz 0.30/1.20/0.50,
  Girasol 0.35/1.15/0.30, Remolacha azucarera 0.35/1.10/0.75, Soja 0.40/1.10/0.50,
  Algodón 0.40/1.10/0.50, Patata 0.50/1.15/0.75
- Tabla 6.3 (leñosos): Olivo intensivo 0.50/0.60/0.60, Cítricos medio 0.70/0.75/0.75,
  Aguacate 0.80/0.85/0.85, Manzano/Peral 0.45/0.95/0.60, Cerezo 0.50/0.85/0.70,
  Melocotonero 0.45/0.95/0.60, Albaricoquero/Ciruelo 0.50/1.00/0.55,
  Higuera 0.40/0.80/0.40, Granado 0.45/0.70/0.45, Caqui 0.35/0.90/0.50,
  Vid (uva vino) 0.30/0.85/0.45, Almendro 0.40/0.90/0.65

## Comandos de desarrollo

```powershell
cd C:\work\sig-riego-rdc-siar-pm
npx vercel dev     # con serverless Python (requiere vercel login vigente)
# No tiene npm run dev — es HTML estático + Python serverless
git add .; git commit -m "..."; git push   # despliegue automático a Vercel
```

**Nota PowerShell:** usar `;` como separador, no `&&`.

## ⚠ Regla de cierre de sesión

Igual que FertiPRO: Vercel despliega desde git. Siempre `git status` + commit antes de cerrar sesión.
