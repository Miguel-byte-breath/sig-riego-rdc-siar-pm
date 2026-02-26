🌾 S.I.G. Riego Pro v2.0 (SIAR Edition – RDC Integrated)

Sistema de Información Geográfica para la Gestión Integral de Recursos Hídricos, orientado al diseño, planificación y evaluación estacional del riego agrícola mediante:

Datos agroclimáticos oficiales del Sistema de Información Agroclimática para el Regadío (SIAR) – MAPA

Integración directa de ETo mensual (EtPMon) oficial

Precipitación mensual (P) y Precipitación efectiva (PePMon) oficial

Balance hídrico agronómico mensual

Redistribución operativa semanal con control hidráulico

Sistema resiliente de estaciones con fallback completo por proximidad

🎯 Objetivo del sistema

Proporcionar una estimación robusta, reproducible y auditable de las necesidades hídricas de un cultivo para campañas presentes o futuras, basada en:

Series históricas oficiales (~36 meses efectivos SIAR)

Datos agroclimáticos validados institucionalmente

Separación explícita entre:

Demanda evaporativa (capa física)

Gobernanza hidráulica (capa operativa)

El sistema está diseñado para servir como:

Referencia técnica inicial para el agricultor

Herramienta de apoyo al asesor agronómico

Base justificativa en planificación estacional

Instrumento de coherencia normativa

🛰️ 1. Fuente climática oficial: SIAR (MAPA)
📡 Sistema de Información Agroclimática para el Regadío (SIAR)

El SIAR es el servicio oficial del Ministerio de Agricultura, Pesca y Alimentación (MAPA) que proporciona:

Datos agroclimáticos horarios y mensuales

Evapotranspiración de referencia (ETo) calculada oficialmente

Precipitación total y precipitación efectiva

Variables meteorológicas validadas

En este sistema se integran directamente:

EtPMon → Evapotranspiración de referencia mensual

PePMon → Precipitación efectiva mensual

Precipitacion → Precipitación total mensual

📜 Referencia normativa

El uso del SIAR como referencia técnica está expresamente recogido en:

Real Decreto 1051/2022 – Anexo IX, donde se establece:

“Con carácter general, la dosis y frecuencia de riego se ajustarán a las necesidades del cultivo y se acomodarán a la capacidad de retención de humedad del suelo para evitar la pérdida de nutrientes por lixiviación, tomando como referencia las recomendaciones de los servicios de asesoramiento al regante de la comunidad autónoma o el Sistema de Información Agroclimática para el regadío (SiAR) del Ministerio de Agricultura, Pesca y Alimentación…”

Este sistema se alinea explícitamente con dicha recomendación normativa.

📍 2. Selección de estación SIAR
📏 Cálculo de distancia real

Se utiliza la fórmula de Haversine para calcular la distancia geodésica entre:

Coordenadas de parcela introducidas por el usuario

Todas las estaciones SIAR disponibles

Se establece:

🔵 Estación principal → la más cercana

🟢 Hasta 5 estaciones de apoyo → ordenadas por distancia

🔁 Fallback por estación (pack completo)

A diferencia del modelo anterior por variable:

El sistema actual trabaja con pack completo por estación:

EtPMon

PePMon

Precipitacion

Si la estación principal no devuelve datos válidos en la ventana histórica:

→ Se prueba apoyo #1
→ apoyo #2
→ … hasta apoyo #5

Se selecciona la primera estación que devuelva datos completos.

Esto garantiza:

Coherencia interna entre variables

Trazabilidad institucional

Consistencia climatológica

📅 3. Ventana temporal histórica

Se utilizan los 3 años completos cerrados anteriores al ciclo.

Ejemplo:

Ciclo 2026 → se usan datos 2023–2025.

Ventana típica: 36 meses efectivos.

Se calcula climatología mensual promedio para los meses del ciclo.

🌡️ 4. Evapotranspiración de Referencia (ET<sub>o</sub>)
📌 Método

En esta versión no se recalcula ET<sub>o</sub>.

Se integra directamente:

EtPMon (SIAR)

Calculada oficialmente en estaciones agroclimáticas del MAPA.

El sistema asume la metodología oficial SIAR como válida y auditada.

🌱 5. Balance Hídrico Agronómico
🔹 Evapotranspiración del cultivo

ET<sub>c</sub> = ET<sub>o</sub> × K<sub>c</sub>

🔹 Precipitación efectiva

Se integra directamente:

Pe = PePMon (SIAR)

Sin aplicar modelo USDA/SCS adicional.

🔹 Precipitación total

Se integra:

P = Precipitacion (SIAR)

Se muestra para análisis comparativo, aunque el balance utiliza Pe.

🔹 Necesidades Hídricas Netas

NH<sub>n</sub> = (ET<sub>c</sub> − Pe) × 10

Unidad: m³/ha

💧 6. Sistema RDC (Redistribución de Dotación por Cultivo)
🎛 Ajuste mensual porcentual

Para cada mes:

RDC (m³/ha) = NH<sub>n</sub> × (RDC% / 100)

El sistema distingue:

🔵 Asignación proporcional

🟢 Ajuste RDC mensual

🔴 Total mensual resultante

No recalcula SIAR ni ET<sub>o</sub>.

📅 7. Programación Semanal
🔵 Capa física intra-mensual

Dentro de cada mes:

Se construye la lista de días activos.

Se interpola ETo entre mes actual y siguiente.

Se distribuye el volumen mensual según pesos diarios.

Se conserva exactamente el total mensual.

🟠 Capa hidráulica (clamp ±10 %)

Para cada semana:

Mínimo = 0.9 × uniforme
Máximo = 1.1 × uniforme

Se aplica corrección manteniendo el total mensual exacto.

🧾 Trazabilidad

El sistema registra:

Estación utilizada

Si fue principal o apoyo

Distancia a parcela

Ventana histórica empleada

Valores mensuales oficiales SIAR

Permite auditoría técnica y validación externa.

💻 Stack Tecnológico

Datos climáticos: SIAR (MAPA)

Backend: Python (serverless Vercel)

Frontend: HTML5 + ES6

Visualización: Chart.js

Exportación: SheetJS (XLSX)

⚖ Decisiones de diseño

Uso exclusivo de fuente oficial agroclimática.

No recalcular ET<sub>o</sub> si ya está institucionalmente calculada.

Separación física / hidráulica.

Resolución mensual coherente con planificación estacional.

Conservación estricta del volumen mensual.

🚫 Limitaciones

No modela balance dinámico de suelo.

No incorpora eficiencia de aplicación.

No sustituye sensores de humedad.

No captura eventos extremos diarios.

No es modelo de predicción meteorológica.

📌 Filosofía del sistema

Referencia institucional + modelo agronómico coherente.
Transparencia, trazabilidad y alineación normativa.
Herramienta técnica para planificación estacional real.
