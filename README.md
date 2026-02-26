# 🌾 S.I.G. Riego Pro v2.0 (SIAR Edition – RDC Integrated)

> Planificación estacional del riego basada en climatología oficial SIAR y redistribución hidráulica controlada.

---

Sistema de Información Geográfica para la Gestión Integral de Recursos Hídricos, orientado al diseño, planificación y evaluación estacional del riego agrícola mediante:

- Datos agroclimáticos oficiales del Sistema de Información Agroclimática para el Regadío (SIAR – MAPA)
- Integración directa de ETo mensual oficial (EtPMon)
- Precipitación mensual (P) y Precipitación efectiva (PePMon) oficial
- Balance hídrico agronómico mensual
- Redistribución operativa semanal con control hidráulico
- Sistema resiliente de estaciones con fallback secuencial por proximidad geodésica

---

## 🎯 Objetivo del sistema

Proporcionar una estimación robusta, reproducible y auditable de las necesidades hídricas de un cultivo para campañas presentes o futuras.

El modelo se basa en:

- Climatología mensual media derivada de los 3 años completos cerrados anteriores al ciclo (~36 meses efectivos)
- Datos agroclimáticos oficiales validados institucionalmente
- Separación explícita entre:
  - Demanda evaporativa (capa física)
  - Gobernanza hidráulica (capa operativa)

El sistema está diseñado como:

- Referencia técnica inicial para el agricultor
- Herramienta de apoyo al asesor agronómico
- Base justificativa en planificación estacional
- Instrumento de coherencia normativa

---

## 🛰️ 1. Fuente climática oficial: SIAR (MAPA)

### 📡 Sistema de Información Agroclimática para el Regadío

Servicio oficial del Ministerio de Agricultura, Pesca y Alimentación (MAPA) que proporciona:

- Datos agroclimáticos horarios y mensuales
- Evapotranspiración de referencia (ETo) calculada oficialmente
- Precipitación total y precipitación efectiva
- Variables meteorológicas validadas

En este sistema se integran directamente:

- **EtPMon** → Evapotranspiración de referencia mensual
- **PePMon** → Precipitación efectiva mensual
- **Precipitación** → Precipitación total mensual

---

## 📜 Referencia normativa

El uso del SIAR como referencia técnica está recogido en:

**Real Decreto 1051/2022 – Anexo IX**

> “Con carácter general, la dosis y frecuencia de riego se ajustarán a las necesidades del cultivo [...] tomando como referencia [...] el Sistema de Información Agroclimática para el regadío (SiAR) del Ministerio de Agricultura, Pesca y Alimentación…”

El sistema se alinea explícitamente con dicha recomendación normativa.

---

## 📍 2. Selección de estación SIAR

### 📏 Cálculo de distancia geodésica

Se utiliza la fórmula de **Haversine** para calcular la distancia real entre:

- Coordenadas de la parcela introducidas por el usuario
- Todas las estaciones SIAR disponibles

Se establecen:

- 🔵 Estación principal → la más cercana
- 🟢 Hasta 5 estaciones de apoyo → ordenadas por distancia

### 🔁 Fallback por estación (bloque climatológico coherente)

El sistema trabaja con bloque completo por estación:

- EtPMon
- PePMon
- Precipitación

Si la estación principal no devuelve datos válidos en la ventana histórica:

1. Se prueba apoyo #1  
2. Apoyo #2  
3. … hasta apoyo #5  

Se selecciona la primera estación con datos completos.

Esto garantiza:

- Coherencia interna entre variables
- Consistencia climatológica
- Trazabilidad institucional

---

## 📅 3. Ventana temporal histórica

Se utilizan los **3 años completos cerrados anteriores al ciclo**.

Ejemplo:

Ciclo 2026 → se emplean datos 2023–2025.

Se calcula climatología mensual media para los meses activos del ciclo.

---

## 🌡️ 4. Evapotranspiración de Referencia (ET<sub>o</sub>)

En esta versión **no se recalcula ET<sub>o</sub>**.

Se integra directamente:

**EtPMon (SIAR)**

Calculada oficialmente en estaciones agroclimáticas del MAPA.

El sistema asume la metodología oficial SIAR como válida y auditada.

---

## 🌱 5. Balance Hídrico Agronómico

### 🔹 Evapotranspiración del cultivo

ET<sub>c</sub> = ET<sub>o</sub> × K<sub>c</sub>

### 🔹 Precipitación efectiva

Pe = PePMon (SIAR)

No se aplica modelo adicional USDA/SCS.

### 🔹 Precipitación total

P = Precipitación (SIAR)

Se muestra para análisis comparativo, aunque el balance utiliza Pe.

### 🔹 Necesidades Hídricas Netas

NH<sub>n</sub> = (ET<sub>c</sub> − Pe) × 10  

Unidad: m³/ha

---

## 💧 6. Sistema RDC (Redistribución de Dotación por Cultivo)

Ajuste mensual porcentual:

RDC (m³/ha) = NH<sub>n</sub> × (RDC% / 100)

El sistema distingue:

- 🔵 Asignación proporcional
- 🟢 Ajuste RDC mensual
- 🔴 Total mensual resultante

No recalcula SIAR ni ET<sub>o</sub>.

---

## 📅 7. Programación Semanal

### 🔵 Capa física intra-mensual

Dentro de cada mes:

- Se construye la lista de días activos
- Se interpola linealmente ET<sub>o</sub> entre mes actual y siguiente
- Se distribuye el volumen mensual según pesos diarios
- Se conserva exactamente el total mensual

### 🟠 Capa hidráulica (clamp ±10 %)

Para cada semana:

- Mínimo = 0.9 × uniforme
- Máximo = 1.1 × uniforme

Se aplica corrección manteniendo el total mensual exacto.

---

## 🧾 Trazabilidad

El sistema registra:

- Estación utilizada
- Si fue principal o apoyo
- Distancia a parcela
- Ventana histórica empleada
- Valores mensuales oficiales SIAR

Garantiza reproducibilidad determinista del cálculo y permite auditoría técnica externa.

---

## 💻 Stack Tecnológico

- Datos climáticos: SIAR (MAPA)
- Backend: Python (serverless Vercel)
- Frontend: HTML5 + ES6
- Visualización: Chart.js
- Exportación: SheetJS (XLSX)

---

## ⚖ Decisiones de diseño

- Uso exclusivo de fuente oficial agroclimática
- No recalcular ET<sub>o</sub> si ya está institucionalmente calculada
- Separación física / hidráulica
- Resolución mensual coherente con planificación estacional
- Conservación estricta del volumen mensual

---

## 🚫 Limitaciones

- No modela balance dinámico de suelo
- No incorpora eficiencia de aplicación
- No sustituye sensores de humedad
- No captura eventos extremos diarios
- No es modelo de predicción meteorológica

---

# 🔄 Comparativa entre versiones del proyecto

## v1.1 (API Connect – RDC Edition)

- Fuente climática: AEMET OpenData
- Cálculo propio de ET<sub>o</sub> mediante FAO-56 Penman-Monteith
- Fallback por variable (temperatura, HR, viento, radiación)
- Mayor complejidad física interna
- Dependencia de disponibilidad completa de variables

## v2.0 (SIAR Edition – RDC Integrated)

- Fuente climática: SIAR (MAPA)
- Integración directa de ET<sub>o</sub> oficial (EtPMon)
- Fallback por estación (bloque climatológico coherente)
- Simplificación del modelo físico
- Alineación normativa directa (RD 1051/2022)

### Diferencia conceptual clave

- **v1.1** → Modelo físico calculado por el sistema.
- **v2.0** → Modelo climático oficial integrado institucionalmente.

La lógica agronómica de balance y programación semanal se mantiene intacta en ambas versiones.

---
