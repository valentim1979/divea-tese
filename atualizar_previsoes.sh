#!/bin/bash
echo "=== Atualizando previsoes TFT ==="
conda activate divea
cd ~/divea/dashboard
python gerar_previsoes_tft.py
echo "=== Concluido ==="
echo "Gerando interpretacao..."
python ~/divea/dashboard/gerar_interpretacao_tft.py
