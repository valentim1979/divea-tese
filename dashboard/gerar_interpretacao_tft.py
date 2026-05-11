import pandas as pd
import requests

def chamar_ollama(prompt):
    response = requests.post(
        'http://localhost:11434/api/generate',
        json={"model": "divea-biostats", "prompt": prompt, "stream": False},
        timeout=180
    )
    return response.json()['response']

def interpretar_parana(df_prev, df_series):
    ultimas = df_series.tail(4)
    media_recente = ultimas['casos'].mean()
    srag = df_prev[df_prev['modelo'] == 'srag']
    flu = df_prev[df_prev['modelo'] == 'influenza']
    vsr = df_prev[df_prev['modelo'] == 'vsr']
    p50_s1 = srag.iloc[0]['p50']
    p50_s4 = srag.iloc[3]['p50']
    tendencia = "aumento" if p50_s4 > p50_s1 else "reducao"
    variacao = abs(p50_s4 - p50_s1) / p50_s1 * 100

    prompt = f"""Você é especialista em vigilância epidemiológica.
Analise as previsões TFT para as próximas 4 semanas no Paraná e gere interpretação técnica objetiva em português para gestores de saúde.

Dados Paraná:
- Média SRAG últimas 4 semanas: {media_recente:.0f} casos/semana
- Previsão SRAG semana +1: {p50_s1:.0f} casos (IC90: {srag.iloc[0]['p10']:.0f}–{srag.iloc[0]['p90']:.0f})
- Previsão SRAG semana +4: {p50_s4:.0f} casos (IC90: {srag.iloc[3]['p10']:.0f}–{srag.iloc[3]['p90']:.0f})
- Tendência: {tendencia} de {variacao:.1f}% entre semana +1 e +4
- Previsão Influenza semana +1: {flu.iloc[0]['p50']:.0f} casos
- Previsão VSR semana +1: {vsr.iloc[0]['p50']:.0f} casos

Gere interpretação em 3 parágrafos curtos:
1. Situação atual e tendência esperada no Paraná
2. Agentes virais em circulação
3. Recomendação para gestores estaduais

Seja objetivo. Não use markdown."""
    return chamar_ollama(prompt)

def interpretar_15rs(df_prev, df_series_15rs):
    ultimas = df_series_15rs.tail(4)
    media_recente = ultimas['casos'].mean()
    srag = df_prev[df_prev['modelo'] == 'srag']
    flu = df_prev[df_prev['modelo'] == 'influenza']
    vsr = df_prev[df_prev['modelo'] == 'vsr']
    p50_s1 = srag.iloc[0]['p50']
    p50_s4 = srag.iloc[3]['p50']
    tendencia = "aumento" if p50_s4 > p50_s1 else "reducao"
    variacao = abs(p50_s4 - p50_s1) / p50_s1 * 100

    prompt = f"""Você é especialista em vigilância epidemiológica.
Analise as previsões TFT para as próximas 4 semanas na 15ª Regional de Saúde de Maringá (30 municípios) e gere interpretação técnica objetiva em português para gestores regionais.

Dados 15ª RS Maringá:
- Média SRAG últimas 4 semanas na regional: {media_recente:.0f} casos/semana
- Previsão SRAG semana +1 (referência Paraná): {p50_s1:.0f} casos (IC90: {srag.iloc[0]['p10']:.0f}–{srag.iloc[0]['p90']:.0f})
- Previsão SRAG semana +4: {p50_s4:.0f} casos
- Tendência: {tendencia} de {variacao:.1f}%
- Previsão Influenza semana +1: {flu.iloc[0]['p50']:.0f} casos
- Previsão VSR semana +1: {vsr.iloc[0]['p50']:.0f} casos

Gere interpretação em 3 parágrafos curtos:
1. Situação atual e tendência esperada na 15ª RS
2. Agentes virais em circulação na regional
3. Recomendação para gestores da 15ª RS de Maringá

Seja objetivo. Não use markdown."""
    return chamar_ollama(prompt)

if __name__ == '__main__':
    df_prev = pd.read_parquet('/home/valentim/divea/data/processed/previsoes_tft.parquet')
    df_series = pd.read_parquet('/home/valentim/divea/data/processed/series_semanais.parquet')
    df_series_15rs = pd.read_parquet('/home/valentim/divea/data/processed/series_semanais_15rs.parquet')

    print("Gerando interpretacao Parana...")
    texto_pr = interpretar_parana(df_prev, df_series)
    with open('/home/valentim/divea/data/processed/interpretacao_tft.txt', 'w') as f:
        f.write(texto_pr)
    print("Parana salvo.")

    print("Gerando interpretacao 15a RS...")
    texto_15rs = interpretar_15rs(df_prev, df_series_15rs)
    with open('/home/valentim/divea/data/processed/interpretacao_tft_15rs.txt', 'w') as f:
        f.write(texto_15rs)
    print("15a RS salvo.")

    print("\n=== Parana ===")
    print(texto_pr)
    print("\n=== 15a RS ===")
    print(texto_15rs)
