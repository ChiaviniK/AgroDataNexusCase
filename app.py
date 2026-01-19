import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- Configuração "Agro Profissional" ---
st.set_page_config(page_title="AgroData Nexus | Hybrid", page_icon="🐮", layout="wide")

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
    .stButton>button { background-color: #2e7d32; color: white; border-radius: 4px; border: none; }
</style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE SIMULAÇÃO (SEGURANÇA PARA A AULA) ---

def gerar_financeiro_fake():
    """Gera dados parecidos com o mercado real caso a API falhe"""
    datas = pd.date_range(end=datetime.now(), periods=365, freq='B')
    n = len(datas)
    # Simula Dolar ~ R$ 5.00
    dolar = 5.0 + np.cumsum(np.random.normal(0, 0.02, n))
    # Simula JBS ~ R$ 25.00
    jbs = 25.0 + np.cumsum(np.random.normal(0, 0.3, n))
    # Simula Boi ~ R$ 230.00
    boi = 230.0 + np.cumsum(np.random.normal(0, 1.5, n))
    
    df = pd.DataFrame({'Dolar': dolar, 'JBS': jbs, 'Boi_Gordo': boi}, index=datas)
    return df

def gerar_clima_fake():
    """Gera clima de Cuiabá simulado"""
    datas = pd.date_range(end=datetime.now(), periods=365, freq='D')
    n = len(datas)
    # Temperatura alta (Cuiabá)
    temp = 32 + 5 * np.sin(np.linspace(0, 3.14, n)) + np.random.normal(0, 2, n)
    # Chuva esporádica
    chuva = np.random.choice([0, 0, 0, 10, 30, 60], n, p=[0.7, 0.1, 0.1, 0.05, 0.03, 0.02])
    
    df = pd.DataFrame({'Temp_Max': temp, 'Chuva_mm': chuva}, index=datas)
    return df

# --- FUNÇÕES DE DADOS REAIS (COM FALLBACK) ---

@st.cache_data(ttl=3600)
def get_finance_data():
    """Tenta Yahoo Finance. Se falhar, chama o Fake."""
    tickers = ['BRL=X', 'JBSS3.SA', 'LE=F']
    try:
        # Tenta baixar
        df = yf.download(tickers, period="1y", interval="1d", progress=False)
        
        # Tratamento para novas versões do yfinance (MultiIndex)
        if isinstance(df.columns, pd.MultiIndex):
            df = df['Close']
            
        # Verifica se baixou algo
        if df.empty or len(df) < 10: raise Exception("Dados vazios")
        
        # Renomeia (pode variar a ordem, então usamos mapeamento seguro se possível, 
        # mas aqui forçamos ordem alfabética que o yfinance costuma retornar: BRL, JBS, LE)
        # O ideal é selecionar por nome:
        df_clean = pd.DataFrame(index=df.index)
        df_clean['Dolar'] = df['BRL=X']
        df_clean['JBS'] = df['JBSS3.SA']
        df_clean['Gado_Futuro_US'] = df['LE=F']
        
        df_clean.index = df_clean.index.tz_localize(None)
        
        # Conversão Boi
        df_clean['Boi_Gordo'] = (df_clean['Gado_Futuro_US'] / 100) * df_clean['Dolar'] * 3.5 * 15 
        
        df_clean = df_clean.ffill()
        return df_clean[['Dolar', 'JBS', 'Boi_Gordo']], True # True = Real Data
        
    except Exception as e:
        # Falhou? Usa o simulado!
        return gerar_financeiro_fake(), False # False = Fake Data

@st.cache_data(ttl=3600)
def get_weather_cuiaba():
    """Tenta Open-Meteo. Se falhar, chama o Fake."""
    try:
        lat, lon = -15.6014, -56.0979
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        
        url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={start_date}&end_date={end_date}&daily=temperature_2m_max,precipitation_sum&timezone=America%2FCuiaba"
        
        res = requests.get(url, timeout=3) # Timeout curto para não travar
        data = res.json()
        
        if 'daily' not in data: raise Exception("API Vazia")

        df = pd.DataFrame({
            'Date': data['daily']['time'],
            'Temp_Max': data['daily']['temperature_2m_max'],
            'Chuva_mm': data['daily']['precipitation_sum']
        })
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
        return df, True
    except:
        return gerar_clima_fake(), False

# --- CARGA E MERGE ---
df_fin, is_real_fin = get_finance_data()
df_clima, is_real_clima = get_weather_cuiaba()

# Garante merge seguro
df_full = pd.concat([df_fin, df_clima], axis=1).sort_index()

# Preenchimento final para garantir que não haja NaNs quebrando gráficos
df_full['Dolar'] = df_full['Dolar'].ffill().bfill()
df_full['JBS'] = df_full['JBS'].ffill().bfill()
df_full['Boi_Gordo'] = df_full['Boi_Gordo'].ffill().bfill()
df_full['Chuva_mm'] = df_full['Chuva_mm'].fillna(0)
df_full['Temp_Max'] = df_full['Temp_Max'].ffill().bfill()

# --- SIDEBAR ---
with st.sidebar:
    st.image("https://img.icons8.com/dusk/96/bull.png", width=80)
    st.title("AgroData Nexus")
    
    # Status Indicators
    if is_real_fin: st.toast("Mercado: Dados Reais (Online)", icon="🟢")
    else: st.toast("Mercado: Modo Simulação (Offline)", icon="🟠")
        
    if is_real_clima: st.toast("Clima: Dados Reais (Cuiabá)", icon="🟢")
    else: st.toast("Clima: Modo Simulação (Offline)", icon="🟠")
    
    if not is_real_fin or not is_real_clima:
        st.warning("⚠️ Operando em Contingência. Alguns dados podem ser simulados devido à instabilidade das APIs.")

    st.markdown("---")
    
    # Datas Seguras
    max_date = df_full.index.max().date()
    min_date = df_full.index.min().date()
    
    default_start = max_date - timedelta(days=90)
    if default_start < min_date: default_start = min_date
        
    start_date_graph = st.date_input("De:", value=default_start, min_value=min_date, max_value=max_date)
    end_date_graph = st.date_input("Até:", value=max_date, min_value=min_date, max_value=max_date)

# Filtro
mask = (df_full.index.date >= start_date_graph) & (df_full.index.date <= end_date_graph)
df_filtered = df_full.loc[mask]

# --- DASHBOARD ---
st.title(f"Monitor Agro: {end_date_graph.strftime('%d/%m/%Y')}")

if df_filtered.empty:
    st.error("Período sem dados. Aumente o intervalo.")
    st.stop()

dia_dados = df_filtered.iloc[-1]
dia_anterior = df_filtered.iloc[-2] if len(df_filtered) > 1 else dia_dados

# KPIs
col1, col2, col3, col4 = st.columns(4)
def kpi(label, val, prev, prefix="R$ ", decim=2):
    try:
        delta = val - prev
        st.metric(label, f"{prefix}{val:.{decim}f}", f"{delta:.{decim}f}")
    except:
        st.metric(label, "N/A", "0.00")

with col1: kpi("💵 Dólar", dia_dados['Dolar'], dia_anterior['Dolar'], "R$ ", 3)
with col2: kpi("🐂 Boi Gordo", dia_dados['Boi_Gordo'], dia_anterior['Boi_Gordo'])
with col3: kpi("🏭 JBS (JBSS3)", dia_dados['JBS'], dia_anterior['JBS'])
with col4: st.metric("🌧️ Chuva (Cuiabá)", f"{dia_dados['Chuva_mm']:.1f} mm")

st.markdown("---")

# ABAS
tab1, tab2, tab3 = st.tabs(["📊 Mercado", "🌦️ Clima vs. Preço", "💾 Dados"])

with tab1:
    st.subheader("Evolução de Preços")
    fig_ind = go.Figure()
    fig_ind.add_trace(go.Scatter(x=df_filtered.index, y=df_filtered['Boi_Gordo'], name="Boi Gordo (R$)", line=dict(color='#8e44ad', width=2)))
    fig_ind.add_trace(go.Scatter(x=df_filtered.index, y=df_filtered['JBS'], name="Ação JBS (R$)", line=dict(color='#e67e22', width=2)))
    fig_ind.add_trace(go.Scatter(x=df_filtered.index, y=df_filtered['Dolar'], name="Dólar", line=dict(color='#2ecc71', dash='dot'), yaxis='y2'))
    
    fig_ind.update_layout(
        height=450, 
        template="plotly_white",
        yaxis=dict(title="Preço Ativos (R$)"),
        yaxis2=dict(title="Cotação Dólar", overlaying='y', side='right')
    )
    st.plotly_chart(fig_ind, use_container_width=True)

with tab2:
    st.subheader("Impacto das Chuvas")
    col_c1, col_c2 = st.columns([3, 1])
    
    with col_c1:
        fig_clima = make_subplots(specs=[[{"secondary_y": True}]])
        fig_clima.add_trace(go.Bar(x=df_filtered.index, y=df_filtered['Chuva_mm'], name="Chuva (mm)", marker_color='#3498db', opacity=0.4), secondary_y=False)
        fig_clima.add_trace(go.Scatter(x=df_filtered.index, y=df_filtered['Boi_Gordo'], name="Preço Boi (R$)", line=dict(color='#c0392b')), secondary_y=True)
        
        fig_clima.update_layout(height=400, template="plotly_white", title="Precipitação vs Arroba")
        fig_clima.update_yaxes(title_text="Chuva (mm)", secondary_y=False)
        fig_clima.update_yaxes(title_text="Preço (R$)", secondary_y=True)
        st.plotly_chart(fig_clima, use_container_width=True)
        
    with col_c2:
        st.markdown("**Correlação**")
        try:
            corr = df_filtered[['Chuva_mm', 'Boi_Gordo']].corr().iloc[0,1]
            st.info(f"Índice: {corr:.2f}")
            if abs(corr) < 0.2: st.caption("Correlação fraca.")
            else: st.caption("Correlação moderada/forte.")
        except:
            st.warning("Dados insuficientes.")

with tab3:
    st.dataframe(df_filtered.sort_index(ascending=False), use_container_width=True)
    csv = df_filtered.to_csv().encode('utf-8')
    st.download_button("📥 Baixar CSV", csv, "dados_agro.csv", "text/csv")
