import streamlit as st
import pandas as pd
import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt
import torch
import torch.nn as nn
import sklearn.preprocessing
from libpysal import weights
from esda import Moran_Local

# Configuração
st.set_page_config(
    page_title="DIVEA - Vigilância Epidemiológica",
    page_icon="🦠",
    layout="wide"
)

# Modelo LSTM
class LSTMModel(nn.Module):
    def __init__(self, input_size=1, hidden_size=64, num_layers=2, output_size=4):
        super(LSTMModel, self).__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers,
                           batch_first=True, dropout=0.2)
        self.fc = nn.Linear(hidden_size, output_size)

    def forward(self, x):
        out, _ = self.lstm(x)
        out = self.fc(out[:, -1, :])
        return out

# Funções de carregamento
@st.cache_data
def carregar_dados():
    df = pd.read_parquet('/home/valentim/divea/data/processed/sivep_parana.parquet')
    df['DT_NOTIFIC'] = pd.to_datetime(df['DT_NOTIFIC'], dayfirst=True, errors='coerce')
    return df

@st.cache_data
def carregar_series():
    return pd.read_parquet('/home/valentim/divea/data/processed/series_semanais.parquet')

@st.cache_data
def carregar_shapefile():
    gdf = gpd.read_file('/home/valentim/divea/data/processed/PR_municipios.gpkg')
    gdf['CD_MUN6'] = gdf['code_muni'].astype(int).astype(str).str[:6]
    return gdf

@st.cache_resource
def carregar_modelo(path):
    torch.serialization.add_safe_globals(
        [sklearn.preprocessing._data.MinMaxScaler]
    )
    checkpoint = torch.load(path, map_location='cpu', weights_only=False)
    model = LSTMModel()
    model.load_state_dict(checkpoint['model_state'])
    model.eval()
    return model, checkpoint['scaler']

def prever(serie, model, scaler, janela=12):
    ultima_janela = serie[-janela:].reshape(-1, 1)
    norm = scaler.transform(ultima_janela)
    X = torch.FloatTensor(norm).unsqueeze(0)
    with torch.no_grad():
        pred_norm = model(X).numpy()
    return scaler.inverse_transform(pred_norm)[0]

def classifica(row):
    if not row['lisa_sig']:
        return 'Não significativo'
    labels = {1: 'HH - Alto-Alto', 2: 'LH - Baixo-Alto',
              3: 'LL - Baixo-Baixo', 4: 'HL - Alto-Baixo'}
    return labels[row['lisa_q']]

# Carregar dados
df = carregar_dados()
df_series = carregar_series()
gdf = carregar_shapefile()

# Título
st.title("DIVEA - Dashboard de Vigilância Epidemiológica")
st.markdown("Vigilância de Vírus Respiratórios - Paraná")

# Sidebar
st.sidebar.header("Filtros")
ano = st.sidebar.selectbox("Ano", sorted(df['ANO_ARQUIVO'].unique(), reverse=True))

# Métricas
st.header("Situação Atual")
df_ano = df[df['ANO_ARQUIVO'] == ano]
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total de casos", f"{len(df_ano):,}")
col2.metric("Óbitos", f"{(df_ano['EVOLUCAO'] == '2').sum():,}")
col3.metric("Internações UTI", f"{(df_ano['UTI'] == '1').sum():,}")
col4.metric("Municípios afetados", f"{df_ano['CO_MUN_RES'].nunique():,}")

# Série temporal
st.header("Série Temporal Semanal")
fig, ax = plt.subplots(figsize=(14, 4))
ax.plot(df_series.index, df_series['casos'], color='steelblue', linewidth=1)
ax.set_ylabel("Casos")
ax.set_xlabel("Data")
st.pyplot(fig)
plt.close()

# LISA
st.header("Análise Espacial - Clusters LISA")
df_mun = df_ano.groupby('CO_MUN_RES').size().reset_index(name='casos')
gdf_ano = gdf.merge(df_mun, left_on='CD_MUN6', right_on='CO_MUN_RES', how='left').fillna(0)
w = weights.Queen.from_dataframe(gdf_ano)
w.transform = 'r'
y = gdf_ano['casos'].values
lisa = Moran_Local(y, w)
gdf_ano['lisa_q'] = lisa.q
gdf_ano['lisa_sig'] = lisa.p_sim < 0.05
gdf_ano['cluster'] = gdf_ano.apply(classifica, axis=1)

cores = {
    'HH - Alto-Alto': '#d7191c',
    'HL - Alto-Baixo': '#fdae61',
    'LH - Baixo-Alto': '#abd9e9',
    'LL - Baixo-Baixo': '#2c7bb6',
    'Não significativo': '#f0f0f0'
}
gdf_ano['cor'] = gdf_ano['cluster'].map(cores)

fig, ax = plt.subplots(figsize=(14, 8))
for cluster, cor in cores.items():
    gdf_ano[gdf_ano['cluster'] == cluster].plot(
        ax=ax, color=cor, edgecolor='grey', linewidth=0.3, label=cluster
    )
ax.legend(loc='lower right', fontsize=9)
ax.set_title(f'Clusters espaciais SRAG - {ano}')
ax.axis('off')
st.pyplot(fig)
plt.close()

hh = gdf_ano[gdf_ano['cluster'] == 'HH - Alto-Alto'][['name_muni', 'casos']].sort_values('casos', ascending=False)
if len(hh) > 0:
    st.subheader(f"Municípios em alerta (HH): {len(hh)}")
    st.dataframe(hh.reset_index(drop=True))

# Previsões LSTM
st.header("Previsão - Próximas 4 Semanas")
col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("SRAG Total")
    model_total, scaler_total = carregar_modelo('/home/valentim/divea/models/lstm_srag_total.pt')
    pred_total = prever(df_series['casos'].values, model_total, scaler_total)
    for i, v in enumerate(pred_total):
        st.metric(f"Semana +{i+1}", f"{max(0, int(v)):,}")

with col2:
    st.subheader("Influenza")
    model_flu, scaler_flu = carregar_modelo('/home/valentim/divea/models/lstm_influenza.pt')
    pred_flu = prever(df_series['influenza'].values, model_flu, scaler_flu)
    for i, v in enumerate(pred_flu):
        st.metric(f"Semana +{i+1}", f"{max(0, int(v)):,}")

with col3:
    st.subheader("VSR")
    model_vsr, scaler_vsr = carregar_modelo('/home/valentim/divea/models/lstm_vsr.pt')
    pred_vsr = prever(df_series['vsr'].values, model_vsr, scaler_vsr)
    for i, v in enumerate(pred_vsr):
        st.metric(f"Semana +{i+1}", f"{max(0, int(v)):,}")
        
# Expander TFT
with st.expander("ℹ️ Como funciona a previsão TFT?"):
    st.markdown("""
    **O que é o TFT?** Modelo de IA treinado com dados históricos de SRAG do Paraná (2019-2026).

    **Como prevê?** Analisa as últimas semanas e padrões sazonais para estimar casos nas próximas 4 semanas.

    **Intervalos de confiança (IC90):** 90% de probabilidade do valor real cair entre P10 e P90.

    **Quando atualizar?** Após novos dados do SIVEP-Gripe, rode: `atualizar_previsoes.sh`
    """)

# Previsao TFT
st.header("Previsao TFT — Proximas 4 Semanas")
st.caption("Modelo Temporal Fusion Transformer com intervalos de confianca (P10-P90)")

try:
    df_prev = pd.read_parquet('/home/valentim/divea/data/processed/previsoes_tft.parquet')

    col1, col2, col3 = st.columns(3)

    for col, modelo, titulo in zip(
        [col1, col2, col3],
        ['srag', 'influenza', 'vsr'],
        ['SRAG Total', 'Influenza', 'VSR']
    ):
        df_m = df_prev[df_prev['modelo'] == modelo]
        col.subheader(titulo)
        for _, row in df_m.iterrows():
            col.metric(
                f"Semana {row['data'].strftime('%d/%m')}",
                f"{max(0, row['p50']):.0f} casos",
                f"IC90: {max(0, row['p10']):.0f}–{row['p90']:.0f}"
            )
except Exception as e:
    st.warning(f"Previsoes nao disponiveis: {e}")

# Interpretacao automatica Ollama
st.header("Interpretação Epidemiológica Automatizada")
st.caption("Gerada pelo modelo divea-biostats (Qwen2.5 14B)")

try:
    with open('/home/valentim/divea/data/processed/interpretacao_tft.txt', 'r') as f:
        interpretacao = f.read()
    st.info(interpretacao)
except:
    st.warning("Interpretação não disponível. Rode: python gerar_interpretacao_tft.py")
