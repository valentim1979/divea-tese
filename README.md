# DIVEA — Dashboard Interativo de Vigilância Epidemiológica Aumentada

**15ª Regional de Saúde de Maringá — SCVGE**
Doutorado em Bioestatística | PPG-PBE/UEM | Orientador: Prof. Dr. Diogo Rossoni

---

## Estrutura do repositório

```
divea-tese/
├── notebooks/                  # Desenvolvimento e análise (Python)
│   ├── 01_exploracao_preparacao_dados.ipynb
│   ├── 02_modelo_lstm_influenza.ipynb
│   ├── 03_clusterizacao_espacial.ipynb
│   ├── 04_painel_15rs.ipynb
│   ├── 05_otimizacao_lstm.ipynb
│   ├── 06_tft_srag.ipynb
│   ├── 07_tft_completo.ipynb
│   ├── A_ollama_assistente_metodologico.ipynb
│   ├── B_rag_artigos_cientificos.ipynb
│   └── C_interpretacao_modelos_llm.ipynb
│
├── dashboard/                  # Aplicações Streamlit (acesso interno)
│   ├── app.py                  # Painel Paraná
│   ├── app_15rs.py             # Painel 15ª RS
│   ├── gerar_previsoes_tft.py
│   ├── gerar_interpretacao_tft.py
│   ├── consultar_rag.py
│   └── indexar_artigos.py
│
├── site/                       # Portal público — GitHub Pages (Quarto)
│   ├── _quarto.yml
│   ├── index.qmd               # Página inicial com cards e resumo Ollama
│   ├── render_divea.sh         # Script de publicação
│   ├── gal/index.qmd           # Laboratório — GAL/LACEN-PR
│   ├── sindromica/index.qmd    # Vigilância sindrômica
│   ├── ollama/gerar_resumo.R   # Gera resumo no render
│   └── dados/
│       └── metricas_srag.json  # Gerado pelo exportar_metricas_divea.R
│
├── tese/                       # Documentos da tese
├── docs/                       # Output Quarto → GitHub Pages
└── environment_divea.yml       # Ambiente conda
```

---

## Fluxo de atualização semanal

```bash
# 1. Atualiza previsões TFT e interpretação Ollama
cd ~/divea-tese/dashboard
conda activate divea
python gerar_previsoes_tft.py
python gerar_interpretacao_tft.py

# 2. Publica o dashboard SRAG (gera metricas_srag.json automaticamente)
cd ~/vigilancia-epidemiologica
./publicar.sh --dados-novos

# 3. Publica o portal DIVEA
cd ~/divea-tese/site
./render_divea.sh
```

---

## Infraestrutura

| Componente | Tecnologia | Endereço |
|---|---|---|
| Portal público | Quarto + GitHub Pages | valentim1979.github.io/divea-tese |
| Dashboard SRAG | Quarto + GitHub Pages | valentim1979.github.io/vigilancia-epidemiologica |
| Painel interativo PR | Streamlit | localhost:8501 |
| Painel interativo 15ª RS | Streamlit | localhost:8502 |
| LLM local | Ollama — divea-biostats (Qwen2.5 14B) | localhost:11434 |
| RAG científico | ChromaDB + nomic-embed-text | /home/valentim/divea/data/chromadb |
| Hardware | Ryzen 5 5600G + RTX 5060 Ti 16GB + 32GB DDR4 | Ubuntu |

---

## Iniciar Streamlit

```bash
conda activate divea
cd ~/divea-tese/dashboard
streamlit run app.py --server.port 8501 &
streamlit run app_15rs.py --server.port 8502 &
```
