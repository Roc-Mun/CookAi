import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="Dashboard CookAI", layout="wide")
st.title("Dashboard de Monitoreo e Indicadores CookAI")
st.caption("Observabilidad en tiempo real del agente: precision, latencia, consistencia y trazabilidad (ISY0101, IL3.1 / IL3.2).")


@st.cache_data(ttl=5)
def cargar_metricas():
    resp = requests.get(f"{API_BASE}/metrics", timeout=5)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=5)
def cargar_historial(limit=50):
    resp = requests.get(f"{API_BASE}/metrics/history", params={"limit": limit}, timeout=5)
    resp.raise_for_status()
    return resp.json().get("registros", [])


try:
    metrics = cargar_metricas()
    historial = cargar_historial()
except Exception as e:
    st.error(
        f"No se pudo conectar con el backend en {API_BASE}. "
        f"Verifica que este corriendo (uvicorn app.main:app). Detalle: {e}"
    )
    st.stop()

df = pd.DataFrame(historial)
hay_historial = not df.empty

if hay_historial:
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["latencia_seg"] = df["latencia_ms"] / 1000
    df["tokens_totales"] = df["tokens_input"].fillna(0) + df["tokens_output"].fillna(0)

# --- KPIs agregados (todas las operaciones registradas) ---
latencia_promedio = metrics.get("latencia_promedio", 0) / 1000
tasa_exito = metrics.get("tasa_exito", 0)
total_ops = metrics.get("total_operaciones", 0)
frecuencia_error = round(100 - tasa_exito, 2)
operaciones_fallidas = round(total_ops * frecuencia_error / 100)

if hay_historial and df["consistency_score"].notna().any():
    consistencia_promedio = round(df["consistency_score"].mean() * 100, 1)
else:
    consistencia_promedio = None

if hay_historial and "precision_score" in df.columns and df["precision_score"].notna().any():
    precision_promedio = round(df["precision_score"].mean() * 100, 1)
else:
    precision_promedio = None

tokens_promedio = round(df["tokens_totales"].mean(), 0) if hay_historial else 0

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("Latencia promedio", f"{latencia_promedio:.2f} s")
with col2:
    st.metric("Tasa de errores", f"{frecuencia_error:.1f} %")
    st.caption(f"{operaciones_fallidas} de {total_ops} operaciones fallaron")
with col3:
    valor_consistencia = f"{consistencia_promedio:.1f} %" if consistencia_promedio is not None else "Sin datos"
    st.metric("Consistencia promedio", valor_consistencia)
    st.caption("Fidelidad de la respuesta frente a lo solicitado")
with col4:
    valor_precision = f"{precision_promedio:.1f} %" if precision_promedio is not None else "Sin datos"
    st.metric("Precision promedio", valor_precision)
    st.caption("Cobertura de ingredientes de la receta recomendada")
with col5:
    st.metric("Tokens promedio por operacion", f"{tokens_promedio:.0f}")

st.divider()

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Evolucion de la latencia")
    st.caption(f"Ultimas {len(df)} operaciones registradas" if hay_historial else "Sin registros aun")
    if hay_historial:
        st.line_chart(df.set_index("timestamp")["latencia_seg"], height=320, y_label="segundos")
    else:
        st.info("Aun no hay suficientes operaciones para graficar la evolucion de la latencia.")

with col_right:
    st.subheader("Consistencia del sistema (exito vs error)")
    if total_ops > 0:
        fig, ax = plt.subplots(figsize=(4, 4), facecolor="white")
        labels = ["Exito", "Error"]
        sizes = [tasa_exito, frecuencia_error]
        colors = ["#4CAF50", "#E5484D"]

        wedges, texts, autotexts = ax.pie(
            sizes, labels=labels, autopct="%1.1f%%", startangle=90, colors=colors
        )
        for text in texts:
            text.set_color("#1A1A2E")
            text.set_weight("bold")
        for autotext in autotexts:
            autotext.set_color("#FFFFFF")
            autotext.set_weight("bold")
        ax.axis("equal")
        st.pyplot(fig)
    else:
        st.info("Aun no hay operaciones registradas.")

st.divider()

st.subheader("Latencia promedio por tipo de operacion")
if hay_historial:
    promedio_por_tipo = df.groupby("tipo_operacion")["latencia_seg"].mean().sort_values(ascending=False)
    st.bar_chart(promedio_por_tipo, height=280, y_label="segundos")
else:
    st.info("Aun no hay operaciones registradas.")

st.divider()

st.subheader("Trazabilidad: ultimas operaciones registradas")
st.caption(
    "Cada fila corresponde a una ejecucion real del agente (IL3.2). El trace_id permite "
    "buscar todos los pasos de esa misma solicitud en data/logs/cookai_execution.log."
)
if hay_historial:
    columnas = ["timestamp", "tipo_operacion", "status", "latencia_seg", "consistency_score", "tokens_totales"]
    nombres = ["Fecha y hora", "Operacion", "Estado", "Latencia (s)", "Consistencia", "Tokens"]
    if "precision_score" in df.columns:
        columnas.append("precision_score")
        nombres.append("Precision")
    if "trace_id" in df.columns:
        columnas.append("trace_id")
        nombres.append("Trace ID")

    tabla = df[columnas].copy()
    tabla = tabla.sort_values("timestamp", ascending=False)
    tabla.columns = nombres
    st.dataframe(tabla, use_container_width=True, hide_index=True)
else:
    st.info("Aun no hay operaciones registradas.")
