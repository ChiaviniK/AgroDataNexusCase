import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- Configuração "Agro Profissional" ---
st.set_page_config(page_title="AgroData Nexus | Data Eng.", page_icon="🚜", layout="wide")

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

# --- FUNÇÕES DE SIMULAÇÃO (FALLBACK) ---

def gerar_serie_fake(valor_inicial, volatilidade, n_dias):
    retornos = np.random.normal(0, volatilidade, n_dias)
    preco = valor_inicial + np.cumsum(retornos)
    return preco

def gerar_financeiro_fake():
    datas = pd.date_range(end=datetime.now(), periods=365, freq='B')
    n = len(datas)
    df = pd.DataFrame(index=datas)
    df['Dolar'] = gerar_serie_fake(5.0, 0.02, n)
    df['JBS'] = gerar_serie_fake(25.0, 0.3, n)
    df['Boi_Gordo'] = gerar_serie_fake(230.0, 1.5, n)
    return df

def gerar_clima_fake():
    datas = pd.date_range(end=datetime.now(), periods=365, freq='D')
    n = len(datas)
    temp = 32 + 5 * np.sin(np.linspace(0, 3.14, n)) + np.random.normal(0, 2, n)
    chuva = np.random.choice([0, 0, 0, 10, 30, 60], n, p=[0.7, 0.1, 0.1, 0.05, 0.03, 0.02])
    return pd.DataFrame({'Temp_Max': temp, 'Chuva_mm': chuva}, index=datas)

# --- FUNÇÕES DE DADOS REAIS ---

@st.cache_data(ttl=3600)
def get_finance_data():
    tickers = ['BRL=X', 'JBSS3.SA', 'LE=F']
    try:
        df = yf.download(tickers, period="1y", interval="1d", progress=False)
        if isinstance(df.columns, pd.MultiIndex): df = df['Close']
        if df.empty: raise Exception("Dados vazios")

        df_clean = pd.DataFrame(index=df.index)
        
        # Lógica de Fallback Granular (Coluna por Coluna)
        # 1. Dólar
        if 'BRL=X' in df.columns and not df['BRL=X'].isnull().all():
            df_clean['Dolar'] = df['BRL=X']
        else:
            df_clean['Dolar'] = gerar_serie_fake(5.10, 0.02, len(df))

        # 2. Gado Futuro
        if 'LE=F' in df.columns and not df['LE=F'].isnull().all():
            df_clean['Gado_Futuro_US'] = df['LE=F']
        else:
            df_clean['Gado_Futuro_US'] = gerar_serie_fake(180.0, 1.0, len(df))

        # 3. JBS
        if 'JBSS3.SA' in df.columns and not df['JBSS3.SA'].isnull().all():
            df_clean['JBS'] = df['JBSS3.SA']
        else:
            df_clean['JBS'] = gerar_serie_fake(32.0, 0.4, len(df))

        df_clean.index = df_clean.index.tz_localize(None)
        df_clean = df_clean.ffill().bfill()
        df_clean['Boi_Gordo'] = (df_clean['Gado_Futuro_US'] / 100) * df_clean['Dolar'] * 3.5 * 15 
        
        return df_clean[['Dolar', 'JBS', 'Boi_Gordo']], True

    except:
        return gerar_financeiro_fake(), False

@st.cache_data(ttl=3600)
def get_weather_cuiaba():
    try:
        lat, lon = -15.6014, -56.0979
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={start_date}&end_date={end_date}&daily=temperature_2m_max,precipitation_sum&timezone=America%2FCuiaba"
        
        res = requests.get(url, timeout=3)
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

# --- CARGA E TRATAMENTO ---
df_fin, is_real_fin = get_finance_data()
df_clima, is_real_clima = get_weather_cuiaba()

# Merge interno para o Dashboard (O aluno vê o resultado final, mas baixa separado)
df_full = pd.concat([df_fin, df_clima], axis=1).sort_index()
df_full['Dolar'] = df_full['Dolar'].ffill().bfill()
df_full['JBS'] = df_full['JBS'].ffill().bfill()
df_full['Boi_Gordo'] = df_full['Boi_Gordo'].ffill().bfill()
df_full['Chuva_mm'] = df_full['Chuva_mm'].fillna(0)
df_full['Temp_Max'] = df_full['Temp_Max'].ffill().bfill()
df_full = df_full.fillna(0)

# --- SIDEBAR ---
with st.sidebar:
    st.image("https://img.icons8.com/dusk/96/bull.png", width=80)
    st.title("AgroData Nexus")
    
    if is_real_fin: st.toast("Mercado: Online", icon="🟢")
    else: st.toast("Mercado: Simulado", icon="🟠")
    
    st.markdown("---")
    
    if not df_full.empty:
        max_date = df_full.index.max().date()
        min_date = df_full.index.min().date()
    else:
        max_date = datetime.now().date()
        min_date = max_date - timedelta(days=30)
    
    default_start = max_date - timedelta(days=90)
    if default_start < min_date: default_start = min_date
        
    start_date_graph = st.date_input("De:", value=default_start, min_value=min_date, max_value=max_date)
    end_date_graph = st.date_input("Até:", value=max_date, min_value=min_date, max_value=max_date)

mask = (df_full.index.date >= start_date_graph) & (df_full.index.date <= end_date_graph)
df_filtered = df_full.loc[mask]

# --- DASHBOARD ---
st.title(f"Monitor Agro: {end_date_graph.strftime('%d/%m/%Y')}")

if df_filtered.empty:
    st.error("Sem dados.")
    st.stop()

dia_dados = df_filtered.iloc[-1]
dia_anterior = df_filtered.iloc[-2] if len(df_filtered) > 1 else dia_dados

col1, col2, col3, col4 = st.columns(4)
def kpi(label, val, prev, prefix="R$ ", decim=2):
    try:
        val, prev = float(val), float(prev)
        if val == 0: st.metric(label, "N/A", "0.00")
        else: st.metric(label, f"{prefix}{val:.{decim}f}", f"{val-prev:.{decim}f}")
    except: st.metric(label, "N/A", "0.00")

with col1: kpi("💵 Dólar", dia_dados['Dolar'], dia_anterior['Dolar'], "R$ ", 3)
with col2: kpi("🐂 Boi Gordo", dia_dados['Boi_Gordo'], dia_anterior['Boi_Gordo'])
with col3: kpi("🏭 JBS (JBSS3)", dia_dados['JBS'], dia_anterior['JBS'])
with col4: st.metric("🌧️ Chuva (Cuiabá)", f"{dia_dados['Chuva_mm']:.1f} mm")

st.markdown("---")

tab1, tab2, tab3 = st.tabs(["📊 Mercado", "🌦️ Clima vs. Preço", "💾 Dados (ETL)"])

with tab1:
    fig_ind = go.Figure()
    fig_ind.add_trace(go.Scatter(x=df_filtered.index, y=df_filtered['Boi_Gordo'], name="Boi Gordo (R$)", line=dict(color='#8e44ad')))
    fig_ind.add_trace(go.Scatter(x=df_filtered.index, y=df_filtered['JBS'], name="Ação JBS (R$)", line=dict(color='#e67e22')))
    fig_ind.add_trace(go.Scatter(x=df_filtered.index, y=df_filtered['Dolar'], name="Dólar", line=dict(color='#2ecc71', dash='dot'), yaxis='y2'))
    fig_ind.update_layout(height=450, template="plotly_white", yaxis=dict(title="R$"), yaxis2=dict(title="USD", overlaying='y', side='right'))
    st.plotly_chart(fig_ind, use_container_width=True)

with tab2:
    col_c1, col_c2 = st.columns([3, 1])
    with col_c1:
        fig_clima = make_subplots(specs=[[{"secondary_y": True}]])
        fig_clima.add_trace(go.Bar(x=df_filtered.index, y=df_filtered['Chuva_mm'], name="Chuva (mm)", marker_color='#3498db', opacity=0.4), secondary_y=False)
        fig_clima.add_trace(go.Scatter(x=df_filtered.index, y=df_filtered['Boi_Gordo'], name="Preço Boi (R$)", line=dict(color='#c0392b')), secondary_y=True)
        fig_clima.update_layout(height=400, template="plotly_white")
        st.plotly_chart(fig_clima, use_container_width=True)
    with col_c2:
        st.markdown("**Correlação**")
        corr = df_filtered[['Chuva_mm', 'Boi_Gordo']].corr().iloc[0,1]
        st.info(f"Índice: {corr:.2f}")

# --- ABA DE DOWNLOADS (SEPARADOS) ---
with tab3:
    st.subheader("Central de Extração (Desafio ETL)")
    st.info("💡 As bases de dados estão separadas propositalmente. Você precisará cruzá-las usando a Data como chave.")

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("##### 💹 Base Financeira (B3/Chicago)")
        # Seleciona apenas colunas financeiras do DF tratado
        cols_fin = ['Dolar', 'JBS', 'Boi_Gordo']
        # Garante que as colunas existem
        cols_fin_validas = [c for c in cols_fin if c in df_filtered.columns]
        df_fin_export = df_filtered[cols_fin_validas]
        
        st.dataframe(df_fin_export.tail(3), use_container_width=True)
        csv_fin = df_fin_export.to_csv().encode('utf-8')
        st.download_button("📥 Baixar Financeiro.csv", csv_fin, "finance_data.csv", "text/csv")

    with c2:
        st.markdown("##### 🌦️ Base Climática (Cuiabá)")
        # Seleciona apenas colunas climáticas
        cols_clima = ['Temp_Max', 'Chuva_mm']
        cols_clima_validas = [c for c in cols_clima if c in df_filtered.columns]
        df_clima_export = df_filtered[cols_clima_validas]
        
        st.dataframe(df_clima_export.tail(3), use_container_width=True)
        csv_clima = df_clima_export.to_csv().encode('utf-8')
        st.download_button("📥 Baixar Clima.csv", csv_clima, "weather_data.csv", "text/csv")

        st.dataframe(df_filtered.sort_index(ascending=False), use_container_width=True)
        csv = df_filtered.to_csv().encode('utf-8')
        st.download_button("📥 Baixar CSV", csv, "dados_agro.csv", "text/csv")
