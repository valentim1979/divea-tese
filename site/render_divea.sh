#!/bin/bash
# =============================================================================
# render_divea.sh
# Publica o portal DIVEA no GitHub Pages
# Execute a partir de: ~/divea-tese/site/
# =============================================================================

set -e

echo ""
echo "=================================================="
echo "  DIVEA — Render do portal GitHub Pages"
echo "  $(date '+%d/%m/%Y %H:%M')"
echo "=================================================="

# 1. Gera resumo executivo via Ollama
echo ""
echo "[1/4] Gerando resumo via Ollama..."
Rscript ollama/gerar_resumo.R

# 2. Renderiza o site Quarto
echo ""
echo "[2/4] Renderizando site Quarto..."
quarto render

# 3. Commit e push
echo ""
echo "[3/4] Publicando no GitHub..."
cd ..
git add docs/
git add site/
git commit -m "DIVEA: SE$(date '+%V')/$(date '+%Y') — $(date '+%d/%m/%Y')" || echo "Nada para commitar."
git push

echo ""
echo "[4/4] Concluído."
echo "Portal: https://valentim1979.github.io/divea-tese/"
echo "=================================================="
