#!/bin/bash

echo "=== Iniciando DIVEA ==="

# JupyterLab
tmux new-session -d -s jupyter -x 220 -y 50
tmux send-keys -t jupyter "conda activate divea && cd ~/divea && jupyter lab --no-browser --ip=0.0.0.0 --port=8888" Enter
echo "JupyterLab iniciado na porta 8888"

# Dashboard DIVEA Parana
tmux new-session -d -s divea -x 220 -y 50
tmux send-keys -t divea "conda activate divea && cd ~/divea/dashboard && streamlit run app.py --server.port 8501" Enter
echo "DIVEA Parana iniciado na porta 8501"

# Dashboard 15a RS
tmux new-session -d -s rs15 -x 220 -y 50
tmux send-keys -t rs15 "conda activate divea && cd ~/divea/dashboard && streamlit run app_15rs.py --server.port 8502" Enter
echo "15a RS iniciado na porta 8502"

echo ""
echo "=== Servicos disponiveis ==="
echo "JupyterLab : http://100.69.212.127:8888"
echo "DIVEA PR   : http://100.69.212.127:8501"
echo "15a RS     : http://100.69.212.127:8502"
