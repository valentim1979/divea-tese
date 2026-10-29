"""Perfil dos egressos do treinamento em vigilância.

Lê a planilha de participantes (.xlsx ou .csv) e gera a tabela
"Variável x Resumo dos resultados" com sexo, idade, profissão, vínculo,
tempo de experiência, local de atuação e o perfil predominante.

Uso:
    python analises/perfil_egressos.py participantes.xlsx
    python analises/perfil_egressos.py participantes.xlsx --somente-concluintes
    python analises/perfil_egressos.py participantes.csv --saida resultados/egressos

Saídas (na pasta --saida):
    resumo_egressos.md    tabela em Markdown
    resumo_egressos.xlsx  aba "Resumo" + uma aba de frequências por variável
    resumo_egressos.docx  tabela pronta para colar na tese
"""

import argparse
import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pandas as pd

# Nomes das colunas como aparecem na planilha original
COLUNAS = {
    'nome': 'Nome do participante',
    'sexo': 'Sexo',
    'idade': 'Idade',
    'profissao': 'Profissão',
    'profissao_outras': 'Especificar "Outras" em profissão',
    'vinculo': 'Vínculo de participante no momento do curso',
    'local': 'Local de atuação no momento do curso',
    'experiencia': 'Tempo de experiência na Vigilância',
    'conclusao': 'Recebeu declaração de conclusão do treinamento?',
}

ORDEM_EXPERIENCIA = ['> 5 anos', '3–5 anos', '1–2 anos', '< 1 ano', 'Sem experiência']


def normalizar(texto):
    """Minúsculas, sem acentos, aspas ou espaços repetidos (para comparar nomes)."""
    texto = unicodedata.normalize('NFKD', str(texto))
    texto = ''.join(c for c in texto if not unicodedata.combining(c))
    texto = texto.replace('"', '').replace("'", '').lower()
    return re.sub(r'\s+', ' ', texto).strip()


def localizar_coluna(df, nome, obrigatoria=True):
    """Acha a coluna pelo nome normalizado; aceita prefixo (ex.: cabeçalho com '(Sim/Não)')."""
    alvo = normalizar(nome)
    candidatas = {normalizar(c): c for c in df.columns}
    if alvo in candidatas:
        return candidatas[alvo]
    for norm, original in candidatas.items():
        if norm.startswith(alvo):
            return original
    if obrigatoria:
        raise KeyError(f'Coluna não encontrada: "{nome}". Colunas lidas: {list(df.columns)}')
    return None


def ler_planilha(caminho, aba=None):
    caminho = Path(caminho)
    if caminho.suffix.lower() in ('.xlsx', '.xls'):
        return pd.read_excel(caminho, sheet_name=aba or 0)
    # CSV: tenta ; , e tabulação
    return pd.read_csv(caminho, sep=None, engine='python', encoding='utf-8-sig')


def limpar_texto(serie):
    serie = serie.astype('string').str.strip()
    serie = serie.str.replace(r'\s+', ' ', regex=True)
    return serie.mask(serie.isin(['', 'nan', 'NaN', '-']))


def porcento(n, total):
    """Percentual com 1 casa, arredondando 0,05 para cima (como o Excel)."""
    return float(Decimal(str(n / total * 100)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))


def pct(n, total):
    return f'{n} ({porcento(n, total):.1f}%)'.replace('.', ',')


def frequencias(serie, total):
    contagem = serie.value_counts(dropna=False)
    tabela = contagem.rename_axis('Categoria').reset_index(name='n')
    tabela['Categoria'] = tabela['Categoria'].fillna('Sem informação')
    tabela['%'] = [porcento(n, total) for n in tabela['n']]
    return tabela


# ---------------------------------------------------------------------------
# Padronização das categorias
# ---------------------------------------------------------------------------

def padronizar_sexo(valor):
    if pd.isna(valor):
        return pd.NA
    v = normalizar(valor)
    if v.startswith('f') or v.startswith('mulher'):
        return 'Feminino'
    if v.startswith('m') or v.startswith('homem'):
        return 'Masculino'
    return str(valor)


def padronizar_profissao(valor):
    """Agrupa grafias diferentes da mesma profissão. A opção 'Outras' do formulário é mantida."""
    if pd.isna(valor):
        return pd.NA
    v = normalizar(valor)
    if v.startswith('outra'):
        return 'Outras'
    if 'tecnic' in v and 'enferm' in v:
        return 'Técnico(a) de enfermagem'
    if 'auxiliar' in v and 'enferm' in v:
        return 'Auxiliar de enfermagem'
    if 'enferm' in v:
        return 'Enfermeiro(a)'
    if 'tecnic' in v and 'vigil' in v:
        return 'Técnico em Vigilância em Saúde'
    if 'farmac' in v:
        return 'Farmacêutico(a)'
    if 'medic' in v and 'veterin' in v:
        return 'Médico(a) veterinário(a)'
    if 'medic' in v:
        return 'Médico(a)'
    if 'biomedic' in v:
        return 'Biomédico(a)'
    return str(valor).strip()


def padronizar_experiencia(valor):
    if pd.isna(valor):
        return pd.NA
    v = normalizar(valor)
    numeros = [int(n) for n in re.findall(r'\d+', v)]
    if 'sem' in v or 'nenhum' in v or v in ('nao', 'nao possui', '0'):
        return 'Sem experiência'
    if '>' in v or 'mais de' in v or 'acima' in v:
        if numeros and max(numeros) >= 5:
            return '> 5 anos'
    if 'menos de' in v or '<' in v:
        return '< 1 ano'
    if numeros:
        maior = max(numeros)
        if maior > 5:
            return '> 5 anos'
        if maior >= 3:
            return '3–5 anos'
        if maior >= 1:
            return '1–2 anos'
        return '< 1 ano'
    return str(valor)


# ---------------------------------------------------------------------------
# Resumos por variável
# ---------------------------------------------------------------------------

def resumo_categorias(tabela, total, ordem=None, top=None, rotulo_outras='Outras'):
    """Texto 'Cat: n (%) • Cat: n (%)'; categorias abaixo do top e 'Outras' viram rotulo_outras."""
    tabela = tabela[tabela['Categoria'] != 'Sem informação']
    if top is not None:
        # 'Outras' (opção do formulário) nunca entra no top; vai para o grupo final
        tabela = pd.concat([tabela[tabela['Categoria'] != 'Outras'], tabela[tabela['Categoria'] == 'Outras']])
    if ordem:
        chave = {c: i for i, c in enumerate(ordem)}
        tabela = tabela.assign(_o=tabela['Categoria'].map(chave).fillna(len(ordem)))
        tabela = tabela.sort_values(['_o', 'n'], ascending=[True, False])
    partes = []
    linhas = tabela if top is None else tabela.head(top)
    for _, linha in linhas.iterrows():
        partes.append(f"{linha['Categoria']}: {pct(int(linha['n']), total)}")
    if top is not None and len(tabela) > top:
        resto = int(tabela['n'].iloc[top:].sum())
        partes.append(f'{rotulo_outras}: {pct(resto, total)}')
    return ' • '.join(partes)


def categorias_predominantes(serie, n=3, separador=None):
    """Categorias mais frequentes. Com separador, conta cada opção de respostas múltiplas."""
    serie = serie.dropna()
    if separador:
        serie = serie.str.split(separador).explode().str.strip()
        serie = serie[serie != '']
    contagem = serie.value_counts()
    return contagem.head(n), contagem


def juntar(itens):
    itens = list(itens)
    if len(itens) <= 1:
        return ''.join(itens)
    return ', '.join(itens[:-1]) + ' e ' + itens[-1]


def flexionar(profissao, feminino):
    """'Enfermeiro(a)' -> 'enfermeira' (ou 'enfermeiro'), em minúsculas."""
    texto = re.sub(r'o\(a\)', 'a' if feminino else 'o', profissao)
    texto = texto.replace('(a)', 'a' if feminino else '')
    return texto[0].lower() + texto[1:]


def analisar(df, separador_local=None, top_profissoes=4, top_locais=3):
    col = {chave: localizar_coluna(df, nome, obrigatoria=chave not in ('profissao_outras', 'conclusao'))
           for chave, nome in COLUNAS.items()}

    dados = pd.DataFrame(index=df.index)
    dados['sexo'] = limpar_texto(df[col['sexo']]).map(padronizar_sexo)
    dados['idade'] = pd.to_numeric(df[col['idade']], errors='coerce')
    dados['profissao'] = limpar_texto(df[col['profissao']]).map(padronizar_profissao)
    if col['profissao_outras']:
        dados['profissao_outras'] = limpar_texto(df[col['profissao_outras']]).where(dados['profissao'] == 'Outras')
    dados['vinculo'] = limpar_texto(df[col['vinculo']])
    dados['local'] = limpar_texto(df[col['local']])
    dados['experiencia'] = limpar_texto(df[col['experiencia']]).map(padronizar_experiencia)

    total = len(dados)
    freq = {
        'Sexo': frequencias(dados['sexo'], total),
        'Profissão': frequencias(dados['profissao'], total),
        'Vínculo': frequencias(dados['vinculo'], total),
        'Experiência': frequencias(dados['experiencia'], total),
    }
    top_local, contagem_local = categorias_predominantes(dados['local'], top_locais, separador_local)
    freq['Local de atuação'] = contagem_local.rename_axis('Categoria').reset_index(name='n')
    freq['Local de atuação']['%'] = [porcento(n, total) for n in freq['Local de atuação']['n']]
    if 'profissao_outras' in dados:
        outras = dados['profissao_outras'].dropna()
        freq['Outras profissões'] = frequencias(outras, total) if len(outras) else pd.DataFrame()

    idade = dados['idade'].dropna()
    texto_idade = (f'Média: {idade.mean():.0f} anos • Mediana: {idade.median():.0f} anos • '
                   f'Mín: {idade.min():.0f} • Máx: {idade.max():.0f}')
    if len(idade) < total:
        texto_idade += f' (idade ausente em {total - len(idade)})'

    vinculo_modal = dados['vinculo'].mode()
    vinculo_modal = vinculo_modal.iloc[0] if len(vinculo_modal) else 'Sem informação'
    n_vinculo = int((dados['vinculo'] == vinculo_modal).sum())

    sexo_modal = dados['sexo'].mode().iloc[0]
    prof_modal = dados['profissao'].mode().iloc[0]
    exp_modal = dados['experiencia'].mode().iloc[0]
    feminino = sexo_modal == 'Feminino'

    if exp_modal == 'Sem experiência':
        texto_exp = 'sem experiência prévia em vigilância'
    else:
        texto_exp = f'com experiência prévia em vigilância ({exp_modal.replace(" anos", "").replace(" ", "")} anos)'
    perfil = (f"{'Mulher' if feminino else 'Homem'}, {flexionar(prof_modal, feminino)}, "
              f"{idade.mean():.0f} anos em média, {texto_exp}, "
              f"vínculo predominante: {vinculo_modal.lower()}")

    resumo = pd.DataFrame([
        ('Número de participantes', f'{total} egressos'),
        ('Sexo', resumo_categorias(freq['Sexo'], total)),
        ('Idade', texto_idade),
        ('Profissão (mais frequentes)', resumo_categorias(freq['Profissão'], total, top=top_profissoes,
                                                          rotulo_outras='Outras profissões')),
        ('Vínculo no momento do curso',
         f'Predomínio de profissionais com vínculo "{vinculo_modal}": {pct(n_vinculo, total)}'),
        ('Tempo de experiência na Vigilância',
         resumo_categorias(freq['Experiência'], total, ordem=ORDEM_EXPERIENCIA)),
        ('Local de atuação no momento do curso',
         'Predomínio de atuação em ' + juntar(f'{c}: {pct(int(n), total)}' for c, n in top_local.items())),
        ('Perfil predominante do egresso', perfil),
    ], columns=['Variável', 'Resumo dos resultados'])
    return resumo, freq


# ---------------------------------------------------------------------------
# Exportação
# ---------------------------------------------------------------------------

def para_markdown(resumo):
    linhas = ['| Variável | Resumo dos resultados |', '|---|---|']
    linhas += [f"| **{v}** | {r} |" for v, r in resumo.itertuples(index=False)]
    return '\n'.join(linhas)


def salvar_docx(resumo, caminho):
    from docx import Document
    from docx.shared import Pt

    doc = Document()
    tabela = doc.add_table(rows=1, cols=2)
    tabela.style = 'Table Grid'
    for celula, titulo in zip(tabela.rows[0].cells, resumo.columns):
        celula.text = ''
        celula.paragraphs[0].add_run(titulo).bold = True
    for variavel, texto in resumo.itertuples(index=False):
        celulas = tabela.add_row().cells
        celulas[0].text = ''
        celulas[0].paragraphs[0].add_run(variavel).bold = True
        celulas[1].text = texto
    for linha in tabela.rows:
        for celula in linha.cells:
            for paragrafo in celula.paragraphs:
                for run in paragrafo.runs:
                    run.font.size = Pt(10)
    doc.save(caminho)


def salvar(resumo, freq, pasta):
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / 'resumo_egressos.md').write_text(para_markdown(resumo) + '\n', encoding='utf-8')
    with pd.ExcelWriter(pasta / 'resumo_egressos.xlsx') as escritor:
        resumo.to_excel(escritor, sheet_name='Resumo', index=False)
        for nome, tabela in freq.items():
            tabela.to_excel(escritor, sheet_name=nome[:31], index=False)
    salvar_docx(resumo, pasta / 'resumo_egressos.docx')
    return pasta


def main():
    parser = argparse.ArgumentParser(description='Gera a tabela de perfil dos egressos.')
    parser.add_argument('arquivo', help='Planilha de participantes (.xlsx ou .csv)')
    parser.add_argument('--aba', help='Nome da aba do Excel (padrão: a primeira)')
    parser.add_argument('--saida', default='resultados/perfil_egressos', help='Pasta de saída')
    parser.add_argument('--somente-concluintes', action='store_true',
                        help='Mantém só quem recebeu declaração de conclusão (Sim)')
    parser.add_argument('--separador-local', default=None,
                        help='Separador quando "Local de atuação" tem várias respostas (ex.: ";")')
    parser.add_argument('--top-profissoes', type=int, default=4)
    parser.add_argument('--top-locais', type=int, default=3)
    args = parser.parse_args()

    df = ler_planilha(args.arquivo, args.aba)
    df.columns = [re.sub(r'\s+', ' ', str(c)).strip() for c in df.columns]

    # Descarta linhas vazias (sem nome do participante)
    col_nome = localizar_coluna(df, COLUNAS['nome'])
    df = df[limpar_texto(df[col_nome]).notna()]
    print(f'Linhas com participante: {len(df)}')

    if args.somente_concluintes:
        col_conclusao = localizar_coluna(df, COLUNAS['conclusao'])
        df = df[limpar_texto(df[col_conclusao]).map(lambda v: not pd.isna(v) and normalizar(v).startswith('s'))]
        print(f'Concluintes (declaração = Sim): {len(df)}')

    resumo, freq = analisar(df, args.separador_local, args.top_profissoes, args.top_locais)

    print()
    print(para_markdown(resumo))
    for nome, tabela in freq.items():
        print(f'\n--- {nome} ---')
        print(tabela.to_string(index=False))

    pasta = salvar(resumo, freq, args.saida)
    print(f'\nArquivos salvos em: {pasta.resolve()}')


if __name__ == '__main__':
    main()
