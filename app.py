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

# --- FUNÇÕES GERADORAS DE DADOS (FALLBACK) ---

def gerar_dados_financeiros_fake():
    """Gera dados simulados se a API falhar"""
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

# --- FUNÇÕES DE API (CACHED) ---

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

# --- CARGA E MERGE DE DADOS ---
df_fin, status_fin = get_finance_history()
df_clima, status_clima = get_weather_history()

try:
    # Merge mantendo todas as datas (Outer Join)
    df_full = pd.concat([df_fin, df_clima], axis=1).sort_index()
    
    # Tratamento de Nulos
    df_full['Dolar'] = df_full['Dolar'].ffill()
    df_full['JBS'] = df_full['JBS'].ffill()
    df_full['Boi_Gordo'] = df_full['Boi_Gordo'].ffill()
    df_full['Chuva_mm'] = df_full['Chuva_mm'].fillna(0) # Se não tem dado de chuva, assume 0
    df_full['Temp_Max'] = df_full['Temp_Max'].ffill()
    
    # Garante que colunas existam mesmo se API falhar
    if 'Chuva_mm' not in df_full.columns: df_full['Chuva_mm'] = 0.0
    
    df_full = df_full.dropna() # Remove dias iniciais sem histórico
except:
    df_full = pd.DataFrame()

# TRAVA DE SEGURANÇA FINAL (Se tudo falhar, gera fake de novo)
if df_full.empty:
    df_full = gerar_dados_financeiros_fake()
    df_full['Chuva_mm'] = 0.0
    df_full['Temp_Max'] = 30.0

# --- SIDEBAR (NAVEGAÇÃO E FILTROS) ---
with st.sidebar:
    st.image("https://img.icons8.com/dusk/96/tractor.png", width=80)
    st.title("AgroData Nexus")
    
    if not status_fin: st.toast("⚠️ Dados Financeiros: Modo Simulação", icon="⚠️")
    if not status_clima: st.toast("⚠️ Dados Climáticos: Modo Simulação", icon="☁️")
    
    st.markdown("---")
    
    # Define limites de data com segurança
    max_date = df_full.index.max().date()
    min_date = df_full.index.min().date()

    # 1. Seletor de Data de Análise (KPIs)
    st.header("1. Data de Análise (KPIs)")
    selected_date = st.date_input("Dia Foco:", value=max_date, min_value=min_date, max_value=max_date)

    st.markdown("---")

    # 2. Filtro de Período para os GRÁFICOS
    st.header("2. Período do Gráfico")
    
    # Lógica de segurança para data padrão
    # Tenta pegar 180 dias atrás. Se for menor que o min_date, usa min_date
    default_start = max_date - timedelta(days=180)
    if default_start < min_date:
        default_start = min_date

    col_d1, col_d2 = st.columns(2)
    with col_d1:
        start_date_graph = st.date_input("De:", value=default_start, min_value=min_date, max_value=max_date)
    with col_d2:
        end_date_graph = st.date_input("Até:", value=max_date, min_value=min_date, max_value=max_date)

# Validação do Filtro
if start_date_graph > end_date_graph:
    st.error("Erro: Data Inicial maior que Final.")
    st.stop()

# Aplica Filtro para Gráficos
mask = (df_full.index.date >= start_date_graph) & (df_full.index.date <= end_date_graph)
df_filtered = df_full.loc[mask]

# --- CÁLCULO DE KPIs ---
try:
    # Tenta encontrar o índice da data selecionada ou o anterior mais próximo
    ts_selected = pd.Timestamp(selected_date)
    idx = df_full.index.get_indexer([ts_selected], method='ffill')[0]
    
    if idx == -1: idx = 0 # Segurança se data for muito antiga
        
    dia_dados = df_full.iloc[idx]
    dia_anterior = df_full.iloc[idx - 1] if idx > 0 else dia_dados
except:
    # Fallback extremo
    dia_dados = df_full.iloc[-1]
    dia_anterior = df_full.iloc[-2]

# --- DASHBOARD ---
st.title(f"Monitor de Mercado: {selected_date.strftime('%d/%m/%Y')}")

# Exibição de Métricas
col1, col2, col3, col4 = st.columns(4)
def safe_metric(label, val_curr, val_prev, prefix="R$ "):
    try:
        curr = float(val_curr)
        delta = curr - float(val_prev)
        st.metric(label, f"{prefix}{curr:.2f}", f"{delta:.2f}")
    except:
        st.metric(label, "N/A", "0.00")

with col1: safe_metric("💵 Dólar", dia_dados['Dolar'], dia_anterior['Dolar'])
with col2: safe_metric("🐂 Boi Gordo", dia_dados['Boi_Gordo'], dia_anterior['Boi_Gordo'])
with col3: safe_metric("🏭 JBS (JBSS3)", dia_dados['JBS'], dia_anterior['JBS'])
with col4: 
    chuva = dia_dados.get('Chuva_mm', 0)
    st.metric("🌧️ Chuva", f"{chuva:.1f} mm")

st.markdown("---")

# --- ABAS DE GRÁFICOS ---
st.subheader("📈 Inteligência de Mercado")

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Tendências", 
    "📦 Volatilidade (Risco)", 
    "🧲 Correlações",
    "💾 Downloads"
])

# 1. TENDÊNCIAS
with tab1:
    fig_ind = go.Figure()
    fig_ind.add_trace(go.Scatter(x=df_filtered.index, y=df_filtered['Dolar'], name="Dólar", line=dict(color='#2ecc71')))
    fig_ind.add_trace(go.Scatter(x=df_filtered.index, y=df_filtered['Boi_Gordo'], name="Boi Gordo", visible='legendonly', line=dict(color='#8e44ad')))
    fig_ind.update_layout(height=400, template="plotly_white")
    st.plotly_chart(fig_ind, use_container_width=True)

# 2. VOLATILIDADE (Boxplot)
with tab2:
    st.caption("Distribuição de preços por mês (Identificação de Risco)")
    df_box = df_filtered.copy()
    df_box['Mes'] = df_box.index.strftime('%Y-%m')
    opt = st.radio("Ativo:", ["Boi_Gordo", "Dolar", "JBS"], horizontal=True)
    
    fig_box = px.box(df_box, x="Mes", y=opt, points="all", color_discrete_sequence=['#2e7d32'])
    st.plotly_chart(fig_box, use_container_width=True)

# 3. CORRELAÇÕES (Com Try/Except para evitar erro OLS)
with tab3:
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("Dispersão: Dólar x Boi")
        try:
            # Tenta criar com linha de tendência (requer statsmodels)
            fig_scat = px.scatter(df_filtered, x="Dolar", y="Boi_Gordo", 
                                 trendline="ols", 
                                 title="Correlação (Com Tendência)", 
                                 color="Chuva_mm")
        except Exception as e:
            # Se falhar (falta de lib ou dados sujos), cria simples
            fig_scat = px.scatter(df_filtered, x="Dolar", y="Boi_Gordo", 
                                 title="Correlação (Simples)", 
                                 color="Chuva_mm")
            
        st.plotly_chart(fig_scat, use_container_width=True)

    with c2:
        st.subheader("Matriz de Correlação")
        cols = ['Dolar', 'Boi_Gordo', 'JBS', 'Chuva_mm', 'Temp_Max']
        cols_validas = [c for c in cols if c in df_filtered.columns]
        
        if len(cols_validas) > 1:
            corr = df_filtered[cols_validas].corr()
            fig_heat = px.imshow(corr, text_auto=True, color_continuous_scale="RdBu_r")
            st.plotly_chart(fig_heat, use_container_width=True)
        else:
            st.info("Dados insuficientes para correlação.")

# 4. DOWNLOADS
with tab4:
    st.info("Central de Engenharia de Dados")
    c_dw1, c_dw2 = st.columns(2)
    with c_dw1: st.download_button("📥 CSV Financeiro", df_fin.to_csv(), "finance.csv", "text/csv")
    with c_dw2: st.download_button("📥 CSV Clima", df_clima.to_csv(), "weather.csv", "text/csv")
