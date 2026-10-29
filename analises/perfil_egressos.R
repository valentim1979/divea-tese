# =============================================================================
# perfil_egressos.R
# Perfil dos egressos do treinamento em vigilância (versão R de perfil_egressos.py)
#
# Lê uma ou mais planilhas de participantes (.xlsx ou .csv), junta as turmas e
# gera a tabela "Variável x Resumo dos resultados" com sexo, idade, profissão,
# vínculo, tempo de experiência, local de atuação e o perfil predominante.
#
# Percentuais são calculados sobre as respostas válidas de cada variável;
# respostas em branco aparecem como "sem informação".
#
# Uso:
#   Rscript analises/perfil_egressos.R turma1.xlsx turma2.xlsx turma3.xlsx
#   Rscript analises/perfil_egressos.R dados/*.xlsx --somente-concluintes
#   Rscript analises/perfil_egressos.R dados/*.xlsx --excluir-turmas MMAR_04
#
# Opções:
#   --aba NOME                Aba do Excel (padrão: a primeira)
#   --saida PASTA             Pasta de saída (padrão: resultados/perfil_egressos)
#   --excluir-turmas T1 T2    Turmas a deixar de fora (ex.: turma em andamento)
#   --somente-concluintes     Mantém só quem recebeu declaração de conclusão (Sim)
#   --separador-local SEP     Separador quando "Local de atuação" tem várias respostas
#   --top-profissoes N        Profissões mostradas antes de "Outras profissões" (padrão: 4)
#   --top-locais N            Locais mostrados no predomínio (padrão: 3)
#
# Saídas (na pasta --saida):
#   resumo_egressos.md    tabela em Markdown
#   resumo_egressos.xlsx  aba "Resumo", frequências por variável e "Mapeamento"
#                         (resposta original -> categoria usada, para conferência)
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
  turma       = "Número da turma",
  sexo        = "Sexo",
  idade       = "Idade",
  profissao   = "Profissão",
  vinculo     = "Vínculo de participante no momento do curso",
  local       = "Local de atuação no momento do curso",
  experiencia = "Tempo de experiência na Vigilância",
  conclusao   = "Recebeu declaração de conclusão do treinamento?"
)
OPCIONAIS <- c("turma", "conclusao")
VARIAVEIS <- c("sexo", "idade", "profissao", "vinculo", "local", "experiencia")

# Categorias do formulário ("Mais de 05 anos", "02 a 05 anos", "Até 02 anos", "Sem experiência")
ORDEM_EXPERIENCIA <- c("> 5 anos", "2 a 5 anos", "Até 2 anos", "Sem experiência")

# -----------------------------------------------------------------------------
# 2. FUNÇÕES AUXILIARES
# -----------------------------------------------------------------------------
# Minúsculas, sem acentos, aspas ou espaços repetidos (para comparar textos)
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
  nomes <- trimws(gsub("\\s+", " ", names(df)))
  # Descarta colunas sem cabeçalho e repetidas (ex.: o segundo "Número da turma")
  manter <- !is.na(nomes) & nomes != "" & !duplicated(nomes)
  df <- df[, manter, drop = FALSE]
  names(df) <- nomes[manter]
  df
}

# Empilha planilhas com colunas diferentes (colunas ausentes ficam NA)
juntar_planilhas <- function(lista) {
  todas <- unique(unlist(lapply(lista, names)))
  do.call(rbind, lapply(lista, function(df) {
    for (coluna in setdiff(todas, names(df))) df[[coluna]] <- NA_character_
    df[, todas, drop = FALSE]
  }))
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

# Frequências sobre as respostas válidas; brancos vão para o fim como "Sem informação"
# (decrescente por n; empate segue a ordem em que aparece)
frequencias <- function(x) {
  validos <- x[!is.na(x)]
  categorias <- unique(validos)
  n <- as.integer(table(factor(validos, levels = categorias)))
  ordem <- order(-n, seq_along(categorias))
  tabela <- data.frame(Categoria = categorias[ordem], n = n[ordem],
                       `%` = porcento(n[ordem], length(validos)),
                       check.names = FALSE, stringsAsFactors = FALSE)
  faltantes <- sum(is.na(x))
  if (faltantes) {
    tabela <- rbind(tabela, data.frame(Categoria = "Sem informação", n = faltantes, `%` = NA,
                                       check.names = FALSE))
  }
  tabela
}

validos <- function(tabela) tabela[tabela$Categoria != "Sem informação", , drop = FALSE]

nota_faltantes <- function(tabela) {
  faltantes <- tabela$n[tabela$Categoria == "Sem informação"]
  if (length(faltantes)) sprintf(" (sem informação: %d)", faltantes) else ""
}

# -----------------------------------------------------------------------------
# 3. PADRONIZAÇÃO DAS CATEGORIAS (respostas livres -> categorias de análise)
# -----------------------------------------------------------------------------
# Aplica a regra a cada valor, mantendo NA
por_valor <- function(regra) {
  function(valor) {
    vapply(valor, function(x) if (is.na(x)) NA_character_ else regra(x, normalizar(x)),
           character(1), USE.NAMES = FALSE)
  }
}

tem <- function(v, ...) all(vapply(c(...), function(t) grepl(t, v, fixed = TRUE), logical(1)))

padronizar_sexo <- por_valor(function(x, v) {
  if (startsWith(v, "f") || startsWith(v, "mulher")) return("Feminino")
  if (startsWith(v, "m") || startsWith(v, "homem")) return("Masculino")
  x
})

# Agrupa grafias diferentes da mesma profissão. A opção "Outras" do formulário é mantida.
padronizar_profissao <- por_valor(function(x, v) {
  if (startsWith(v, "outra"))                  return("Outras")
  if (tem(v, "tecnic", "enferm"))              return("Técnico(a) de enfermagem")
  if (tem(v, "auxiliar", "enferm"))            return("Auxiliar de enfermagem")
  if (tem(v, "enferm"))                        return("Enfermeiro(a)")
  if (tem(v, "tecnic", "vigil"))               return("Técnico em Vigilância em Saúde")
  if (tem(v, "farmac"))                        return("Farmacêutico(a)")
  if (tem(v, "biomedic"))                      return("Biomédico(a)")
  if (tem(v, "medic", "veterin"))              return("Médico(a) veterinário(a)")
  if (tem(v, "medic"))                         return("Médico(a)")
  if (tem(v, "biolog"))                        return("Biólogo(a)")
  if (tem(v, "psicolog"))                      return("Psicólogo(a)")
  if (tem(v, "nutricion"))                     return("Nutricionista")
  if (tem(v, "dentista") || tem(v, "odontolog")) return("Cirurgião(ã)-dentista")
  if (tem(v, "administrativ"))                 return("Auxiliar/assistente administrativo")
  trimws(x)
})

padronizar_vinculo <- por_valor(function(x, v) {
  if (tem(v, "servidor", "publ")) {
    if (tem(v, "municip")) return("Servidor público municipal")
    if (tem(v, "estad"))   return("Servidor público estadual")
    if (tem(v, "feder"))   return("Servidor público federal")
    return("Servidor público (esfera não informada)")
  }
  if (tem(v, "privad"))   return("Serviço privado")
  if (tem(v, "resident")) return("Residente")
  if (tem(v, "estagi"))   return("Estagiário(a)")
  if (tem(v, "tempor"))   return("Contrato temporário")
  trimws(x)
})

# Agrupa o local de atuação (texto livre) em áreas de atuação
padronizar_local <- por_valor(function(x, v) {
  palavra <- function(p) grepl(sprintf("\\b%s\\b", p), v)
  if (tem(v, "hospital") || tem(v, "nveh"))   return("Serviços hospitalares")
  if (tem(v, "epidemiolog"))                  return("Vigilância Epidemiológica")
  if (tem(v, "sanitari"))                     return("Vigilância Sanitária")
  if (tem(v, "ambiental"))                    return("Vigilância Ambiental")
  if (tem(v, "saude do trabalhador"))         return("Saúde do Trabalhador")
  if (tem(v, "vigilancia em saude"))          return("Vigilância em Saúde (sem especificar)")
  if (tem(v, "atencao primaria") || palavra("aps") || palavra("ubs") || tem(v, "centro de saude"))
    return("Atenção Primária à Saúde")
  if (palavra("upa") || tem(v, "urgencia") || tem(v, "regulacao"))
    return("Urgência/emergência e regulação")
  if (tem(v, "secretaria") || palavra("sms") || tem(v, "regional") || tem(v, "gestor"))
    return("Secretaria/Regional de Saúde (setor não especificado)")
  "Outros"
})

padronizar_experiencia <- por_valor(function(x, v) {
  numeros <- as.integer(regmatches(v, gregexpr("[0-9]+", v))[[1]])
  if (tem(v, "sem") || tem(v, "nenhum") || v %in% c("nao", "nao possui", "0")) return("Sem experiência")
  if ((tem(v, ">") || tem(v, "mais de") || tem(v, "acima")) && length(numeros) && max(numeros) >= 5)
    return("> 5 anos")
  if ("ate" %in% strsplit(v, " ")[[1]] || tem(v, "menos de") || tem(v, "<")) return("Até 2 anos")
  if (length(numeros) >= 2) return(if (max(numeros) <= 5) "2 a 5 anos" else "> 5 anos")  # faixa "02 a 05 anos"
  if (length(numeros)) {
    anos <- numeros[1]
    if (anos == 0) return("Sem experiência")
    if (anos <= 2) return("Até 2 anos")
    if (anos <= 5) return("2 a 5 anos")
    return("> 5 anos")
  }
  x
})

# -----------------------------------------------------------------------------
# 4. RESUMOS POR VARIÁVEL
# -----------------------------------------------------------------------------
# Texto "Cat: n (%) • Cat: n (%)"; categorias abaixo do top e "Outras" viram rotulo_outras
resumo_categorias <- function(tabela, ordem = NULL, top = NULL, rotulo_outras = "Outras") {
  nota <- nota_faltantes(tabela)
  tabela <- validos(tabela)
  total <- sum(tabela$n)
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
  paste0(paste(partes, collapse = " • "), nota)
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

mapeamento <- function(original, padronizado, variavel) {
  ok <- !is.na(original)
  if (!any(ok)) return(NULL)
  tabela <- aggregate(list(n = rep(1L, sum(ok))),
                      list(`Resposta original` = original[ok], `Categoria usada` = padronizado[ok]),
                      sum)
  names(tabela)[1:2] <- c("Resposta original", "Categoria usada")
  tabela <- tabela[order(tabela$`Categoria usada`, -tabela$n), ]
  cbind(`Variável` = variavel, tabela)
}

analisar <- function(df, separador_local = NULL, top_profissoes = 4, top_locais = 3) {
  col <- lapply(names(COLUNAS), function(k) localizar_coluna(df, COLUNAS[[k]], !(k %in% OPCIONAIS)))
  names(col) <- names(COLUNAS)

  bruto <- lapply(c(sexo = "sexo", profissao = "profissao", vinculo = "vinculo",
                    local = "local", experiencia = "experiencia"),
                  function(k) limpar_texto(df[[col[[k]]]]))
  local <- bruto$local
  if (!is.null(separador_local)) {
    local <- trimws(unlist(lapply(local, function(x) if (is.na(x)) NA else strsplit(x, separador_local, fixed = TRUE)[[1]])))
    local[local %in% ""] <- NA
  }

  dados <- list(
    sexo        = padronizar_sexo(bruto$sexo),
    idade       = suppressWarnings(as.numeric(sub(",", ".", df[[col$idade]], fixed = TRUE))),
    profissao   = padronizar_profissao(bruto$profissao),
    vinculo     = padronizar_vinculo(bruto$vinculo),
    local       = padronizar_local(local),
    experiencia = padronizar_experiencia(bruto$experiencia)
  )

  total <- nrow(df)
  freq <- list(
    "Sexo"             = frequencias(dados$sexo),
    "Profissão"        = frequencias(dados$profissao),
    "Vínculo"          = frequencias(dados$vinculo),
    "Experiência"      = frequencias(dados$experiencia),
    "Local de atuação" = frequencias(dados$local)
  )
  if (!is.na(col$turma)) freq[["Turmas"]] <- frequencias(limpar_texto(df[[col$turma]]))
  freq[["Mapeamento"]] <- rbind(
    mapeamento(bruto$profissao, dados$profissao, "Profissão"),
    mapeamento(bruto$vinculo, dados$vinculo, "Vínculo"),
    mapeamento(local, dados$local, "Local de atuação"),
    mapeamento(bruto$experiencia, dados$experiencia, "Experiência")
  )

  # Número de participantes, por turma
  texto_n <- sprintf("%d egressos", total)
  if (!is.na(col$turma)) {
    turmas <- validos(freq[["Turmas"]])
    turmas <- turmas[order(turmas$Categoria), ]
    texto_n <- paste0(texto_n, " (", paste(sprintf("%s: %d", turmas$Categoria, turmas$n), collapse = " • "), ")")
  }

  idade <- dados$idade[!is.na(dados$idade)]
  texto_idade <- sprintf("Média: %.0f anos • Mediana: %.0f anos • Mín: %.0f • Máx: %.0f",
                         mean(idade), median(idade), min(idade), max(idade))
  if (length(idade) < total) {
    texto_idade <- paste0(texto_idade, sprintf(" (sem informação: %d)", total - length(idade)))
  }

  # Vínculo: soma os servidores públicos de todas as esferas
  vinc <- validos(freq[["Vínculo"]])
  n_vinc <- sum(vinc$n)
  publico <- vinc[startsWith(vinc$Categoria, "Servidor público"), ]
  n_publico <- sum(publico$n)
  detalhe <- paste(sprintf("%s: %d", sub("Servidor público ", "", publico$Categoria, fixed = TRUE), publico$n),
                   collapse = " • ")
  texto_vinculo <- paste0(sprintf("Serviço público: %s [%s] • Outros vínculos: %s",
                                  pct(n_publico, n_vinc), detalhe, pct(n_vinc - n_publico, n_vinc)),
                          nota_faltantes(freq[["Vínculo"]]))

  todos_locais <- validos(freq[["Local de atuação"]])
  locais <- head(todos_locais[todos_locais$Categoria != "Outros", ], top_locais)
  texto_local <- paste0("Predomínio de atuação em ",
                        juntar(sprintf("%s: %s", locais$Categoria, pct(locais$n, sum(todos_locais$n)))),
                        nota_faltantes(freq[["Local de atuação"]]))

  sexo_modal <- validos(freq[["Sexo"]])$Categoria[1]
  prof_modal <- validos(freq[["Profissão"]])$Categoria[1]
  exp_modal  <- validos(freq[["Experiência"]])$Categoria[1]
  feminino   <- identical(sexo_modal, "Feminino")
  texto_exp <- if (identical(exp_modal, "Sem experiência")) {
    "sem experiência prévia em vigilância"
  } else {
    sprintf("com experiência prévia em vigilância (%s)", exp_modal)
  }
  texto_servico <- if (n_publico > n_vinc / 2) {
    "atuando em serviços públicos de saúde"
  } else {
    paste("vínculo predominante:", tolower(vinc$Categoria[1]))
  }
  perfil <- sprintf("%s, %s, %.0f anos em média, %s, %s",
                    if (feminino) "Mulher" else "Homem", flexionar(prof_modal, feminino),
                    mean(idade), texto_exp, texto_servico)

  resumo <- data.frame(
    `Variável` = c(
      "Número de participantes", "Sexo", "Idade", "Profissão (mais frequentes)",
      "Vínculo no momento do curso", "Tempo de experiência na Vigilância",
      "Local de atuação no momento do curso", "Perfil predominante do egresso"
    ),
    `Resumo dos resultados` = c(
      texto_n,
      resumo_categorias(freq[["Sexo"]]),
      texto_idade,
      resumo_categorias(freq[["Profissão"]], top = top_profissoes, rotulo_outras = "Outras profissões"),
      texto_vinculo,
      resumo_categorias(freq[["Experiência"]], ordem = ORDEM_EXPERIENCIA),
      texto_local,
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
  opcoes <- list(arquivos = character(), aba = NULL, saida = "resultados/perfil_egressos",
                 excluir_turmas = character(), somente_concluintes = FALSE,
                 separador_local = NULL, top_profissoes = 4, top_locais = 3)
  i <- 1
  while (i <= length(args)) {
    a <- args[i]
    valor <- if (i < length(args)) args[i + 1] else NA
    if (a == "--somente-concluintes") { opcoes$somente_concluintes <- TRUE; i <- i + 1; next }
    if (a == "--excluir-turmas") {
      i <- i + 1
      while (i <= length(args) && !startsWith(args[i], "--") && !file.exists(args[i])) {
        opcoes$excluir_turmas <- c(opcoes$excluir_turmas, args[i]); i <- i + 1
      }
      next
    }
    if (a == "--aba")             { opcoes$aba <- valor; i <- i + 2; next }
    if (a == "--saida")           { opcoes$saida <- valor; i <- i + 2; next }
    if (a == "--separador-local") { opcoes$separador_local <- valor; i <- i + 2; next }
    if (a == "--top-profissoes")  { opcoes$top_profissoes <- as.integer(valor); i <- i + 2; next }
    if (a == "--top-locais")      { opcoes$top_locais <- as.integer(valor); i <- i + 2; next }
    if (startsWith(a, "--")) stop("Opção desconhecida: ", a, call. = FALSE)
    opcoes$arquivos <- c(opcoes$arquivos, a)
    i <- i + 1
  }
  if (!length(opcoes$arquivos)) {
    stop("Informe as planilhas: Rscript analises/perfil_egressos.R turma1.xlsx turma2.xlsx", call. = FALSE)
  }
  opcoes
}

main <- function() {
  opcoes <- ler_argumentos(commandArgs(trailingOnly = TRUE))
  df <- juntar_planilhas(lapply(opcoes$arquivos, ler_planilha, aba = opcoes$aba))

  # Descarta linhas sem nenhuma das variáveis analisadas preenchida
  col_vars <- vapply(VARIAVEIS, function(k) localizar_coluna(df, COLUNAS[[k]]), character(1))
  preenchida <- Reduce(`|`, lapply(col_vars, function(c) !is.na(limpar_texto(df[[c]]))))
  df <- df[preenchida, , drop = FALSE]
  cat(sprintf("Linhas com participante: %d\n", nrow(df)))

  if (length(opcoes$excluir_turmas)) {
    turma <- normalizar(limpar_texto(df[[localizar_coluna(df, COLUNAS$turma)]]))
    df <- df[is.na(turma) | !(turma %in% normalizar(opcoes$excluir_turmas)), , drop = FALSE]
    cat(sprintf("Sem as turmas %s: %d\n", paste(opcoes$excluir_turmas, collapse = ", "), nrow(df)))
  }

  if (opcoes$somente_concluintes) {
    resposta <- limpar_texto(df[[localizar_coluna(df, COLUNAS$conclusao)]])
    df <- df[!is.na(resposta) & startsWith(normalizar(resposta), "s"), , drop = FALSE]
    cat(sprintf("Concluintes (declaração = Sim): %d\n", nrow(df)))
  }

  resultado <- analisar(df, opcoes$separador_local, opcoes$top_profissoes, opcoes$top_locais)

  cat("\n", paste(para_markdown(resultado$resumo), collapse = "\n"), "\n", sep = "")
  for (nome in setdiff(names(resultado$freq), "Mapeamento")) {
    cat(sprintf("\n--- %s ---\n", nome))
    print(resultado$freq[[nome]], row.names = FALSE)
  }

  pasta <- salvar(resultado, opcoes$saida)
  cat(sprintf("\nArquivos salvos em: %s\n", pasta))
}

if (sys.nframe() == 0) main()
