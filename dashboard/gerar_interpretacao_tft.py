import pandas as pd
import requests
import json

def interpretar_previsoes(df_prev, df_series):
    # Dados recentes
    ultimas = df_series.tail(4)
    media_recente = ultimas['casos'].mean()
    
    # Previsoes SRAG
    srag = df_prev[df_prev['modelo'] == 'srag']
    p50_s1 = srag.iloc[0]['p50']
    p50_s4 = srag.iloc[3]['p50']
    tendencia = "aumento" if p50_s4 > p50_s1 else "reducao"
    variacao = abs(p50_s4 - p50_s1) / p50_s1 * 100

    # Influenza
    flu = df_prev[df_prev['modelo'] == 'influenza']
    flu_s1 = flu.iloc[0]['p50']

    # VSR
    vsr = df_prev[df_prev['modelo'] == 'vsr']
    vsr_s1 = vsr.iloc[0]['p50']

    prompt = f"""Você é um especialista em vigilância epidemiológica. 
Analise as previsões do modelo TFT para as próximas 4 semanas no Paraná e gere uma interpretação técnica objetiva em português para gestores de saúde.

Dados:
- Média de casos SRAG nas últimas 4 semanas: {media_recente:.0f} casos/semana
- Previsão SRAG semana +1: {p50_s1:.0f} casos (IC90: {srag.iloc[0]['p10']:.0f}–{srag.iloc[0]['p90']:.0f})
- Previsão SRAG semana +4: {p50_s4:.0f} casos (IC90: {srag.iloc[3]['p10']:.0f}–{srag.iloc[3]['p90']:.0f})
- Tendência: {tendencia} de {variacao:.1f}% entre semana +1 e +4
- Previsão Influenza semana +1: {flu_s1:.0f} casos
- Previsão VSR semana +1: {vsr_s1:.0f} casos

Gere uma interpretação em 3 parágrafos curtos:
1. Situação atual e tendência esperada
2. Agentes virais em circulação
3. Recomendação para gestores

Seja objetivo e direto. Não use markdown."""

    response = requests.post(
        'http://localhost:11434/api/generate',
        json={"model": "divea-biostats", "prompt": prompt, "stream": False},
        timeout=120
    )
    
    return response.json()['response']

if __name__ == '__main__':
    df_prev = pd.read_parquet('/home/valentim/divea/data/processed/previsoes_tft.parquet')
    df_series = pd.read_parquet('/home/valentim/divea/data/processed/series_semanais.parquet')
    
    print("Gerando interpretacao...")
    texto = interpretar_previsoes(df_prev, df_series)
    
    # Salvar
    with open('/home/valentim/divea/data/processed/interpretacao_tft.txt', 'w') as f:
        f.write(texto)
    
    print("Salvo.")
    print("\n" + texto)
