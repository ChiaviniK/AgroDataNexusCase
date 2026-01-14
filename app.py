import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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
    .stButton>button { background-color: #2e7d32; color: white; border-radius: 4px; border: none; }
    [data-testid="stSidebar"] { background-color: #e8f5e9; border-right: 1px solid #c8e6c9; }
</style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE DADOS (COM FALLBACK/SIMULAÇÃO) ---

def gerar_dados_financeiros_fake():
    """Gera dados financeiros simulados se a API falhar"""
    datas = pd.date_range(end=datetime.now(), periods=365, freq='B')
    n = len(datas)
    # Random Walk
    dolar = 5.0 + np.cumsum(np.random.normal(0, 0.05, n))
    jbs = 25.0 + np.cumsum(np.random.normal(0, 0.5, n))
    
    df = pd.DataFrame({'Dolar': dolar, 'JBS': jbs}, index=datas)
    # Arroba simulada seguindo JBS
    df['Boi_Gordo'] = (df['JBS'] * 8.5) + 50 + np.random.normal(0, 2, n)
    return df

def gerar_dados_clima_fake():
    """Gera dados de clima simulados se a API falhar"""
    datas = pd.date_range(end=datetime.now(), periods=365, freq='D')
    n = len(datas)
    temp = 30 + 5 * np.sin(np.linspace(0, 3.14, n)) + np.random.normal(0, 2, n)
    chuva = np.random.choice([0, 0, 0, 0, 10, 25, 50], n, p=[0.6, 0.1, 0.1, 0.1, 0.05, 0.03, 0.02])
    
    df = pd.DataFrame({'Temp_Max': temp, 'Chuva_mm': chuva}, index=datas)
    return df

@st.cache_data
def get_finance_history():
    tickers = ['BRL=X', 'JBSS3.SA']
    try:
        # Tenta baixar da API
        df = yf.download(tickers, period="2y", interval="1d", progress=False)['Close']
        if df.empty or len(df) < 10: raise Exception("Dados vazios")
        
        df.columns = ['Dolar', 'JBS']
        df.index = df.index.tz_localize(None) 
        df['Boi_Gordo'] = (df['JBS'] * 8.5) + 50 # Simulação baseada em JBS
        return df, True
    except:
        return gerar_dados_financeiros_fake(), False

@st.cache_data
def get_weather_history():
    try:
        lat, lon = -11.86, -55.50 # Sinop-MT
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d') # 2 anos
        
        url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={start_date}&end_date={end_date}&daily=temperature_2m_max,precipitation_sum&timezone=America%2FSao_Paulo"
        
        res = requests.get(url, timeout=5)
        data = res.json()
        if 'daily' not in data: raise Exception("API Clima falhou")

        df = pd.DataFrame({
            'Date': data['daily']['time'],
            'Temp_Max': data['daily']['temperature_2m_max'],
            'Chuva_mm': data['daily']['precipitation_sum']
        })
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
        return df, True
    except:
        return gerar_dados_clima_fake(), False

# --- CARGA E MERGE (CORRIGIDO) ---
df_fin, status_fin = get_finance_history()
df_clima, status_clima = get_weather_history()

# Lógica de Merge Blindada
df_full = pd.DataFrame()

try:
    # Tenta cruzar os dados
    df_full = pd.concat([df_fin, df_clima], axis=1).dropna()
    
    # Se o cruzamento der vazio (datas não batem), usa financeiro e preenche clima com 0
    if df_full.empty:
        df_full = df_fin.copy()
        df_full['Temp_Max'] = 0.0
        df_full['Chuva_mm'] = 0.0
except:
    # Se der erro no concat, usa financeiro e preenche clima com 0
    df_full = df_fin.copy()
    df_full['Temp_Max'] = 0.0
    df_full['Chuva_mm'] = 0.0

# Garante que as colunas existam, mesmo que vazias (Evita KeyError)
if 'Chuva_mm' not in df_full.columns:
    df_full['Chuva_mm'] = 0.0
if 'Temp_Max' not in df_full.columns:
    df_full['Temp_Max'] = 0.0


# --- SIDEBAR (NAVEGAÇÃO E FILTROS) ---
with st.sidebar:
    st.image("https://img.icons8.com/dusk/96/tractor.png", width=80)
    st.title("AgroData Nexus")
    
    # Avisos de Status
    if not status_fin: st.toast("⚠️ Dados Financeiros: Modo Simulação", icon="⚠️")
    if not status_clima: st.toast("⚠️ Dados Climáticos: Modo Simulação", icon="☁️")
    
    st.markdown("---")
    
    # 1. Seletor do "Dia de Análise" (Para os KPIs)
    st.header("1. Data de Análise (KPIs)")
    if not df_full.empty:
        max_date = df_full.index.max().date()
        min_date = df_full.index.min().date()
        selected_date = st.date_input("Dia Foco:", value=max_date, min_value=min_date, max_value=max_date)
    else:
        selected_date = datetime.now().date()
        min_date = selected_date - timedelta(days=365)
        max_date = selected_date

    st.markdown("---")

    # 2. Filtro de Período para os GRÁFICOS
    st.header("2. Período do Gráfico")
    
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        start_date_graph = st.date_input("De:", value=min_date + timedelta(days=180), min_value=min_date, max_value=max_date)
    with col_d2:
        end_date_graph = st.date_input("Até:", value=max_date, min_value=min_date, max_value=max_date)

# --- FILTRAGEM DO DATAFRAME ---
if start_date_graph > end_date_graph:
    st.error("Erro: A Data Inicial não pode ser maior que a Final.")
    st.stop()

# Cria o DF Filtrado apenas para os gráficos
mask = (df_full.index.date >= start_date_graph) & (df_full.index.date <= end_date_graph)
df_filtered = df_full.loc[mask]

# --- CONTEÚDO PRINCIPAL ---
st.title(f"Monitor de Mercado: {selected_date.strftime('%d/%m/%Y')}")

# KPI CALCULATION
try:
    dia_dados = df_full.loc[pd.Timestamp(selected_date)]
    try:
        dia_anterior = df_full.iloc[df_full.index.get_loc(pd.Timestamp(selected_date)) - 1]
    except:
        dia_anterior = dia_dados
except:
    # Fallback final
    if not df_full.empty:
        dia_dados = df_full.iloc[-1]
        dia_anterior = df_full.iloc[-2]
    else:
        st.error("Sem dados disponíveis.")
        st.stop()

# KPI Display
col1, col2, col3, col4 = st.columns(4)
with col1:
    delta = dia_dados['Dolar'] - dia_anterior['Dolar']
    st.metric("💵 Dólar (USD/BRL)", f"R$ {dia_dados['Dolar']:.3f}", f"{delta:.3f}")
with col2:
    delta = dia_dados['Boi_Gordo'] - dia_anterior['Boi_Gordo']
    st.metric("🐂 Boi Gordo (@)", f"R$ {dia_dados['Boi_Gordo']:.2f}", f"{delta:.2f}")
with col3:
    delta = dia_dados['JBS'] - dia_anterior['JBS']
    st.metric("🏭 Ação JBS (JBSS3)", f"R$ {dia_dados['JBS']:.2f}", f"{delta:.2f}")
with col4:
    # Usa .get para evitar KeyError se a coluna chuva não existir no registro
    chuva = dia_dados.get('Chuva_mm', 0)
    st.metric("🌧️ Precipitação", f"{chuva:.1f} mm")

st.markdown("---")

# --- GRÁFICOS AVANÇADOS (COM ABAS) ---
st.subheader("📈 Análise Técnica & Tendências")

tab_fin, tab_comp, tab_clima, tab_down = st.tabs([
    "📊 Flutuação de Mercado", 
    "⚖️ Comparativo (Dólar x Boi)", 
    "🌦️ Impacto Climático",
    "💾 Downloads"
])

# ABA 1: Visão Geral
with tab_fin:
    st.markdown("##### Evolução de Preços Individuais")
    fig_ind = go.Figure()
    fig_ind.add_trace(go.Scatter(x=df_filtered.index, y=df_filtered['Dolar'], name="Dólar", visible=True, line=dict(color='#2ecc71')))
    fig_ind.add_trace(go.Scatter(x=df_filtered.index, y=df_filtered['Boi_Gordo'], name="Boi Gordo", visible='legendonly', line=dict(color='#8e44ad')))
    fig_ind.add_trace(go.Scatter(x=df_filtered.index, y=df_filtered['JBS'], name="JBS", visible='legendonly', line=dict(color='#e67e22')))
    
    fig_ind.update_layout(template="plotly_white", height=400, hovermode="x unified")
    st.plotly_chart(fig_ind, use_container_width=True)

# ABA 2: Comparativo Direto
with tab_comp:
    st.markdown("##### Dólar vs. Arroba do Boi")
    fig_comp = make_subplots(specs=[[{"secondary_y": True}]])
    fig_comp.add_trace(go.Scatter(x=df_filtered.index, y=df_filtered['Dolar'], name="Dólar (USD)", line=dict(color='#117a65', width=2)), secondary_y=False)
    fig_comp.add_trace(go.Scatter(x=df_filtered.index, y=df_filtered['Boi_Gordo'], name="Boi Gordo (R$)", line=dict(color='#d35400', width=2, dash='dot')), secondary_y=True)
    
    fig_comp.update_layout(template="plotly_white", height=450, hovermode="x unified", yaxis=dict(title="Dólar"), yaxis2=dict(title="Arroba", showgrid=False))
    st.plotly_chart(fig_comp, use_container_width=True)

# ABA 3: Clima (CORRIGIDO)
with tab_clima:
    st.markdown("##### Chuvas no Mato Grosso vs. Preço")
    
    fig_clima = go.Figure()
    
    # Plota Boi
    fig_clima.add_trace(go.Scatter(x=df_filtered.index, y=df_filtered['Boi_Gordo'], name="Preço Arroba (R$)", line=dict(color='#2e7d32')))
    
    # Plota Chuva (Verifica se a coluna existe antes)
    if 'Chuva_mm' in df_filtered.columns:
        fig_clima.add_trace(go.Bar(x=df_filtered.index, y=df_filtered['Chuva_mm'], name="Chuva (mm)", marker_color='#81d4fa', opacity=0.3, yaxis='y2'))
    
    fig_clima.update_layout(
        yaxis=dict(title="Preço Arroba (R$)", side="left"),
        yaxis2=dict(title="Chuva (mm)", side="right", overlaying="y", showgrid=False),
        template="plotly_white", height=400
    )
    st.plotly_chart(fig_clima, use_container_width=True)

# ABA 4: Downloads
with tab_down:
    st.subheader("📂 Central de Engenharia de Dados")
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("📥 Baixar CSV Financeiro", df_fin.to_csv(), "finance_data.csv", "text/csv")
    with c2:
        st.download_button("📥 Baixar CSV Clima", df_clima.to_csv(), "weather_data.csv", "text/csv")

st.markdown("---")
st.caption("AgroData Nexus © 2024 | Powered by Yahoo Finance & Open-Meteo")
