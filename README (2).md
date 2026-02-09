# 🌾 S.I.G. Riego Pro v1.0 (API Connect)

**Sistema de Información Geográfica para la Gestión Integral de Recursos Hídricos**, orientado al diseño y planificación del riego agrícola mediante **climatología histórica real** y **cálculo agronómico riguroso**.

La aplicación automatiza el **balance hídrico mensual y semanal** conectando de forma directa, resiliente y trazable con los servicios de **AEMET OpenData**.

---

## 🎯 Objetivo del sistema

Proporcionar una **estimación robusta y reproducible** de las necesidades hídricas de un cultivo, incluso para **ciclos futuros**, combinando:

- Climatología histórica real.
- Evapotranspiración de referencia **FAO-56 Penman–Monteith**.
- Reglas agronómicas explícitas y auditables.
- Priorización inteligente de estaciones meteorológicas.

---

## 📍 Selección y validación de estaciones (Sección 1)

### 📏 Cálculo de distancias
A partir de la latitud y longitud de la parcela, el sistema calcula la **distancia geográfica real (Haversine)** a todas las estaciones AEMET disponibles.

- Se selecciona una **estación principal** (la más cercana).
- Se identifican hasta **5 estaciones de apoyo**, ordenadas por distancia.
- Las distancias se muestran redondeadas con fines informativos.

---

### 🧪 Diagnóstico de cobertura de datos

Para cada estación candidata se analiza la **cobertura real de datos mensuales** por variable climática:

- Temperatura
- Humedad relativa
- Viento
- Radiación (global / insolación)

Ejemplo de lectura:

Cobertura 39/39
Significa:
> La estación tiene datos válidos en **todos los meses disponibles** del histórico devuelto por AEMET  
> (AEMET puede devolver 36, 37, 38 o 39 meses según disponibilidad real).

📌 **No se fuerza nunca a “36 exactos”**: se usa el histórico efectivo real.

---

## 🛰️ Motor climático histórico (Sección 2)

### 📅 Ventana temporal
El sistema trabaja con los **últimos 3 años naturales completos**, típicamente:

- Año N-2
- Año N-1
- Año N (último completo disponible)

Resultado habitual: **36 a 39 meses reales**.

---

### 🧩 Fallback inteligente por variable (no por estación)

Cada variable climática se resuelve **mensualmente** siguiendo esta prioridad:

1. **Estación principal** (más cercana).
2. Hasta **5 estaciones de apoyo**, por orden de distancia.
3. Se registra **qué estación aportó cada variable y cada mes** (trazabilidad).

Esto evita descartar meses completos por el fallo de una sola variable.

---

### 📐 Tratamiento de datos ausentes
- Valores no numéricos o erróneos se descartan.
- Las medias mensuales se calculan **dividiendo solo por registros válidos**.
- El sistema **nunca inventa datos** ni detiene el cálculo por huecos parciales.

---

## 🌡️ Evapotranspiración de referencia — FAO-56

La **Evapotranspiración de referencia ($ET_o$)** se calcula mediante el método **FAO-56 Penman–Monteith**, usando un día representativo mensual.

Variables utilizadas:
- Temperatura media, máxima y mínima
- Humedad relativa media
- Viento ajustado a 2 m ($u_2$)
- Radiación solar ($R_s$)
- Latitud y altitud de la estación principal

📌 El método **no se modifica** ni se simplifica.

---

## 🌱 Balance hídrico agronómico

### 🔹 Evapotranspiración del cultivo ($ET_c$)
\[
ET_c = ET_o \cdot K_c
\]

Donde $K_c$ depende del cultivo y del mes fenológico.

---

### 🔹 Precipitación mensual ($P$)

- Se obtiene de **AEMET (p_mes)**.
- Se calcula como **media mensual histórica** por mes natural.
- Es **independiente** de la disponibilidad de otras variables climáticas.

---

### 🔹 Precipitación Efectiva ($P_e$)

**Precipitación Efectiva ($P_e$):**  
Se calcula mediante una formulación tipo **USDA / SCS**, aplicada a la precipitación mensual media y posteriormente prorrateada si el mes es parcial.

Ejemplo conceptual:
- Mes completo → se usa $P_e$ mensual total.
- Mes parcial → $P_e$ proporcional a los días activos.

---

### 🔹 Necesidades Hídricas Netas ($NH_n$)

\[
NH_n = (ET_c - P_e) \cdot 10
\]

Resultado expresado en **$m^3/ha$**.

---

## 📅 Programación semanal (Sección 3)

- Distribución diaria del riego neto.
- Agregación por **semanas naturales ISO**.
- Visualización mediante gráfico dinámico.
- Exportación a Excel para uso operativo.

---

## 📊 Visualización y exportación

- Gráficos comparativos:
  - Precipitación efectiva
  - Necesidades netas
  - Asignación ajustada
- Exportación profesional a **Excel (.xlsx)**:
  - Balance mensual
  - Programación semanal

---

## 🧾 Trazabilidad y transparencia

El sistema mantiene un registro interno que indica:
- Qué estación aportó cada variable.
- Para qué mes.
- Bajo qué condición (principal / apoyo).

Esto permite **auditoría técnica** y validación externa (SIAR, estudios de riego, etc.).

---

## 💻 Stack tecnológico

- **Datos climáticos:** AEMET OpenData (REST)
- **Frontend:** HTML5 + Vanilla JavaScript (ES6)
- **Visualización:** Chart.js, chartjs-plugin-datalabels
- **Exportación:** SheetJS (XLSX)

---

## ⚙️ Configuración

Para ejecutar el sistema es necesaria una **API Key válida de AEMET**:

```js
const API_KEY = "TU_AEMET_API_KEY";

---

## 🧠 Decisiones de diseño y limitaciones del modelo

Este sistema ha sido diseñado con un enfoque **agrónomo-práctico**, priorizando la **robustez**, la **trazabilidad** y la **interpretabilidad** frente a soluciones “caja negra”. A continuación se explicitan las principales decisiones adoptadas y sus implicaciones.

---

### 🔹 Uso de climatología histórica (no predicción meteorológica)

- El modelo **no realiza predicción meteorológica**.
- Se basa en la **climatología histórica real** (≈36–39 meses AEMET) para construir un **mes climático típico**.
- Esta aproximación es adecuada para:
  - diseño de riego,
  - planificación de dotaciones,
  - estudios comparativos,
  - escenarios de campaña futura.

📌 No pretende sustituir a modelos de predicción diaria a corto plazo.

---

### 🔹 Proyección de ciclos futuros

- El ciclo de cultivo (fechas introducidas por el usuario) puede pertenecer a **años futuros**.
- La climatología histórica se **proyecta por mes natural** (marzo → marzo, etc.).
- No se usan datos AEMET “del futuro” ni extrapolaciones temporales.

Esta separación evita inconsistencias temporales y permite reproducibilidad.

---

### 🔹 Priorización por variable, no por estación única

- No se fuerza una estación “perfecta”.
- Cada variable climática (T, HR, viento, radiación) puede proceder de **estaciones distintas**, priorizando:
  1. estación más cercana,
  2. estaciones de apoyo por distancia.
- Este enfoque reduce pérdidas de información por fallos parciales de estaciones.

📌 La trazabilidad por mes y variable permite auditar esta decisión.

---

### 🔹 Tratamiento de precipitación

- La **precipitación mensual ($P$)** se calcula **independientemente** del resto de variables.
- No se descarta un mes por ausencia de HR, viento o temperatura.
- La **Precipitación Efectiva ($P_e$)** se calcula a partir de $P$ mediante una formulación tipo USDA/SCS y se prorratea en meses parciales.

Esto evita infraestimar sistemáticamente la lluvia en estaciones con fallos climáticos parciales.

---

### 🔹 Resolución temporal mensual

- El cálculo se realiza a escala **mensual**, usando un **día representativo** para $ET_o$.
- No se capturan extremos diarios (olas de calor, tormentas intensas).
- La programación semanal es una **redistribución operativa**, no un cálculo climático independiente.

📌 Este enfoque es coherente con estudios de riego y planificación de dotaciones.

---

### 🔹 Limitaciones conocidas

- No incorpora:
  - balance de suelo dinámico,
  - capacidad de retención hídrica,
  - estrés hídrico real del cultivo,
  - coeficientes de eficiencia de aplicación.
- No sustituye a:
  - estaciones propias en parcela,
  - sensores de humedad,
  - modelos de riego en tiempo real.

El sistema debe entenderse como una **herramienta de apoyo a la decisión**, no como un controlador automático de riego.

---

### 🔹 Validación externa

- El modelo está pensado para ser **contrastado** con:
  - SIAR,
  - estudios locales,
  - series históricas propias del usuario.
- Las discrepancias deben interpretarse en términos de:
  - escala temporal,
  - representatividad espacial,
  - hipótesis de diseño.

---

📌 **Filosofía general:**  
> *Mejor un modelo claro, explicable y trazable que uno aparentemente preciso pero opaco.*

---

