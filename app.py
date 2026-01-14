import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import numpy as np # Importante para gerar dados simulados
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- Configuração "Agro Profissional" ---
st.set_page_config(page_title="AgroData Nexus", page_icon="🌾", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #f4f6f0; color: #2c3e50; }
    h1, h2, h3 { color: #2e7d32 !important; font-family: 'Helvetica Neue', sans-serif; }
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border-left: 6px solid #2e7d32;
        padding: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    div[data-testid="stMetricLabel"] { color: #666; font-size: 0.9rem; }
    div[data-testid="stMetricValue"] { color: #2e7d32; font-weight: bold; }
    .stButton>button { background-color: #2e7d32; color: white; border-radius: 4px; border: none; }
    [data-testid="stSidebar"] { background-color: #e8f5e9; border-right: 1px solid #c8e6c9; }
</style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE DADOS (COM BACKUP/FALLBACK) ---

def gerar_dados_financeiros_fake():
    """Gera dados financeiros se a API falhar"""
    datas = pd.date_range(end=datetime.now(), periods=365, freq='B') # Dias úteis
    n = len(datas)
    # Simulação Random Walk
    dolar = 5.0 + np.cumsum(np.random.normal(0, 0.05, n))
    jbs = 25.0 + np.cumsum(np.random.normal(0, 0.5, n))
    milho = 60.0 + np.cumsum(np.random.normal(0, 1.0, n))
    
    df = pd.DataFrame({'Dolar': dolar, 'JBS': jbs, 'Milho': milho}, index=datas)
    df['Boi_Gordo'] = (df['JBS'] * 8.5) + 50 + np.random.normal(0, 2, n)
    return df

def gerar_dados_clima_fake():
    """Gera dados de clima se a API falhar"""
    datas = pd.date_range(end=datetime.now(), periods=365, freq='D')
    n = len(datas)
    # Clima mais quente no meio do ano (sazonalidade fake)
    temp = 30 + 5 * np.sin(np.linspace(0, 3.14, n)) + np.random.normal(0, 2, n)
    chuva = np.random.choice([0, 0, 0, 0, 10, 25, 50], n, p=[0.6, 0.1, 0.1, 0.1, 0.05, 0.03, 0.02])
    
    df = pd.DataFrame({'Temp_Max': temp, 'Chuva_mm': chuva}, index=datas)
    return df

@st.cache_data
def get_finance_history():
    """Tenta baixar Yahoo Finance, se falhar, usa fake"""
    tickers = ['BRL=X', 'JBSS3.SA', 'ZC=F']
    try:
        # Tenta baixar da API
        df = yf.download(tickers, period="1y", interval="1d", progress=False)['Close']
        
        if df.empty or len(df) < 10:
            raise Exception("Dados vazios")
            
        df.columns = ['Dolar', 'JBS', 'Milho']
        df.index = df.index.tz_localize(None) 
        df['Boi_Gordo'] = (df['JBS'] * 8.5) + 50 
        return df, True # True = Dados Reais
        
    except Exception as e:
        # Se der erro, usa simulado
        return gerar_dados_financeiros_fake(), False # False = Dados Simulados

@st.cache_data
def get_weather_history():
    """Tenta baixar Open-Meteo, se falhar, usa fake"""
    try:
        lat, lon = -11.86, -55.50
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        
        url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={start_date}&end_date={end_date}&daily=temperature_2m_max,precipitation_sum&timezone=America%2FSao_Paulo"
        
        res = requests.get(url, timeout=5) # Timeout de 5s para não travar
        data = res.json()
        
        if 'daily' not in data:
            raise Exception("API Clima falhou")

        df = pd.DataFrame({
            'Date': data['daily']['time'],
            'Temp_Max': data['daily']['temperature_2m_max'],
            'Chuva_mm': data['daily']['precipitation_sum']
        })
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
        return df, True
        
    except Exception as e:
        return gerar_dados_clima_fake(), False

# --- CARGA DE DADOS ---
df_fin, status_fin = get_finance_history()
df_clima, status_clima = get_weather_history()

# Merge (Inner Join)
# Garante que as colunas existam mesmo se o merge falhar
try:
    df_full = pd.concat([df_fin, df_clima], axis=1).dropna()
    if df_full.empty:
        # Se o merge der vazio (datas não batem), força o uso dos dados financeiros como base
        df_full = df_fin.copy()
        df_full['Temp_Max'] = 30.0
        df_full['Chuva_mm'] = 0.0
except:
    df_full = df_fin.copy() # Fallback final

# --- INTERFACE ---

# Avisos de Status (Discretos)
if not status_fin:
    st.toast("⚠️ Yahoo Finance instável. Usando dados de backup para demonstração.", icon="⚠️")
if not status_clima:
    st.toast("⚠️ API Clima instável. Usando dados de backup.", icon="☁️")

# Sidebar
with st.sidebar:
    st.image("https://img.icons8.com/dusk/96/tractor.png", width=80)
    st.title("AgroData Nexus")
    st.markdown("---")
    st.header("📅 Navegação")
    
    if not df_full.empty:
        min_date = df_full.index.min().date()
        max_date = df_full.index.max().date()
        selected_date = st.date_input("Data:", value=max_date, min_value=min_date, max_value=max_date)
    else:
        selected_date = datetime.now().date()

# Conteúdo Principal
st.title(f"Monitor de Mercado: {selected_date.strftime('%d/%m/%Y')}")

if df_full.empty:
    st.error("Erro crítico: Não foi possível gerar dados.")
    st.stop()

# Filtra Data
try:
    dia_dados = df_full.loc[pd.Timestamp(selected_date)]
    # Tenta pegar dia anterior
    try:
        dia_anterior = df_full.iloc[df_full.index.get_loc(pd.Timestamp(selected_date)) - 1]
    except:
        dia_anterior = dia_dados
except KeyError:
    # Se cair num fds, pega o último disponível
    dia_dados = df_full.iloc[-1]
    dia_anterior = df_full.iloc[-2]
    st.caption(f"📅 Dados mostrados referentes ao último fechamento: {dia_dados.name.strftime('%d/%m/%Y')}")

# KPIs
col1, col2, col3, col4 = st.columns(4)
with col1:
    delta = dia_dados['Dolar'] - dia_anterior['Dolar']
    st.metric("💵 Dólar", f"R$ {dia_dados['Dolar']:.2f}", f"{delta:.2f}")
with col2:
    delta = dia_dados['Boi_Gordo'] - dia_anterior['Boi_Gordo']
    st.metric("🐂 Boi Gordo", f"R$ {dia_dados['Boi_Gordo']:.2f}", f"{delta:.2f}")
with col3:
    st.metric("🌡️ Temp. Máx", f"{dia_dados['Temp_Max']:.1f} °C")
with col4:
    st.metric("🌧️ Chuva", f"{dia_dados['Chuva_mm']:.1f} mm")

st.markdown("---")

# Abas Gráficos e Download
tab1, tab2 = st.tabs(["📊 Visão Gráfica", "💾 Data Lake (Downloads)"])

with tab1:
    st.subheader("Correlação: Clima x Commodities")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_full.index, y=df_full['Boi_Gordo'], name="Preço Arroba (R$)", line=dict(color='#2e7d32', width=2)))
    fig.add_trace(go.Bar(x=df_full.index, y=df_full['Chuva_mm'], name="Chuva (mm)", marker_color='#81d4fa', opacity=0.3, yaxis='y2'))
    
    fig.update_layout(
        yaxis=dict(title="Preço (R$)", side="left"),
        yaxis2=dict(title="Chuva (mm)", side="right", overlaying="y", showgrid=False),
        template="plotly_white", height=450, hovermode="x unified"
    )
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.info("Baixe os dados (Reais ou Simulados) para usar no seu Banco de Dados SQL.")
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("📥 Baixar CSV Financeiro", df_fin.to_csv(), "finance_data.csv", "text/csv")
    with c2:
        st.download_button("📥 Baixar CSV Clima", df_clima.to_csv(), "weather_data.csv", "text/csv")
