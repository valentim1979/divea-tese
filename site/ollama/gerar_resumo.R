# =============================================================================
# gerar_resumo.R
# Gera resumo executivo da situação epidemiológica via Ollama
# Execute ANTES de quarto render
# Saída: site/ollama/resumo_atual.txt
# =============================================================================
# Ollama: http://localhost:11434
# Modelo: divea-biostats
# =============================================================================

library(tidyverse)
library(lubridate)
library(janitor)
library(readxl)
library(httr2)
library(jsonlite)

# -----------------------------------------------------------------------------
# 1. CONFIGURAÇÃO
# -----------------------------------------------------------------------------
OLLAMA_URL   <- "http://localhost:11434/api/generate"
OLLAMA_MODEL <- "divea-biostats"
SAIDA        <- "ollama/resumo_atual.txt"

GAL_PATH    <- "/home/valentim/divea/data/GAL_VR_consolidado.xlsx"
INTERP_15RS <- "/home/valentim/divea/data/processed/interpretacao_tft_15rs.txt"
METRICAS    <- "dados/metricas_srag.json"

municipios_15rs <- c(
  "ANGULO", "ASTORGA", "ATALAIA", "COLORADO", "DOUTOR CAMARGO",
  "FLORAI", "FLORESTA", "FLORIDA", "IGUARACU", "ITAGUAJE",
  "ITAMBE", "IVATUBA", "LOBATO", "MANDAGUACU", "MANDAGUARI",
  "MARIALVA", "MARINGA", "MUNHOZ DE MELO", "NOSSA SENHORA DAS GRACAS",
  "NOVA ESPERANCA", "OURIZONA", "PAICANDU", "PARANACITY",
  "PRESIDENTE CASTELO BRANCO", "SANTA FE", "SANTA INES",
  "SANTO INACIO", "SAO JORGE DO IVAI", "SARANDI", "UNIFLOR"
)

# -----------------------------------------------------------------------------
# 2. INDICADORES DO GAL
# -----------------------------------------------------------------------------
gal <- read_excel(GAL_PATH, col_types = "text") |>
  clean_names() |>
  mutate(
    data_da_coleta    = as.Date(as.numeric(data_da_coleta), origin = "1899-12-30"),
    data_da_liberacao = as.Date(as.numeric(data_da_liberacao), origin = "1899-12-30"),
    tat_total         = as.numeric(data_da_liberacao - data_da_coleta)
  ) |>
  filter(
    municipio_de_residencia %in% municipios_15rs,
    !is.na(data_da_coleta),
    data_da_coleta >= Sys.Date() - 28,
    !is.na(tat_total), tat_total >= 0, tat_total <= 60
  )

tat_recente  <- round(median(gal$tat_total, na.rm = TRUE), 1)
n_amostras   <- nrow(gal)
data_atual   <- format(Sys.Date(), "%d/%m/%Y")
semana_atual <- epiweek(Sys.Date())
ano_atual    <- year(Sys.Date())

# -----------------------------------------------------------------------------
# 3. MÉTRICAS SRAG (se disponíveis)
# -----------------------------------------------------------------------------
srag_ctx <- ""
if (file.exists(METRICAS)) {
  m <- fromJSON(METRICAS)
  srag_ctx <- paste0(
    "Casos SRAG notificados (", m$ano_referencia, "): ", m$total_casos, "\n",
    "Óbitos: ", m$total_obitos, "\n",
    "Vírus predominante: ", m$virus_pred, "\n",
    "Variação semanal: ", m$variacao_pct, "%\n"
  )
}

# -----------------------------------------------------------------------------
# 4. INTERPRETAÇÃO TFT (se disponível)
# -----------------------------------------------------------------------------
tft_ctx <- ""
if (file.exists(INTERP_15RS)) {
  tft_ctx <- paste(
    "Interpretação dos modelos preditivos (15ª RS):",
    paste(readLines(INTERP_15RS, warn = FALSE), collapse = " ")
  )
}

# -----------------------------------------------------------------------------
# 5. PROMPT
# -----------------------------------------------------------------------------
prompt <- paste0(
  "Você é um assistente de vigilância epidemiológica da 15ª Regional de Saúde ",
  "de Maringá, Paraná. Gere um parágrafo de resumo executivo em português, ",
  "claro e direto, para gestores de saúde. Máximo 4 frases. Não use markdown.\n\n",
  "Data: ", data_atual, "\n",
  "Semana epidemiológica: SE", semana_atual, "/", ano_atual, "\n",
  "Amostras GAL (últimas 4 semanas, 15ª RS): ", n_amostras, "\n",
  "TAT mediano GAL: ", tat_recente, " dias\n",
  srag_ctx,
  tft_ctx
)

# -----------------------------------------------------------------------------
# 6. CHAMADA AO OLLAMA
# -----------------------------------------------------------------------------
message("Consultando Ollama...")

resposta <- tryCatch({
  resp <- request(OLLAMA_URL) |>
    req_body_json(list(
      model   = OLLAMA_MODEL,
      prompt  = prompt,
      stream  = FALSE,
      options = list(temperature = 0.2)
    )) |>
    req_timeout(120) |>
    req_perform()
  resp_body_json(resp)$response
}, error = function(e) {
  message("Erro Ollama: ", e$message)
  NULL
})

# -----------------------------------------------------------------------------
# 7. SALVA
# -----------------------------------------------------------------------------
dir.create(dirname(SAIDA), recursive = TRUE, showWarnings = FALSE)

if (!is.null(resposta) && nchar(trimws(resposta)) > 0) {
  writeLines(c(
    paste0("> **Resumo epidemiológico — SE", semana_atual, "/", ano_atual, "**"),
    ">",
    paste0("> ", trimws(resposta)),
    ">",
    paste0("> *Gerado em: ", data_atual,
           " | Modelo: ", OLLAMA_MODEL,
           " | Amostras GAL (4 sem.): ", n_amostras, "*")
  ), SAIDA)
  message("Resumo salvo: ", SAIDA)
} else {
  writeLines("> *Resumo automático não disponível nesta atualização.*", SAIDA)
  message("Resumo não gerado — verifique Ollama.")
}
