import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- Configuração "Agro Profissional" ---
st.set_page_config(page_title="AgroData Nexus", page_icon="🌾", layout="wide")

st.markdown("""
<style>
    /* Cores: Verde Floresta, Terra e Branco */
    .stApp { background-color: #f4f6f0; color: #2c3e50; }
    
    /* Cabeçalhos */
    h1, h2, h3 { color: #2e7d32 !important; font-family: 'Helvetica Neue', sans-serif; }
    
    /* Metrics Cards */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border-left: 6px solid #2e7d32;
        padding: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    div[data-testid="stMetricLabel"] { color: #666; font-size: 0.9rem; }
    div[data-testid="stMetricValue"] { color: #2e7d32; font-weight: bold; }
    
    /* Botões */
    .stButton>button {
        background-color: #2e7d32; color: white; border-radius: 4px; border: none;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #e8f5e9; border-right: 1px solid #c8e6c9; }
</style>
""", unsafe_allow_html=True)

# --- Funções de API (Backend Real) ---

@st.cache_data
def get_finance_history():
    """Baixa 1 ano de dados financeiros (Yahoo Finance)"""
    # BRL=X: Dólar, JBSS3.SA: JBS, ZC=F: Milho Futuro (Corn)
    tickers = ['BRL=X', 'JBSS3.SA', 'ZC=F']
    try:
        df = yf.download(tickers, period="1y", interval="1d")['Close']
        
        # Correção para evitar erro se a API falhar parcialmente
        if df.empty:
            return pd.DataFrame()
            
        df.columns = ['Dolar', 'JBS', 'Milho']
        
        # Remove timezone para garantir compatibilidade com Open-Meteo
        df.index = df.index.tz_localize(None) 
        
        # Simula Arroba do Boi (Já que B3 não tem API free estável)
        # Lógica: Segue JBS com fator de mercado
        df['Boi_Gordo'] = (df['JBS'] * 8.5) + 50 
        return df
    except Exception as e:
        print(f"Erro Yahoo Finance: {e}")
        return pd.DataFrame()

@st.cache_data
def get_weather_history():
    """Baixa 1 ano de dados climáticos de Sinop-MT (Coração do Agro)"""
    try:
        # Lat/Lon de Sinop, Mato Grosso
        lat, lon = -11.86, -55.50
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        
        url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={start_date}&end_date={end_date}&daily=temperature_2m_max,precipitation_sum&timezone=America%2FSao_Paulo"
        
        res = requests.get(url)
        data = res.json()
        
        if 'daily' not in data:
            return pd.DataFrame()

        df = pd.DataFrame({
            'Date': data['daily']['time'],
            'Temp_Max': data['daily']['temperature_2m_max'],
            'Chuva_mm': data['daily']['precipitation_sum']
        })
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
        return df
    except Exception as e:
        print(f"Erro Open-Meteo: {e}")
        return pd.DataFrame()

# --- Carga e Processamento de Dados ---

df_fin = get_finance_history()
df_clima = get_weather_history()

# Merge dos dados (Inner Join por data)
# Se uma das APIs falhar, criamos um DF vazio para não quebrar o app
if not df_fin.empty and not df_clima.empty:
    df_full = pd.concat([df_fin, df_clima], axis=1).dropna()
else:
    df_full = pd.DataFrame()

# --- Interface ---

# Sidebar: Navegação Temporal
with st.sidebar:
    st.image("https://img.icons8.com/dusk/96/tractor.png", width=80)
    st.title("AgroData Nexus")
    st.markdown("---")
    st.header("📅 Navegação Temporal")
    
    # --- CORREÇÃO DE SEGURANÇA (Evita erro NaT) ---
    if df_full.empty:
        st.warning("⚠️ Dados insuficientes. Verifique a conexão com as APIs.")
        # Define hoje como padrão para não quebrar
        selected_date = datetime.now().date()
        dados_disponiveis = False
    else:
        min_date = df_full.index.min().date()
        max_date = df_full.index.max().date()
        selected_date = st.date_input("Analise o dia:", value=max_date, min_value=min_date, max_value=max_date)
        dados_disponiveis = True

# --- Conteúdo Principal ---
st.title(f"Monitor de Mercado: {selected_date.strftime('%d/%m/%Y')}")

if not dados_disponiveis:
    st.error("Não foi possível carregar os dados financeiros ou climáticos. Tente recarregar a página.")
    st.stop() # Para a execução aqui se não tiver dados

# Filtra o dia selecionado
try:
    dia_dados = df_full.loc[pd.Timestamp(selected_date)]
    
    # Tenta pegar o dia anterior para calcular Delta (Variação)
    # Se for o primeiro dia do dataset, usa o próprio dia (delta zero)
    try:
        dia_anterior = df_full.loc[pd.Timestamp(selected_date) - timedelta(days=1)]
    except:
        dia_anterior = dia_dados

except KeyError:
    st.warning("Mercado fechado nesta data (Fim de semana/Feriado). Mostrando dados mais recentes disponíveis.")
    dia_dados = df_full.iloc[-1]
    dia_anterior = df_full.iloc[-2]

# 1. Painel de KPIs (Financeiro + Climático)
col1, col2, col3, col4 = st.columns(4)

with col1:
    delta_dol = dia_dados['Dolar'] - dia_anterior['Dolar']
    st.metric("💵 Dólar (USD/BRL)", f"R$ {dia_dados['Dolar']:.3f}", f"{delta_dol:.3f}")

with col2:
    delta_boi = dia_dados['Boi_Gordo'] - dia_anterior['Boi_Gordo']
    st.metric("🐂 Boi Gordo (Simulado)", f"R$ {dia_dados['Boi_Gordo']:.2f}", f"{delta_boi:.2f}")

with col3:
    st.metric("🌡️ Temp. Máx (Sinop-MT)", f"{dia_dados['Temp_Max']} °C")

with col4:
    chuva = dia_dados['Chuva_mm']
    # Cor do delta: Azul se choveu, Cinza se seco
    st.metric("🌧️ Precipitação (Chuva)", f"{chuva} mm")

st.markdown("---")

# 2. Gráficos de Correlação (Plotly)
st.subheader("📊 Correlação: Clima x Mercado")
st.caption("Analise se a falta de chuvas impactou o preço das commodities.")

tab1, tab2 = st.tabs(["Visão Gráfica", "Downloads (Data Lake)"])

with tab1:
    # Gráfico com Eixo Duplo (Preço x Chuva)
    fig = go.Figure()
    
    # Linha do Boi (Eixo Esquerdo)
    fig.add_trace(go.Scatter(
        x=df_full.index, y=df_full['Boi_Gordo'],
        name="Preço Boi Gordo (R$)", line=dict(color='#2e7d32', width=2)
    ))
    
    # Barras de Chuva (Eixo Direito)
    fig.add_trace(go.Bar(
        x=df_full.index, y=df_full['Chuva_mm'],
        name="Chuva (mm)", marker_color='#81d4fa', opacity=0.3, yaxis='y2'
    ))
    
    fig.update_layout(
        title="Histórico: Preço do Boi vs. Chuvas no Mato Grosso",
        yaxis=dict(title="Preço Arroba (R$)", side="left"),
        yaxis2=dict(title="Precipitação (mm)", side="right", overlaying="y", showgrid=False),
        template="plotly_white",
        height=450,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("📂 Central de Engenharia de Dados")
    st.info("Baixe os datasets brutos para realizar a carga no seu Banco de Dados SQL.")
    
    c_down1, c_down2 = st.columns(2)
    
    with c_down1:
        csv_fin = df_fin.to_csv().encode('utf-8')
        st.download_button(
            label="📥 Baixar Dados Financeiros (B3/Yahoo)",
            data=csv_fin,
            file_name="finance_data_raw.csv",
            mime="text/csv"
        )
    
    with c_down2:
        csv_clima = df_clima.to_csv().encode('utf-8')
        st.download_button(
            label="📥 Baixar Dados Climáticos (Open-Meteo)",
            data=csv_clima,
            file_name="weather_sinop_raw.csv",
            mime="text/csv"
        )
