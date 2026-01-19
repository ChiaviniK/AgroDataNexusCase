import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- Configuração "Agro Profissional" ---
st.set_page_config(page_title="AgroData Nexus | Real-Time", page_icon="🐮", layout="wide")

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

# --- FUNÇÕES DE DADOS (REAIS) ---

@st.cache_data(ttl=3600)
def get_finance_data():
    """Baixa dados REAIS do Yahoo Finance."""
    tickers = ['BRL=X', 'JBSS3.SA', 'LE=F']
    try:
        df = yf.download(tickers, period="2y", interval="1d", progress=False)['Close']
        if df.empty: return pd.DataFrame(), False
        
        df.columns = ['Dolar', 'JBS', 'Gado_Futuro_US']
        df.index = df.index.tz_localize(None)
        
        # Conversão: (Preço em centavos / 100) * Dolar * Fator Conversão
        df['Boi_Gordo'] = (df['Gado_Futuro_US'] / 100) * df['Dolar'] * 3.5 * 15 
        
        df = df.ffill()
        return df, True
    except:
        return pd.DataFrame(), False

@st.cache_data(ttl=3600)
def get_weather_cuiaba():
    """Baixa dados REAIS de Clima (Cuiabá)."""
    try:
        lat, lon = -15.6014, -56.0979
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')
        
        url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={start_date}&end_date={end_date}&daily=temperature_2m_max,precipitation_sum&timezone=America%2FCuiaba"
        
        res = requests.get(url, timeout=5)
        data = res.json()
        
        if 'daily' not in data: return pd.DataFrame(), False

        df = pd.DataFrame({
            'Date': data['daily']['time'],
            'Temp_Max': data['daily']['temperature_2m_max'],
            'Chuva_mm': data['daily']['precipitation_sum']
        })
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
        return df, True
    except:
        return pd.DataFrame(), False

# --- CARGA E MERGE (ETL BLINDADO) ---
df_fin, status_fin = get_finance_data()
df_clima, status_clima = get_weather_cuiaba()

df_full = pd.DataFrame() # Começa vazio por segurança

try:
    if not df_fin.empty and not df_clima.empty:
        df_full = pd.concat([df_fin, df_clima], axis=1).sort_index()
        df_full['Dolar'] = df_full['Dolar'].ffill()
        df_full['JBS'] = df_full['JBS'].ffill()
        df_full['Boi_Gordo'] = df_full['Boi_Gordo'].ffill()
        df_full['Chuva_mm'] = df_full['Chuva_mm'].fillna(0)
        df_full['Temp_Max'] = df_full['Temp_Max'].ffill()
        df_full = df_full.dropna().tail(730)
except:
    pass # Se der erro no merge, df_full continua vazio

# --- SIDEBAR (CORREÇÃO DO ERRO NAT) ---
with st.sidebar:
    st.image("https://img.icons8.com/dusk/96/bull.png", width=80)
    st.title("AgroData Nexus")
    st.caption("📍 Dados: Cuiabá/MT & B3/Chicago")
    
    if status_fin: st.toast("Mercado: Online", icon="🟢")
    else: st.error("Mercado: Offline/Erro")
        
    if status_clima: st.toast("Clima: Online", icon="🟢")
    else: st.error("Clima: Offline/Erro")
    
    st.markdown("---")
    
    # --- AQUI ESTÁ A CORREÇÃO PRINCIPAL ---
    # Verifica se o DataFrame tem dados antes de calcular datas
    if not df_full.empty:
        try:
            max_date = df_full.index.max().date()
            min_date = df_full.index.min().date()
        except:
            # Fallback se a conversão falhar
            max_date = datetime.now().date()
            min_date = max_date - timedelta(days=30)
    else:
        # Fallback total se não houver dados (evita o crash)
        max_date = datetime.now().date()
        min_date = max_date - timedelta(days=30)

    st.header("1. Filtro Temporal")
    
    # Garante que start_date padrão seja válido
    default_start = max_date - timedelta(days=180)
    if default_start < min_date: default_start = min_date
        
    start_date_graph = st.date_input("De:", value=default_start, min_value=min_date, max_value=max_date)
    end_date_graph = st.date_input("Até:", value=max_date, min_value=min_date, max_value=max_date)

# Se não tiver dados, para aqui e avisa
if df_full.empty:
    st.warning("⚠️ Não foi possível carregar os dados reais no momento.")
    st.info("Verifique sua conexão ou tente recarregar a página em instantes.")
    st.stop()

# Filtro do DataFrame
mask = (df_full.index.date >= start_date_graph) & (df_full.index.date <= end_date_graph)
df_filtered = df_full.loc[mask]

# --- DASHBOARD ---
st.title(f"Monitor Agro: {end_date_graph.strftime('%d/%m/%Y')}")

if not df_filtered.empty:
    dia_dados = df_filtered.iloc[-1]
    dia_anterior = df_filtered.iloc[-2] if len(df_filtered) > 1 else dia_dados
else:
    st.error("Sem dados para o período selecionado.")
    st.stop()

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
            st.caption("Valores próximos de 1 ou -1 indicam forte relação.")
        except:
            st.warning("Dados insuficientes.")

with tab3:
    st.dataframe(df_filtered.sort_index(ascending=False), use_container_width=True)
    csv = df_filtered.to_csv().encode('utf-8')
    st.download_button("📥 Baixar CSV", csv, "dados_agro.csv", "text/csv")
