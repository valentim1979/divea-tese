import pandas as pd
import numpy as np
import torch
from pytorch_forecasting import TemporalFusionTransformer, TimeSeriesDataSet
from pytorch_forecasting.data import GroupNormalizer
from pytorch_forecasting.metrics import QuantileLoss

def gerar_previsao(serie, janela, modelo_path, nome):
    df = serie.reset_index()
    df.columns = ['data', 'casos']
    df['time_idx'] = range(len(df))
    df['grupo'] = 'parana'
    df['casos'] = df['casos'].astype(float)
    df['semana'] = df['data'].dt.isocalendar().week.astype(str)
    df['mes'] = df['data'].dt.month.astype(str)

    SPLIT = int(len(df) * 0.7)

    treino = TimeSeriesDataSet(
        df[df['time_idx'] <= SPLIT],
        time_idx='time_idx', target='casos', group_ids=['grupo'],
        min_encoder_length=janela, max_encoder_length=janela,
        min_prediction_length=4, max_prediction_length=4,
        time_varying_known_categoricals=['semana', 'mes'],
        time_varying_unknown_reals=['casos'],
        target_normalizer=GroupNormalizer(groups=['grupo'], transformation='softplus'),
        add_relative_time_idx=True, add_target_scales=True, add_encoder_length=True,
    )

    hidden = 64 if nome == 'vsr' else 32
    model = TemporalFusionTransformer.from_dataset(
        treino, hidden_size=hidden, attention_head_size=2,
        dropout=0.1, hidden_continuous_size=16, loss=QuantileLoss(),
    )
    model.load_state_dict(torch.load(modelo_path, map_location='cpu'))
    model.eval()

    # Usar ultimas semanas para previsao
    df_pred = df.copy()
    df_pred['time_idx'] = range(len(df_pred))

    dataset_pred = TimeSeriesDataSet.from_dataset(
        treino, df_pred, predict=True, stop_randomization=True
    )
    loader = dataset_pred.to_dataloader(train=False, batch_size=1, num_workers=0)

    with torch.no_grad():
        for batch in loader:
            x, _ = batch
            out = model(x)
            pred = out['prediction'].cpu().numpy()[0]

    ultima_data = serie.index[-1]
    datas = [ultima_data + pd.Timedelta(weeks=i+1) for i in range(4)]

    resultado = pd.DataFrame({
        'data': datas,
        'p10': pred[:, 0],
        'p25': pred[:, 1],
        'p50': pred[:, 3],
        'p75': pred[:, 4],
        'p90': pred[:, 5],
        'modelo': nome
    })
    return resultado

df_series = pd.read_parquet('/home/valentim/divea/data/processed/series_semanais.parquet')

resultados = []

print("Gerando previsao SRAG...")
r = gerar_previsao(df_series['casos'], 16,
    '/home/valentim/divea/models/tft_srag_total.pt', 'srag')
resultados.append(r)

print("Gerando previsao Influenza...")
serie_flu = df_series['influenza'].copy()
serie_flu = serie_flu[(serie_flu.index < '2020-01-01') | (serie_flu.index >= '2022-01-01')]
r = gerar_previsao(serie_flu, 8,
    '/home/valentim/divea/models/tft_influenza.pt', 'influenza')
resultados.append(r)

print("Gerando previsao VSR...")
r = gerar_previsao(df_series['vsr'], 16,
    '/home/valentim/divea/models/tft_vsr.pt', 'vsr')
resultados.append(r)

df_prev = pd.concat(resultados, ignore_index=True)
df_prev.to_parquet('/home/valentim/divea/data/processed/previsoes_tft.parquet', index=False)
print("Previsoes salvas.")
print(df_prev)