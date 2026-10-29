# =============================================================================
# perfil_egressos.R
# Perfil dos egressos do treinamento em vigilância (versão R de perfil_egressos.py)
#
# Lê a planilha de participantes (.xlsx ou .csv) e gera a tabela
# "Variável x Resumo dos resultados" com sexo, idade, profissão, vínculo,
# tempo de experiência, local de atuação e o perfil predominante.
#
# Uso:
#   Rscript analises/perfil_egressos.R participantes.xlsx
#   Rscript analises/perfil_egressos.R participantes.xlsx --somente-concluintes
#   Rscript analises/perfil_egressos.R participantes.csv --saida resultados/egressos
#
# Opções:
#   --aba NOME                Aba do Excel (padrão: a primeira)
#   --saida PASTA             Pasta de saída (padrão: resultados/perfil_egressos)
#   --somente-concluintes     Mantém só quem recebeu declaração de conclusão (Sim)
#   --separador-local SEP     Separador quando "Local de atuação" tem várias respostas
#   --top-profissoes N        Profissões mostradas antes de "Outras profissões" (padrão: 4)
#   --top-locais N            Locais mostrados no predomínio (padrão: 3)
#
# Saídas (na pasta --saida):
#   resumo_egressos.md    tabela em Markdown
#   resumo_egressos.xlsx  aba "Resumo" + uma aba de frequências por variável
#   resumo_egressos.docx  tabela pronta para colar na tese
#
# Pacotes: readxl, readr, stringi, openxlsx, officer, flextable
# =============================================================================

# Acentos dos nomes de colunas e categorias exigem localidade UTF-8
if (!l10n_info()[["UTF-8"]]) invisible(Sys.setlocale("LC_CTYPE", "C.UTF-8"))

suppressPackageStartupMessages({
  library(readxl)
  library(readr)
  library(stringi)
  library(openxlsx)
  library(officer)
  library(flextable)
})

# -----------------------------------------------------------------------------
# 1. CONFIGURAÇÃO
# -----------------------------------------------------------------------------
# Nomes das colunas como aparecem na planilha original
COLUNAS <- list(
  nome             = "Nome do participante",
  sexo             = "Sexo",
  idade            = "Idade",
  profissao        = "Profissão",
  profissao_outras = 'Especificar "Outras" em profissão',
  vinculo          = "Vínculo de participante no momento do curso",
  local            = "Local de atuação no momento do curso",
  experiencia      = "Tempo de experiência na Vigilância",
  conclusao        = "Recebeu declaração de conclusão do treinamento?"
)
OPCIONAIS <- c("profissao_outras", "conclusao")

ORDEM_EXPERIENCIA <- c("> 5 anos", "3–5 anos", "1–2 anos", "< 1 ano", "Sem experiência")

# -----------------------------------------------------------------------------
# 2. FUNÇÕES AUXILIARES
# -----------------------------------------------------------------------------
# Minúsculas, sem acentos, aspas ou espaços repetidos (para comparar nomes)
normalizar <- function(texto) {
  texto <- stri_trans_general(as.character(texto), "Latin-ASCII")
  texto <- gsub("[\"']", "", tolower(texto))
  trimws(gsub("\\s+", " ", texto))
}

# Acha a coluna pelo nome normalizado; aceita prefixo (ex.: cabeçalho com "(Sim/Não)")
localizar_coluna <- function(df, nome, obrigatoria = TRUE) {
  alvo <- normalizar(nome)
  norm <- normalizar(names(df))
  i <- match(alvo, norm)
  if (is.na(i)) i <- which(startsWith(norm, alvo))[1]
  if (is.na(i)) {
    if (obrigatoria) {
      stop(sprintf('Coluna não encontrada: "%s". Colunas lidas: %s',
                   nome, paste(names(df), collapse = " | ")), call. = FALSE)
    }
    return(NA_character_)
  }
  names(df)[i]
}

ler_planilha <- function(caminho, aba = NULL) {
  if (tolower(tools::file_ext(caminho)) %in% c("xlsx", "xls")) {
    df <- read_excel(caminho, sheet = if (is.null(aba)) 1 else aba,
                     col_types = "text", .name_repair = "minimal")
  } else {
    # CSV: detecta ; , ou tabulação pela primeira linha
    primeira <- readLines(caminho, n = 1, encoding = "UTF-8", warn = FALSE)
    seps <- c(";", ",", "\t")
    sep <- seps[which.max(sapply(seps, function(s) lengths(regmatches(primeira, gregexpr(s, primeira, fixed = TRUE)))))]
    df <- read_delim(caminho, delim = sep, col_types = cols(.default = "c"),
                     locale = locale(encoding = "UTF-8"), name_repair = "minimal",
                     show_col_types = FALSE)
  }
  df <- as.data.frame(df, check.names = FALSE, stringsAsFactors = FALSE)
  names(df) <- trimws(gsub("\\s+", " ", names(df)))
  df
}

limpar_texto <- function(x) {
  x <- trimws(gsub("\\s+", " ", as.character(x)))
  x[x %in% c("", "nan", "NaN", "NA", "-")] <- NA
  x
}

# Percentual com 1 casa, arredondando 0,05 para cima (como o Excel)
porcento <- function(n, total) {
  floor(n / total * 1000 + 0.5 + 1e-9) / 10
}

pct <- function(n, total) {
  sub(".", ",", sprintf("%d (%.1f%%)", as.integer(n), porcento(n, total)), fixed = TRUE)
}

# Tabela de frequências: decrescente por n; empate segue a ordem em que aparece
frequencias <- function(x, total) {
  x[is.na(x)] <- "Sem informação"
  if (length(x) == 0) return(data.frame(Categoria = character(), n = integer(), `%` = numeric(), check.names = FALSE))
  categorias <- unique(x)
  n <- as.integer(table(factor(x, levels = categorias)))
  ordem <- order(-n, seq_along(categorias))
  data.frame(Categoria = categorias[ordem], n = n[ordem],
             `%` = porcento(n[ordem], total), check.names = FALSE, stringsAsFactors = FALSE)
}

moda <- function(x) {
  x <- x[!is.na(x)]
  if (length(x) == 0) return(NA_character_)
  frequencias(x, length(x))$Categoria[1]
}

# -----------------------------------------------------------------------------
# 3. PADRONIZAÇÃO DAS CATEGORIAS
# -----------------------------------------------------------------------------
padronizar_sexo <- function(valor) {
  v <- normalizar(valor)
  ifelse(is.na(valor), NA,
  ifelse(startsWith(v, "f") | startsWith(v, "mulher"), "Feminino",
  ifelse(startsWith(v, "m") | startsWith(v, "homem"), "Masculino", valor)))
}

# Agrupa grafias diferentes da mesma profissão. A opção "Outras" do formulário é mantida.
padronizar_profissao <- function(valor) {
  sapply(valor, function(p) {
    if (is.na(p)) return(NA_character_)
    v <- normalizar(p)
    tem <- function(...) all(sapply(c(...), function(t) grepl(t, v, fixed = TRUE)))
    if (startsWith(v, "outra"))         return("Outras")
    if (tem("tecnic", "enferm"))        return("Técnico(a) de enfermagem")
    if (tem("auxiliar", "enferm"))      return("Auxiliar de enfermagem")
    if (tem("enferm"))                  return("Enfermeiro(a)")
    if (tem("tecnic", "vigil"))         return("Técnico em Vigilância em Saúde")
    if (tem("farmac"))                  return("Farmacêutico(a)")
    if (tem("biomedic"))                return("Biomédico(a)")
    if (tem("medic", "veterin"))        return("Médico(a) veterinário(a)")
    if (tem("medic"))                   return("Médico(a)")
    trimws(p)
  }, USE.NAMES = FALSE)
}

padronizar_experiencia <- function(valor) {
  sapply(valor, function(e) {
    if (is.na(e)) return(NA_character_)
    v <- normalizar(e)
    numeros <- as.integer(regmatches(v, gregexpr("[0-9]+", v))[[1]])
    if (grepl("sem", v) || grepl("nenhum", v) || v %in% c("nao", "nao possui", "0")) return("Sem experiência")
    if ((grepl(">", v) || grepl("mais de", v) || grepl("acima", v)) &&
        length(numeros) && max(numeros) >= 5) return("> 5 anos")
    if (grepl("menos de", v) || grepl("<", v)) return("< 1 ano")
    if (length(numeros)) {
      maior <- max(numeros)
      if (maior > 5)  return("> 5 anos")
      if (maior >= 3) return("3–5 anos")
      if (maior >= 1) return("1–2 anos")
      return("< 1 ano")
    }
    e
  }, USE.NAMES = FALSE)
}

# -----------------------------------------------------------------------------
# 4. RESUMOS POR VARIÁVEL
# -----------------------------------------------------------------------------
# Texto "Cat: n (%) • Cat: n (%)"; categorias abaixo do top e "Outras" viram rotulo_outras
resumo_categorias <- function(tabela, total, ordem = NULL, top = NULL, rotulo_outras = "Outras") {
  tabela <- tabela[tabela$Categoria != "Sem informação", ]
  if (!is.null(top)) {
    # "Outras" (opção do formulário) nunca entra no top; vai para o grupo final
    tabela <- rbind(tabela[tabela$Categoria != "Outras", ], tabela[tabela$Categoria == "Outras", ])
  }
  if (!is.null(ordem)) {
    chave <- match(tabela$Categoria, ordem)
    chave[is.na(chave)] <- length(ordem) + 1
    tabela <- tabela[order(chave, -tabela$n), ]
  }
  linhas <- if (is.null(top)) tabela else head(tabela, top)
  partes <- sprintf("%s: %s", linhas$Categoria, pct(linhas$n, total))
  if (!is.null(top) && nrow(tabela) > top) {
    partes <- c(partes, sprintf("%s: %s", rotulo_outras, pct(sum(tabela$n[-seq_len(top)]), total)))
  }
  paste(partes, collapse = " • ")
}

juntar <- function(itens) {
  if (length(itens) <= 1) return(paste(itens, collapse = ""))
  paste0(paste(head(itens, -1), collapse = ", "), " e ", tail(itens, 1))
}

# "Enfermeiro(a)" -> "enfermeira" (ou "enfermeiro"), começando em minúscula
flexionar <- function(profissao, feminino) {
  texto <- gsub("o\\(a\\)", if (feminino) "a" else "o", profissao)
  texto <- gsub("(a)", if (feminino) "a" else "", texto, fixed = TRUE)
  paste0(tolower(substr(texto, 1, 1)), substring(texto, 2))
}

analisar <- function(df, separador_local = NULL, top_profissoes = 4, top_locais = 3) {
  col <- lapply(names(COLUNAS), function(k) localizar_coluna(df, COLUNAS[[k]], !(k %in% OPCIONAIS)))
  names(col) <- names(COLUNAS)

  sexo        <- padronizar_sexo(limpar_texto(df[[col$sexo]]))
  idade       <- suppressWarnings(as.numeric(sub(",", ".", df[[col$idade]], fixed = TRUE)))
  profissao   <- padronizar_profissao(limpar_texto(df[[col$profissao]]))
  vinculo     <- limpar_texto(df[[col$vinculo]])
  local       <- limpar_texto(df[[col$local]])
  experiencia <- padronizar_experiencia(limpar_texto(df[[col$experiencia]]))

  total <- nrow(df)
  freq <- list(
    "Sexo"        = frequencias(sexo, total),
    "Profissão"   = frequencias(profissao, total),
    "Vínculo"     = frequencias(vinculo, total),
    "Experiência" = frequencias(experiencia, total)
  )

  # Local de atuação: com separador, conta cada opção das respostas múltiplas
  locais <- local[!is.na(local)]
  if (!is.null(separador_local)) {
    locais <- trimws(unlist(strsplit(locais, separador_local, fixed = TRUE)))
    locais <- locais[locais != ""]
  }
  freq[["Local de atuação"]] <- frequencias(locais, total)
  top_local <- head(freq[["Local de atuação"]], top_locais)

  if (!is.na(col$profissao_outras)) {
    outras <- limpar_texto(df[[col$profissao_outras]])[profissao %in% "Outras"]
    outras <- outras[!is.na(outras)]
    if (length(outras)) freq[["Outras profissões"]] <- frequencias(outras, total)
  }

  idade_ok <- idade[!is.na(idade)]
  texto_idade <- sprintf("Média: %.0f anos • Mediana: %.0f anos • Mín: %.0f • Máx: %.0f",
                         mean(idade_ok), median(idade_ok), min(idade_ok), max(idade_ok))
  if (length(idade_ok) < total) {
    texto_idade <- paste0(texto_idade, sprintf(" (idade ausente em %d)", total - length(idade_ok)))
  }

  vinculo_modal <- moda(vinculo)
  if (is.na(vinculo_modal)) vinculo_modal <- "Sem informação"
  n_vinculo <- sum(vinculo %in% vinculo_modal)

  sexo_modal <- moda(sexo)
  prof_modal <- moda(profissao)
  exp_modal  <- moda(experiencia)
  feminino   <- identical(sexo_modal, "Feminino")

  texto_exp <- if (identical(exp_modal, "Sem experiência")) {
    "sem experiência prévia em vigilância"
  } else {
    sprintf("com experiência prévia em vigilância (%s anos)", gsub(" ", "", sub(" anos", "", exp_modal)))
  }
  perfil <- sprintf("%s, %s, %.0f anos em média, %s, vínculo predominante: %s",
                    if (feminino) "Mulher" else "Homem", flexionar(prof_modal, feminino),
                    mean(idade_ok), texto_exp, tolower(vinculo_modal))

  resumo <- data.frame(
    `Variável` = c(
      "Número de participantes", "Sexo", "Idade", "Profissão (mais frequentes)",
      "Vínculo no momento do curso", "Tempo de experiência na Vigilância",
      "Local de atuação no momento do curso", "Perfil predominante do egresso"
    ),
    `Resumo dos resultados` = c(
      sprintf("%d egressos", total),
      resumo_categorias(freq[["Sexo"]], total),
      texto_idade,
      resumo_categorias(freq[["Profissão"]], total, top = top_profissoes,
                        rotulo_outras = "Outras profissões"),
      sprintf('Predomínio de profissionais com vínculo "%s": %s', vinculo_modal, pct(n_vinculo, total)),
      resumo_categorias(freq[["Experiência"]], total, ordem = ORDEM_EXPERIENCIA),
      paste0("Predomínio de atuação em ",
             juntar(sprintf("%s: %s", top_local$Categoria, pct(top_local$n, total)))),
      perfil
    ),
    check.names = FALSE, stringsAsFactors = FALSE
  )
  list(resumo = resumo, freq = freq)
}

# -----------------------------------------------------------------------------
# 5. EXPORTAÇÃO
# -----------------------------------------------------------------------------
para_markdown <- function(resumo) {
  c("| Variável | Resumo dos resultados |", "|---|---|",
    sprintf("| **%s** | %s |", resumo[[1]], resumo[[2]]))
}

salvar_docx <- function(resumo, caminho) {
  tabela <- flextable(resumo)
  tabela <- bold(tabela, part = "header")
  tabela <- bold(tabela, j = 1, part = "body")
  tabela <- fontsize(tabela, size = 10, part = "all")
  tabela <- border_outer(tabela)
  tabela <- border_inner(tabela)
  tabela <- width(tabela, j = 1, width = 2.2)
  tabela <- width(tabela, j = 2, width = 4.3)
  doc <- body_add_flextable(read_docx(), tabela)
  print(doc, target = caminho)
}

salvar <- function(resultado, pasta) {
  dir.create(pasta, recursive = TRUE, showWarnings = FALSE)
  writeLines(para_markdown(resultado$resumo), file.path(pasta, "resumo_egressos.md"), useBytes = TRUE)
  abas <- c(list(Resumo = resultado$resumo), resultado$freq)
  names(abas) <- substr(names(abas), 1, 31)
  write.xlsx(abas, file.path(pasta, "resumo_egressos.xlsx"), overwrite = TRUE)
  salvar_docx(resultado$resumo, file.path(pasta, "resumo_egressos.docx"))
  normalizePath(pasta)
}

# -----------------------------------------------------------------------------
# 6. EXECUÇÃO
# -----------------------------------------------------------------------------
ler_argumentos <- function(args) {
  opcoes <- list(arquivo = NULL, aba = NULL, saida = "resultados/perfil_egressos",
                 somente_concluintes = FALSE, separador_local = NULL,
                 top_profissoes = 4, top_locais = 3)
  i <- 1
  while (i <= length(args)) {
    a <- args[i]
    valor <- if (i < length(args)) args[i + 1] else NA
    if (a == "--somente-concluintes") { opcoes$somente_concluintes <- TRUE; i <- i + 1; next }
    if (a == "--aba")             { opcoes$aba <- valor; i <- i + 2; next }
    if (a == "--saida")           { opcoes$saida <- valor; i <- i + 2; next }
    if (a == "--separador-local") { opcoes$separador_local <- valor; i <- i + 2; next }
    if (a == "--top-profissoes")  { opcoes$top_profissoes <- as.integer(valor); i <- i + 2; next }
    if (a == "--top-locais")      { opcoes$top_locais <- as.integer(valor); i <- i + 2; next }
    if (startsWith(a, "--")) stop("Opção desconhecida: ", a, call. = FALSE)
    opcoes$arquivo <- a
    i <- i + 1
  }
  if (is.null(opcoes$arquivo)) {
    stop("Informe a planilha: Rscript analises/perfil_egressos.R participantes.xlsx", call. = FALSE)
  }
  opcoes
}

main <- function() {
  opcoes <- ler_argumentos(commandArgs(trailingOnly = TRUE))
  df <- ler_planilha(opcoes$arquivo, opcoes$aba)

  # Descarta linhas vazias (sem nome do participante)
  col_nome <- localizar_coluna(df, COLUNAS$nome)
  df <- df[!is.na(limpar_texto(df[[col_nome]])), , drop = FALSE]
  cat(sprintf("Linhas com participante: %d\n", nrow(df)))

  if (opcoes$somente_concluintes) {
    col_conclusao <- localizar_coluna(df, COLUNAS$conclusao)
    resposta <- limpar_texto(df[[col_conclusao]])
    df <- df[!is.na(resposta) & startsWith(normalizar(resposta), "s"), , drop = FALSE]
    cat(sprintf("Concluintes (declaração = Sim): %d\n", nrow(df)))
  }

  resultado <- analisar(df, opcoes$separador_local, opcoes$top_profissoes, opcoes$top_locais)

  cat("\n", paste(para_markdown(resultado$resumo), collapse = "\n"), "\n", sep = "")
  for (nome in names(resultado$freq)) {
    cat(sprintf("\n--- %s ---\n", nome))
    print(resultado$freq[[nome]], row.names = FALSE)
  }

  pasta <- salvar(resultado, opcoes$saida)
  cat(sprintf("\nArquivos salvos em: %s\n", pasta))
}

if (sys.nframe() == 0) main()
