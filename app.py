import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
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

# --- FUNÇÕES DE DADOS ---

def gerar_dados_financeiros_fake():
    """Gera dados simulados se tudo falhar"""
    datas = pd.date_range(end=datetime.now(), periods=365, freq='B')
    n = len(datas)
    dolar = 5.0 + np.cumsum(np.random.normal(0, 0.05, n))
    jbs = 25.0 + np.cumsum(np.random.normal(0, 0.5, n))
    df = pd.DataFrame({'Dolar': dolar, 'JBS': jbs}, index=datas)
    df['Boi_Gordo'] = (df['JBS'] * 8.5) + 50 + np.random.normal(0, 2, n)
    return df

def gerar_dados_clima_fake():
    """Gera clima simulado se tudo falhar"""
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
        df = yf.download(tickers, period="2y", interval="1d", progress=False)['Close']
        if df.empty or len(df) < 10: raise Exception("Dados vazios")
        
        df.columns = ['Dolar', 'JBS']
        df.index = df.index.tz_localize(None) 
        df['Boi_Gordo'] = (df['JBS'] * 8.5) + 50 
        return df, True
    except:
        return gerar_dados_financeiros_fake(), False

@st.cache_data
def get_weather_history():
    try:
        lat, lon = -11.86, -55.50 # Sinop-MT
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')
        
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

# --- CARGA E TRATAMENTO DE DADOS ---
df_fin, status_fin = get_finance_history()
df_clima, status_clima = get_weather_history()

try:
    # Outer Join para manter tudo
    df_full = pd.concat([df_fin, df_clima], axis=1).sort_index()
    
    # Preenchimentos
    df_full['Dolar'] = df_full['Dolar'].ffill()
    df_full['JBS'] = df_full['JBS'].ffill()
    df_full['Boi_Gordo'] = df_full['Boi_Gordo'].ffill()
    df_full['Chuva_mm'] = df_full['Chuva_mm'].fillna(0)
    df_full['Temp_Max'] = df_full['Temp_Max'].ffill()
    
    df_full = df_full.dropna() # Remove sobras do início
except:
    df_full = pd.DataFrame()

# --- TRAVA DE SEGURANÇA (O PULO DO GATO) ---
# Se o dataframe estiver vazio, paramos o app AQUI.
# Isso impede o erro "iloc[-1]" lá na frente.
if df_full.empty:
    st.warning("⚠️ Falha na conexão com APIs e na geração de backup.")
    st.info("Tentando regenerar dados simulados de emergência...")
    df_full = gerar_dados_financeiros_fake()
    # Se mesmo assim falhar (muito raro):
    if df_full.empty:
        st.error("Erro Crítico: Não há dados para exibir. Recarregue a página.")
        st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.image("https://img.icons8.com/dusk/96/tractor.png", width=80)
    st.title("AgroData Nexus")
    
    if not status_fin: st.toast("Modo Simulação (Financeiro)", icon="⚠️")
    if not status_clima: st.toast("Modo Simulação (Clima)", icon="☁️")
    
    st.markdown("---")
    
    # Definição segura de datas
    max_date = df_full.index.max().date()
    min_date = df_full.index.min().date()

    # 1. Seletor de Data
    st.header("1. Análise Pontual")
    selected_date = st.date_input("Dia Foco:", value=max_date, min_value=min_date, max_value=max_date)

    st.markdown("---")

    # 2. Filtro Gráfico (Lógica Corrigida)
    st.header("2. Período Gráfico")
    
    # Valor padrão: Últimos 180 dias (se houver dados suficientes)
    default_start = max_date - timedelta(days=180)
    if default_start < min_date:
        default_start = min_date
        
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        start_date_graph = st.date_input("De:", value=default_start, min_value=min_date, max_value=max_date)
    with col_d2:
        end_date_graph = st.date_input("Até:", value=max_date, min_value=min_date, max_value=max_date)

if start_date_graph > end_date_graph:
    st.error("Data Inicial maior que Final.")
    st.stop()

# Filtro
mask = (df_full.index.date >= start_date_graph) & (df_full.index.date <= end_date_graph)
df_filtered = df_full.loc[mask]

# --- KPI CALCULATION ---
try:
    ts_selected = pd.Timestamp(selected_date)
    # Tenta achar o índice exato ou anterior
    idx = df_full.index.get_indexer([ts_selected], method='ffill')[0]
    
    if idx == -1: # Se data selecionada for antes do início do df
        idx = 0
        
    dia_dados = df_full.iloc[idx]
    dia_anterior = df_full.iloc[idx - 1] if idx > 0 else dia_dados

except Exception as e:
    # Se der qualquer erro aqui, pega o último dia disponível com segurança
    dia_dados = df_full.iloc[-1]
    dia_anterior = df_full.iloc[-2] if len(df_full) > 1 else dia_dados

# --- DASHBOARD ---
st.title(f"Monitor de Mercado: {selected_date.strftime('%d/%m/%Y')}")

col1, col2, col3, col4 = st.columns(4)
def safe_metric(label, current, prev, prefix="R$ "):
    try:
        val = float(current)
        d = float(current) - float(prev)
        st.metric(label, f"{prefix}{val:.2f}", f"{d:.2f}")
    except:
        st.metric(label, "N/A", "0.00")

with col1: safe_metric("💵 Dólar", dia_dados['Dolar'], dia_anterior['Dolar'])
with col2: safe_metric("🐂 Boi Gordo", dia_dados['Boi_Gordo'], dia_anterior['Boi_Gordo'])
with col3: safe_metric("🏭 JBS (JBSS3)", dia_dados['JBS'], dia_anterior['JBS'])
with col4: 
    chuva = dia_dados.get('Chuva_mm', 0)
    st.metric("🌧️ Chuva", f"{chuva:.1f} mm")

st.markdown("---")

# --- ABAS E GRÁFICOS ---
tab1, tab2, tab3, tab4 = st.tabs(["Tendências", "Volatilidade", "Correlações", "Downloads"])

with tab1:
    st.subheader("Evolução Temporal")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_filtered.index, y=df_filtered['Dolar'], name="Dólar", line=dict(color='#2ecc71')))
    fig.add_trace(go.Scatter(x=df_filtered.index, y=df_filtered['Boi_Gordo'], name="Boi Gordo", visible='legendonly', line=dict(color='#8e44ad')))
    fig.update_layout(height=400, template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("Análise de Risco (Boxplot Mensal)")
    df_box = df_filtered.copy()
    df_box['Mes'] = df_box.index.strftime('%Y-%m')
    opt = st.radio("Ativo:", ["Boi_Gordo", "Dolar", "JBS"], horizontal=True)
    fig_box = px.box(df_box, x="Mes", y=opt, points="all", color_discrete_sequence=['#2e7d32'])
    st.plotly_chart(fig_box, use_container_width=True)

with tab3:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Dispersão: Dólar x Boi")
        fig_scat = px.scatter(df_filtered, x="Dolar", y="Boi_Gordo", trendline="ols", title="Correlação", color="Chuva_mm")
        st.plotly_chart(fig_scat, use_container_width=True)
    with c2:
        st.subheader("Matriz de Correlação")
        cols_corr = ['Dolar', 'Boi_Gordo', 'JBS', 'Chuva_mm', 'Temp_Max']
        # Garante que as colunas existem antes de correlacionar
        cols_existentes = [c for c in cols_corr if c in df_filtered.columns]
        corr = df_filtered[cols_existentes].corr()
        fig_heat = px.imshow(corr, text_auto=True, color_continuous_scale="RdBu_r")
        st.plotly_chart(fig_heat, use_container_width=True)

with tab4:
    st.info("Download de Dados")
    st.download_button("📥 CSV Completo", df_full.to_csv(), "agro_data.csv", "text/csv")
