import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.set_page_config(page_title="Dashboard de Observabilidad - CookAi", layout="wide")
st.title("📊 Dashboard de Monitoreo e Indicadores CookAi")

# 1. Simulación de carga de datos de logs (reemplazar por tu archivo real)
# En producción, aquí leerías tu archivo de logs.csv o tu base de datos
data = {
    "Fecha": pd.date_range(start="2026-07-01", periods=10, freq="D"),
    "Latencia_Segundos": [1.2, 1.5, 2.4, 0.8, 3.1, 1.1, 1.4, 4.2, 1.9, 1.3],
    "Resultado": ["Success", "Success", "Error", "Success", "Success", "Success", "Error", "Success", "Success", "Success"],
    "Tokens_Uso": [150, 180, 90, 210, 320, 140, 95, 410, 200, 175]
}
df = pd.DataFrame(data)

# --- FILAS DE MÉTRICAS PRINCIPALES ---
col1, col2, col3 = st.columns(3)

with col1:
    # Métrica 1: Latencia Promedio
    latencia_promedio = df["Latencia_Segundos"].mean()
    st.metric(label="⏱️ Latencia Promedio", value=f"{latencia_promedio:.2f} seg")

with col2:
    # Métrica 2: Frecuencia de Errores
    total_errores = (df["Resultado"] == "Error").sum()
    tasa_error = (total_errores / len(df)) * 100
    st.metric(label="❌ Frecuencia de Errores", value=f"{tasa_error:.1f}%", delta=f"{total_errores} fallos")

with col3:
    # Métrica 3: Uso de Recursos (Tokens promedio)
    tokens_promedio = df["Tokens_Uso"].mean()
    st.metric(label="⚡ Uso de Recursos Promedio", value=f"{tokens_promedio:.0f} Tokens")

st.markdown("---")

# --- GRÁFICOS INTERACTIVOS ---
col_graf1, col_graf2 = st.columns(2)

with col_graf1:
    st.subheader("Evolución de la Latencia por Día")
    st.line_chart(df.set_index("Fecha")["Latencia_Segundos"])

with col_graf2:
    st.subheader("Consistencia del Sistema (Éxitos vs Errores)")
    conteo_resultados = df["Resultado"].value_counts()

    # Gráfico usando matplotlib
    fig, ax = plt.subplots()
    ax.pie(conteo_resultados, labels=conteo_resultados.index, autopct='%1.1f%%', colors=['#4CAF50', '#FF5722'])
    st.pyplot(fig)