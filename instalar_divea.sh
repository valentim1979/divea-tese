#!/bin/bash
# =============================================================================
# instalar_divea.sh
# Cria a estrutura completa do portal DIVEA dentro do repositório divea-tese
# Execute UMA VEZ a partir da raiz do repositório: ~/divea-tese/
# Uso: bash instalar_divea.sh
# =============================================================================

set -e

REPO_DIVEA="$HOME/divea-tese"
REPO_SRAG="$HOME/vigilancia-epidemiologica"

echo ""
echo "=================================================="
echo "  DIVEA — Instalação da estrutura do portal"
echo "  $(date '+%d/%m/%Y %H:%M')"
echo "=================================================="

# -----------------------------------------------------------------------------
# 1. Verifica se está na pasta certa
# -----------------------------------------------------------------------------
if [ ! -d "$REPO_DIVEA" ]; then
  echo ""
  echo "[ERRO] Pasta $REPO_DIVEA não encontrada."
  echo "       Ajuste a variável REPO_DIVEA no início do script."
  exit 1
fi

cd "$REPO_DIVEA"
echo ""
echo "[1/6] Repositório: $REPO_DIVEA"

# -----------------------------------------------------------------------------
# 2. Cria estrutura de pastas do site/
# -----------------------------------------------------------------------------
echo ""
echo "[2/6] Criando estrutura de pastas..."

mkdir -p site/gal
mkdir -p site/sindromica
mkdir -p site/ollama
mkdir -p site/dados
mkdir -p docs

echo "      site/gal          ✓"
echo "      site/sindromica   ✓"
echo "      site/ollama       ✓"
echo "      site/dados        ✓"
echo "      docs/             ✓"

# -----------------------------------------------------------------------------
# 3. Cria .nojekyll (necessário para GitHub Pages com Quarto)
# -----------------------------------------------------------------------------
touch docs/.nojekyll
echo ""
echo "[3/6] docs/.nojekyll criado ✓"

# -----------------------------------------------------------------------------
# 4. Copia os arquivos gerados pelo Claude para as pastas corretas
# -----------------------------------------------------------------------------
echo ""
echo "[4/6] Copiando arquivos do portal..."
echo ""
echo "      ATENÇÃO: copie manualmente os arquivos baixados do Claude"
echo "      para as seguintes destinações:"
echo ""
echo "      Arquivo                        → Destino"
echo "      ─────────────────────────────────────────────────────────"
echo "      _quarto.yml                    → site/_quarto.yml"
echo "      index.qmd                      → site/index.qmd"
echo "      render_divea.sh                → site/render_divea.sh"
echo "      gal/index.qmd                  → site/gal/index.qmd"
echo "      sindromica/index.qmd           → site/sindromica/index.qmd"
echo "      ollama/gerar_resumo.R          → site/ollama/gerar_resumo.R"
echo "      README.md                      → README.md (raiz do repo)"
echo ""
echo "      Para o repositório SRAG:"
echo "      exportar_metricas_divea.R      → $REPO_SRAG/exportar_metricas_divea.R"

# -----------------------------------------------------------------------------
# 5. Permissões
# -----------------------------------------------------------------------------
echo ""
echo "[5/6] Configurando permissões..."

if [ -f "site/render_divea.sh" ]; then
  chmod +x site/render_divea.sh
  echo "      site/render_divea.sh → executável ✓"
else
  echo "      site/render_divea.sh não encontrado ainda — rode chmod +x site/render_divea.sh após copiar"
fi

# -----------------------------------------------------------------------------
# 6. Configura GitHub Pages no _quarto.yml (verifica output-dir)
# -----------------------------------------------------------------------------
echo ""
echo "[6/6] Verificações finais..."
echo ""

# Verifica se Quarto está instalado
if command -v quarto &> /dev/null; then
  echo "      Quarto: $(quarto --version) ✓"
else
  echo "      [AVISO] Quarto não encontrado. Instale em: https://quarto.org/docs/get-started/"
fi

# Verifica se R está instalado
if command -v Rscript &> /dev/null; then
  echo "      R: $(Rscript --version 2>&1 | head -1) ✓"
else
  echo "      [AVISO] R não encontrado no PATH."
fi

# Verifica pacotes R necessários
echo ""
echo "      Verificando pacotes R necessários..."
Rscript --quiet -e "
pkgs <- c('tidyverse','lubridate','janitor','readxl','jsonlite','httr2','writexl')
faltam <- pkgs[!sapply(pkgs, requireNamespace, quietly=TRUE)]
if (length(faltam) == 0) {
  cat('      Todos os pacotes R estão instalados ✓\n')
} else {
  cat('      Pacotes ausentes:', paste(faltam, collapse=', '), '\n')
  cat('      Instale com: install.packages(c(\"', paste(faltam, collapse='\",\"'), '\"))\n', sep='')
}
"

# -----------------------------------------------------------------------------
# Instruções finais
# -----------------------------------------------------------------------------
echo ""
echo "=================================================="
echo "  Estrutura criada com sucesso."
echo ""
echo "  PRÓXIMOS PASSOS:"
echo ""
echo "  1. Copie os arquivos conforme indicado no passo 4"
echo ""
echo "  2. Ajuste os caminhos em site/_quarto.yml:"
echo "     output-dir: ../docs"
echo ""
echo "  3. Ajuste os caminhos absolutos em:"
echo "     site/ollama/gerar_resumo.R  (GAL_PATH, INTERP_15RS)"
echo "     site/gal/index.qmd          (GAL_PATH)"
echo "     site/index.qmd              (METRICAS_SRAG, GAL_PATH)"
echo ""
echo "  4. No repositório SRAG, adicione ao final do SCRIPT_Unificado.R:"
echo "     source('exportar_metricas_divea.R')"
echo ""
echo "  5. Ajuste o caminho de saída em exportar_metricas_divea.R:"
echo "     saida <- '$REPO_DIVEA/site/dados/metricas_srag.json'"
echo ""
echo "  6. Configure o GitHub Pages:"
echo "     Settings → Pages → Source: main / pasta /docs"
echo ""
echo "  7. Primeiro render:"
echo "     cd $REPO_SRAG && ./publicar.sh --dados-novos"
echo "     cd $REPO_DIVEA/site && ./render_divea.sh"
echo ""
echo "  Portal: https://valentim1979.github.io/divea-tese/"
echo "=================================================="
