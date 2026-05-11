import streamlit as st
import pandas as pd
import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt
from libpysal import weights
from esda import Moran_Local

st.set_page_config(
    page_title="15ª RS — Vigilância SRAG",
    page_icon="🏥",
    layout="wide"
)

# Carregar dados
@st.cache_data
def carregar_dados():
    df = pd.read_parquet('/home/valentim/divea/data/processed/sivep_15rs.parquet')
    return df

@st.cache_data
def carregar_series():
    return pd.read_parquet('/home/valentim/divea/data/processed/series_semanais_15rs.parquet')

@st.cache_data
def carregar_canal():
    return pd.read_parquet('/home/valentim/divea/data/processed/canal_endemico_15rs.parquet')

@st.cache_data
def carregar_municipios():
    return pd.read_csv('/home/valentim/divea/data/processed/municipios_15rs.csv')

@st.cache_data
def carregar_shapefile():
    gdf = gpd.read_file('/home/valentim/divea/data/processed/PR_municipios.gpkg')
    gdf['CD_MUN6'] = gdf['code_muni'].astype(int).astype(str).str[:6]
    
    return gdf

df = carregar_dados()
df_series = carregar_series()
canal = carregar_canal()
muns = carregar_municipios()
gdf = carregar_shapefile()
gdf_15rs = gdf[gdf['CD_MUN6'].isin(muns['CD_MUN6'].astype(str))].copy()

# Título
st.title("15ª Regional de Saúde — Vigilância SRAG")
st.markdown("Maringá/PR — 30 municípios")

# Sidebar
st.sidebar.header("Filtros")
ano = st.sidebar.selectbox("Ano", sorted(df['ANO_ARQUIVO'].unique(), reverse=True))
municipio = st.sidebar.selectbox(
    "Município",
    ['Todos'] + sorted(muns['NM_MUN'].tolist())
)

# Filtrar por município
df_ano = df[df['ANO_ARQUIVO'] == ano]
if municipio != 'Todos':
    cod = muns[muns['NM_MUN'] == municipio]['CD_MUN6'].values[0]
    df_ano = df_ano[df_ano['CO_MUN_RES'] == str(cod)]

# Métricas
st.header("Situação Atual")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total de casos", f"{len(df_ano):,}")
col2.metric("Óbitos", f"{(df_ano['EVOLUCAO'] == '2').sum():,}")
col3.metric("Internações UTI", f"{(df_ano['UTI'] == '1').sum():,}")
col4.metric("Municípios afetados", f"{df_ano['CO_MUN_RES'].nunique():,}")

# Canal endêmico
st.header("Canal Endêmico")

df_ano_canal = df[df['ANO_ARQUIVO'] == ano].copy()
if municipio != 'Todos':
    df_ano_canal = df_ano_canal[df_ano_canal['CO_MUN_RES'] == str(cod)]

casos_ano = (
    df_ano_canal.groupby(
        pd.to_numeric(df_ano_canal['SEM_NOT'], errors='coerce')
    )
    .size()
    .reset_index(name='casos')
)
casos_ano.columns = ['semana', 'casos']

fig, ax = plt.subplots(figsize=(14, 5))
ax.fill_between(canal['semana'], canal['limite_inferior'], canal['limite_superior'],
                alpha=0.3, color='green', label='Zona segura')
ax.fill_between(canal['semana'], canal['limite_superior'], canal['alerta'],
                alpha=0.3, color='yellow', label='Zona de alerta')
ax.fill_between(canal['semana'], canal['alerta'], canal['epidemia'],
                alpha=0.3, color='orange', label='Zona de risco')
ax.plot(canal['semana'], canal['media'],
        color='green', linewidth=1, linestyle='--', label='Média histórica')
ax.plot(casos_ano['semana'], casos_ano['casos'],
        color='red', linewidth=2, label=str(ano))
ax.set_xlabel('Semana Epidemiológica')
ax.set_ylabel('Casos')
ax.set_title(f'Canal Endêmico SRAG — {municipio} ({ano})')
ax.legend()
ax.set_xlim(1, 52)
plt.tight_layout()
st.pyplot(fig)
plt.close()

# Mapa 15ª RS
st.header("Distribuição Geográfica")

df_mun = df_ano.groupby('CO_MUN_RES').size().reset_index(name='casos')
df_mun['CO_MUN_RES'] = df_mun['CO_MUN_RES'].astype(str)
gdf_mapa = gdf_15rs.merge(df_mun, left_on='CD_MUN6', right_on='CO_MUN_RES', how='left').fillna(0)

fig, ax = plt.subplots(figsize=(12, 8))
gdf_mapa.plot(column='casos', cmap='YlOrRd', legend=True, ax=ax,
              edgecolor='grey', linewidth=0.5)
ax.set_title(f'Casos SRAG por município — 15ª RS ({ano})')
ax.axis('off')
plt.tight_layout()
st.pyplot(fig)
plt.close()

# Circulação viral
st.header("Circulação Viral")

col1, col2, col3 = st.columns(3)
flu_count = int((df_ano['POS_PCRFLU'] == '1').sum())
col1.metric("Influenza positivo", f"{flu_count:,}")
cov_count = int((df_ano['PCR_SARS2'] == '1').sum())
col2.metric("SARS-CoV-2 detectado", f"{cov_count:,}")
vsr_count = int((df_ano['PCR_VSR'] == '1').sum())
col3.metric("VSR detectado", f"{vsr_count:,}")
vsr_count = int((df_ano['PCR_VSR'] == '1').sum())

# Previsão TFT
st.header("Previsão TFT — Próximas 4 Semanas")

with st.expander("ℹ️ Como funciona a previsão TFT?"):
    st.markdown("""
    **O que é o TFT?** Modelo de IA treinado com dados históricos de SRAG do Paraná (2019-2026).

    **Como prevê?** Analisa as últimas semanas e padrões sazonais para estimar casos nas próximas 4 semanas.

    **Intervalos de confiança (IC90):** 90% de probabilidade do valor real cair entre P10 e P90.

    **Quando atualizar?** Após novos dados do SIVEP-Gripe, rode: `atualizar_previsoes.sh`
    """)

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
                f"{row['p50']:.0f} casos",
                f"IC90: {row['p10']:.0f}–{row['p90']:.0f}"
            )
except Exception as e:
    st.warning(f"Previsões não disponíveis: {e}")

# Interpretacao automatica Ollama
st.header("Interpretação Epidemiológica Automatizada")
st.caption("Gerada pelo modelo divea-biostats (Qwen2.5 14B)")

try:
    with open('/home/valentim/divea/data/processed/interpretacao_tft_15rs.txt', 'r') as f:
        interpretacao = f.read()
    st.info(interpretacao)
except:
    st.warning("Interpretação não disponível. Rode: python gerar_interpretacao_tft.py")
