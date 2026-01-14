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
    
    /* Metrics Cards com tratamento de erro visual */
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
    datas = pd.date_range(end=datetime.now(), periods=365, freq='B')
    n = len(datas)
    dolar = 5.0 + np.cumsum(np.random.normal(0, 0.05, n))
    jbs = 25.0 + np.cumsum(np.random.normal(0, 0.5, n))
    df = pd.DataFrame({'Dolar': dolar, 'JBS': jbs}, index=datas)
    df['Boi_Gordo'] = (df['JBS'] * 8.5) + 50 + np.random.normal(0, 2, n)
    return df

def gerar_dados_clima_fake():
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

# --- CARGA E TRATAMENTO (CORREÇÃO DO NAN) ---
df_fin, status_fin = get_finance_history()
df_clima, status_clima = get_weather_history()

try:
    # 1. Merge (Outer Join para não perder dias de chuva só pq é domingo)
    df_full = pd.concat([df_fin, df_clima], axis=1)
    
    # 2. Ordena por data
    df_full = df_full.sort_index()
    
    # 3. CORREÇÃO CRÍTICA: Forward Fill (Repete o preço de sexta no sábado/domingo)
    df_full['Dolar'] = df_full['Dolar'].ffill()
    df_full['JBS'] = df_full['JBS'].ffill()
    df_full['Boi_Gordo'] = df_full['Boi_Gordo'].ffill()
    
    # 4. Preenche Clima vazio com 0
    df_full['Chuva_mm'] = df_full['Chuva_mm'].fillna(0)
    df_full['Temp_Max'] = df_full['Temp_Max'].fillna(method='ffill')
    
    # 5. Remove linhas que continuam vazias (início do dataset)
    df_full = df_full.dropna()

except:
    df_full = df_fin.copy() # Fallback

# --- # --- SUBSTIRUIR A PARTE DA SIDEBAR POR ESTE BLOCO CORRIGIDO ---

with st.sidebar:
    st.image("https://img.icons8.com/dusk/96/tractor.png", width=80)
    st.title("AgroData Nexus")
    
    if not status_fin: st.toast("⚠️ Financeiro: Modo Simulação", icon="⚠️")
    if not status_clima: st.toast("⚠️ Clima: Modo Simulação", icon="☁️")
    
    st.markdown("---")
    
    # Validação de Datas para evitar erros
    if not df_full.empty:
        max_date = df_full.index.max().date()
        min_date = df_full.index.min().date()
    else:
        # Fallback total de segurança
        max_date = datetime.now().date()
        min_date = max_date - timedelta(days=30)

    # 1. Seletor de Data de Análise (KPIs)
    st.header("1. Data de Análise (KPIs)")
    selected_date = st.date_input("Dia Foco:", value=max_date, min_value=min_date, max_value=max_date)

    st.markdown("---")

    # 2. Filtro de Período para os GRÁFICOS
    st.header("2. Período do Gráfico")
    
    # --- LÓGICA DE SEGURANÇA PARA O VALOR PADRÃO ---
    # Tentamos mostrar os últimos 180 dias. 
    # Se a base for menor que 180 dias, usamos a data mínima como início.
    default_start_value = max_date - timedelta(days=180)
    if default_start_value < min_date:
        default_start_value = min_date

    col_d1, col_d2 = st.columns(2)
    with col_d1:
        start_date_graph = st.date_input("De:", value=default_start_value, min_value=min_date, max_value=max_date)
    with col_d2:
        end_date_graph = st.date_input("Até:", value=max_date, min_value=min_date, max_value=max_date)

# --- FIM DA CORREÇÃO ---

if start_date_graph > end_date_graph:
    st.error("Erro: Data Inicial maior que Final.")
    st.stop()

# Filtra DF para gráficos
mask = (df_full.index.date >= start_date_graph) & (df_full.index.date <= end_date_graph)
df_filtered = df_full.loc[mask]

# --- KPI CALCULATION (BLINDADO) ---
try:
    # Garante que selected_date seja timestamp compatível
    ts_selected = pd.Timestamp(selected_date)
    
    # Tenta achar o índice exato ou o mais próximo anterior (asof)
    idx_loc = df_full.index.get_indexer([ts_selected], method='ffill')[0]
    
    dia_dados = df_full.iloc[idx_loc]
    dia_anterior = df_full.iloc[idx_loc - 1] if idx_loc > 0 else dia_dados

except:
    dia_dados = df_full.iloc[-1]
    dia_anterior = df_full.iloc[-2]

# --- DASHBOARD ---
st.title(f"Monitor de Mercado: {selected_date.strftime('%d/%m/%Y')}")

# KPIs
col1, col2, col3, col4 = st.columns(4)

def safe_metric(label, current, prev, format_str="R$ {:.2f}"):
    try:
        val = float(current)
        delta = float(current) - float(prev)
        return st.metric(label, format_str.format(val), f"{delta:.2f}")
    except:
        return st.metric(label, "N/A", "0.00")

with col1: safe_metric("💵 Dólar (USD/BRL)", dia_dados['Dolar'], dia_anterior['Dolar'], "R$ {:.3f}")
with col2: safe_metric("🐂 Boi Gordo (@)", dia_dados['Boi_Gordo'], dia_anterior['Boi_Gordo'])
with col3: safe_metric("🏭 Ação JBS (JBSS3)", dia_dados['JBS'], dia_anterior['JBS'])
with col4: 
    chuva = dia_dados.get('Chuva_mm', 0)
    st.metric("🌧️ Precipitação", f"{chuva:.1f} mm")

st.markdown("---")

# --- VISUALIZAÇÕES AVANÇADAS ---
st.subheader("📈 Inteligência de Mercado")

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Tendências & Comparativos", 
    "📦 Volatilidade (Boxplot)", 
    "🧲 Correlações (Scatter/Heatmap)",
    "💾 Downloads"
])

# 1. TENDÊNCIAS
with tab1:
    col_g1, col_g2 = st.columns([3, 1])
    with col_g1:
        st.markdown("**Evolução Temporal**")
        fig_ind = go.Figure()
        fig_ind.add_trace(go.Scatter(x=df_filtered.index, y=df_filtered['Dolar'], name="Dólar", line=dict(color='#2ecc71')))
        fig_ind.add_trace(go.Scatter(x=df_filtered.index, y=df_filtered['Boi_Gordo'], name="Boi Gordo", visible='legendonly', line=dict(color='#8e44ad')))
        fig_ind.update_layout(template="plotly_white", height=350, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig_ind, use_container_width=True)
    
    with col_g2:
        st.markdown("**Resumo do Período**")
        if not df_filtered.empty:
            media_boi = df_filtered['Boi_Gordo'].mean()
            max_dolar = df_filtered['Dolar'].max()
            st.info(f"Média Arroba: R$ {media_boi:.2f}")
            st.info(f"Máxima Dólar: R$ {max_dolar:.2f}")
            st.info(f"Dias de Chuva: {len(df_filtered[df_filtered['Chuva_mm'] > 0])}")

# 2. BOXPLOT (NOVO!)
with tab2:
    st.markdown("##### 📦 Análise de Volatilidade (Risco)")
    st.caption("O Boxplot mostra a variação de preço dentro de cada mês. Caixas maiores = Maior instabilidade/risco.")
    
    # Prepara dados para Boxplot (Agrupa por Mês)
    df_box = df_filtered.copy()
    df_box['Mes'] = df_box.index.strftime('%Y-%m')
    
    grafico_opcao = st.radio("Selecione o Ativo para Análise de Risco:", ["Boi_Gordo", "Dólar", "JBS"], horizontal=True)
    
    col_mapping = {"Boi_Gordo": "Boi_Gordo", "Dólar": "Dolar", "JBS": "JBS"}
    col_escolhida = col_mapping[grafico_opcao]
    
    fig_box = px.box(df_box, x="Mes", y=col_escolhida, points="all", color_discrete_sequence=['#2e7d32'])
    fig_box.update_layout(template="plotly_white", height=400)
    st.plotly_chart(fig_box, use_container_width=True)

# 3. CORRELAÇÃO (NOVO!)
with tab3:
    col_c1, col_c2 = st.columns(2)
    
    with col_c1:
        st.markdown("##### 🧲 Dispersão: Dólar vs Boi")
        st.caption("Se formar uma linha subindo, indica correlação positiva (Dólar sobe, Boi sobe).")
        
        fig_scat = px.scatter(df_filtered, x="Dolar", y="Boi_Gordo", 
                             trendline="ols", # Adiciona Linha de Tendência
                             color="Chuva_mm", # Pinta bolinha conforme chuva
                             title="Impacto do Câmbio no Preço",
                             labels={"Dolar": "Cotação Dólar (R$)", "Boi_Gordo": "Arroba (R$)"})
        st.plotly_chart(fig_scat, use_container_width=True)
        
    with col_c2:
        st.markdown("##### 🔥 Matriz de Correlação")
        st.caption("1.0 = Correlação Perfeita. 0.0 = Sem relação.")
        
        # Calcula correlação
        corr_matrix = df_filtered[['Dolar', 'Boi_Gordo', 'JBS', 'Chuva_mm', 'Temp_Max']].corr()
        
        fig_heat = px.imshow(corr_matrix, 
                            text_auto=True, 
                            aspect="auto",
                            color_continuous_scale="RdBu_r")
        st.plotly_chart(fig_heat, use_container_width=True)

# 4. DOWNLOADS
with tab4:
    st.subheader("Central de Dados")
    c1, c2 = st.columns(2)
    with c1: st.download_button("📥 Baixar CSV Financeiro", df_fin.to_csv(), "finance.csv", "text/csv")
    with c2: st.download_button("📥 Baixar CSV Clima", df_clima.to_csv(), "weather.csv", "text/csv")
