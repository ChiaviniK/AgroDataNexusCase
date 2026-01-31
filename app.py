import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="AgroDataNexus | Intelligence", page_icon="🌱", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #f4f9f4; color: #1e4d2b; }
    h1, h2 { color: #2e8b57 !important; }
    .stMetric { background-color: white; border: 1px solid #c3e6cb; border-radius: 8px; padding: 10px; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 📡 MOTOR 1: API CLIMÁTICA REAL (OPEN-METEO)
# ==============================================================================
@st.cache_data
def get_climate_history(lat, lon, anos=3):
    """
    Busca dados reais de chuva e temperatura na Open-Meteo API.
    """
    hoje = datetime.now()
    inicio = (hoje - timedelta(days=365 * anos)).strftime('%Y-%m-%d')
    fim = hoje.strftime('%Y-%m-%d')
    
    # URL da API (Dados Históricos)
    url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={inicio}&end_date={fim}&daily=temperature_2m_max,precipitation_sum&timezone=America%2FSao_Paulo"
    
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            
            # Monta o DataFrame
            df = pd.DataFrame({
                'Data': data['daily']['time'],
                'Temp_Max_C': data['daily']['temperature_2m_max'],
                'Chuva_mm': data['daily']['precipitation_sum']
            })
            df['Data'] = pd.to_datetime(df['Data'])
            df['Ano'] = df['Data'].dt.year
            return df
        else:
            return pd.DataFrame()
    except:
        return pd.DataFrame()

# ==============================================================================
# 🚜 MOTOR 2: SIMULADOR DE SAFRA (FENOLOGIA)
# ==============================================================================
@st.cache_data
def gerar_dados_safra_atual():
    """Gera dados biológicos (NDVI) para a Safra 2024."""
    datas = pd.date_range(start='2024-01-01', end='2024-12-31', freq='D')
    df = pd.DataFrame({'Data': datas})
    df['Mes'] = df['Data'].dt.month
    
    # Simula Chuva (Sazonalidade MT)
    conditions = [(df['Mes'].isin([1, 2, 3, 11, 12])), (df['Mes'].isin([6, 7, 8]))]
    choices = [np.random.gamma(2, 10, len(df)), np.random.exponential(1, len(df))]
    df['Chuva_mm'] = np.select(conditions, choices, default=np.random.gamma(1, 5, len(df)))
    
    # Simula NDVI (Saúde da Planta)
    def get_ndvi(m):
        if m in [1, 2]: return 0.85 # Soja cheia
        if m == 3: return 0.60      # Amarelando
        if m == 4: return 0.20      # Colheita
        if m >= 10: return 0.40     # Plantio
        return 0.15                 # Pousio
    
    df['NDVI'] = df['Mes'].apply(get_ndvi) + np.random.normal(0, 0.02, len(df))
    df['NDVI'] = df['NDVI'].clip(0, 1)
    
    return df

# ==============================================================================
# 🖥️ INTERFACE
# ==============================================================================
st.sidebar.image("https://img.icons8.com/dusk/96/tractor.png", width=80)
st.sidebar.title("AgroDataNexus")
st.sidebar.markdown("---")
st.sidebar.info("📍 Fazenda Monitorada:\nSorriso, Mato Grosso\n(Capital da Soja)")

st.title("🚜 Painel de Inteligência Agrícola")

tab_safra, tab_hist = st.tabs(["🌱 Safra Atual (Operacional)", "🌦️ Histórico Climático (3 Anos)"])

# --- ABA 1: SAFRA ATUAL (O que já tínhamos) ---
with tab_safra:
    st.header("Monitoramento Fenológico: Safra 2024")
    df_safra = gerar_dados_safra_atual()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Acumulado Chuva (2024)", f"{df_safra['Chuva_mm'].sum():.1f} mm")
    c2.metric("Vigor Médio (NDVI)", f"{df_safra['NDVI'].mean():.2f}")
    c3.metric("Status", "Colheita Finalizada", "Abr/24")
    
    # Gráfico Combinado
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df_safra['Data'], y=df_safra['Chuva_mm'], name='Chuva (mm)', marker_color='#82ca9d'))
    fig.add_trace(go.Scatter(x=df_safra['Data'], y=df_safra['NDVI']*100, name='NDVI (x100)', line=dict(color='green', width=2)))
    fig.update_layout(title="Ciclo da Cultura (Chuva vs Biomassa)", height=400)
    st.plotly_chart(fig, use_container_width=True)

# --- ABA 2: HISTÓRICO REAL (A Novidade) ---
with tab_hist:
    st.header("Análise Climática Histórica (Big Data)")
    st.markdown("Dados reais extraídos da estação meteorológica via satélite (Open-Meteo API).")
    
    # Coordenadas de Sorriso - MT
    LAT, LON = -12.54, -55.72 
    
    with st.spinner("Conectando ao Satélite..."):
        df_hist = get_climate_history(LAT, LON)
        
    if not df_hist.empty:
        # Filtros de Ano
        anos_disponiveis = sorted(df_hist['Ano'].unique())
        ano_sel = st.multiselect("Comparar Anos:", anos_disponiveis, default=anos_disponiveis)
        
        df_filtrado = df_hist[df_hist['Ano'].isin(ano_sel)]
        
        # 1. Gráfico de Precipitação
        st.subheader("💧 Regime de Chuvas (Comparativo)")
        fig_chuva = px.bar(
            df_filtrado, 
            x='Data', 
            y='Chuva_mm', 
            color='Ano', 
            title="Precipitação Diária (mm)",
            color_discrete_sequence=px.colors.qualitative.Prism
        )
        st.plotly_chart(fig_chuva, use_container_width=True)
        
        # 2. Gráfico de Temperatura
        st.subheader("🌡️ Estresse Térmico")
        fig_temp = px.line(
            df_filtrado, 
            x='Data', 
            y='Temp_Max_C', 
            title="Temperaturas Máximas Diárias (°C)",
            line_shape='spline' # Linha suave
        )
        # Adiciona linha de perigo (acima de 35 graus soja sofre abortamento de vagem)
        fig_temp.add_hline(y=35, line_dash="dot", line_color="red", annotation_text="Estresse Térmico (>35°C)")
        st.plotly_chart(fig_temp, use_container_width=True)
        
        # 3. Tabela e Download
        st.markdown("---")
        st.subheader("📥 Exportar Dados Oficiais")
        st.dataframe(df_filtrado.sort_values('Data', ascending=False).head(100), use_container_width=True)
        st.download_button("Baixar CSV Histórico", df_hist.to_csv(index=False).encode('utf-8'), "clima_sorriso_mt.csv")
        
    else:
        st.error("Erro ao conectar com a API Open-Meteo.")
