"""Perfil dos egressos do treinamento em vigilância.

Lê uma ou mais planilhas de participantes (.xlsx ou .csv), junta as turmas e
gera a tabela "Variável x Resumo dos resultados" com sexo, idade, profissão,
vínculo, tempo de experiência, local de atuação e o perfil predominante.

Percentuais são calculados sobre as respostas válidas de cada variável;
respostas em branco aparecem como "sem informação".

Uso:
    python analises/perfil_egressos.py turma1.xlsx turma2.xlsx turma3.xlsx
    python analises/perfil_egressos.py dados/*.xlsx --somente-concluintes
    python analises/perfil_egressos.py dados/*.xlsx --excluir-turmas MMAR_04
    python analises/perfil_egressos.py participantes.csv --saida resultados/egressos

Saídas (na pasta --saida):
    resumo_egressos.md    tabela em Markdown
    resumo_egressos.xlsx  aba "Resumo", frequências por variável e "Mapeamento"
                          (resposta original -> categoria usada, para conferência)
    resumo_egressos.docx  tabela pronta para colar na tese
"""

import argparse
import io
import re
import unicodedata
import zipfile
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pandas as pd

# Nomes das colunas como aparecem na planilha original
COLUNAS = {
    'turma': 'Número da turma',
    'sexo': 'Sexo',
    'idade': 'Idade',
    'profissao': 'Profissão',
    'vinculo': 'Vínculo de participante no momento do curso',
    'local': 'Local de atuação no momento do curso',
    'experiencia': 'Tempo de experiência na Vigilância',
    'conclusao': 'Recebeu declaração de conclusão do treinamento?',
}
OPCIONAIS = ('turma', 'conclusao')
VARIAVEIS = ('sexo', 'idade', 'profissao', 'vinculo', 'local', 'experiencia')

# Categorias do formulário ("Mais de 05 anos", "02 a 05 anos", "Até 02 anos", "Sem experiência")
ORDEM_EXPERIENCIA = ['> 5 anos', '2 a 5 anos', 'Até 2 anos', 'Sem experiência']


def normalizar(texto):
    """Minúsculas, sem acentos, aspas ou espaços repetidos (para comparar textos)."""
    texto = unicodedata.normalize('NFKD', str(texto))
    texto = ''.join(c for c in texto if not unicodedata.combining(c))
    texto = texto.replace('"', '').replace("'", '').lower()
    return re.sub(r'\s+', ' ', texto).strip()


def localizar_coluna(df, nome, obrigatoria=True):
    """Acha a coluna pelo nome normalizado; aceita prefixo (ex.: cabeçalho com '(Sim/Não)')."""
    alvo = normalizar(nome)
    candidatas = {}
    for c in df.columns:
        candidatas.setdefault(normalizar(c), c)
    if alvo in candidatas:
        return candidatas[alvo]
    for norm, original in candidatas.items():
        if norm.startswith(alvo):
            return original
    if obrigatoria:
        raise KeyError(f'Coluna não encontrada: "{nome}". Colunas lidas: {list(df.columns)}')
    return None


def ler_excel(caminho, aba):
    try:
        return pd.read_excel(caminho, sheet_name=aba or 0, dtype=str)
    except (TypeError, ValueError):
        # Validações de dados malformadas (ex.: "A1;A99:A998") travam o openpyxl; remove-as em memória
        buffer = io.BytesIO()
        with zipfile.ZipFile(caminho) as origem, zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as destino:
            for item in origem.infolist():
                conteudo = origem.read(item.filename)
                if item.filename.startswith('xl/worksheets/') and item.filename.endswith('.xml'):
                    conteudo = re.sub(rb'<dataValidations\b.*?</dataValidations>', b'', conteudo, flags=re.S)
                destino.writestr(item, conteudo)
        buffer.seek(0)
        return pd.read_excel(buffer, sheet_name=aba or 0, dtype=str)


def ler_planilha(caminho, aba=None):
    caminho = Path(caminho)
    if caminho.suffix.lower() in ('.xlsx', '.xls'):
        df = ler_excel(caminho, aba)
    else:
        # CSV: tenta ; , e tabulação
        df = pd.read_csv(caminho, sep=None, engine='python', encoding='utf-8-sig', dtype=str)
    df.columns = [re.sub(r'\s+', ' ', str(c)).strip() for c in df.columns]
    # Descarta colunas sem cabeçalho e repetidas (ex.: o segundo "Número da turma")
    df = df.loc[:, [not c.startswith('Unnamed:') and c != '' for c in df.columns]]
    df.columns = [re.sub(r'\.\d+$', '', c) for c in df.columns]
    return df.loc[:, ~df.columns.duplicated()]


def limpar_texto(serie):
    serie = serie.astype('string').str.strip()
    serie = serie.str.replace(r'\s+', ' ', regex=True)
    return serie.mask(serie.isin(['', 'nan', 'NaN', '-']))


def porcento(n, total):
    """Percentual com 1 casa, arredondando 0,05 para cima (como o Excel)."""
    return float(Decimal(str(n / total * 100)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))


def pct(n, total):
    return f'{n} ({porcento(n, total):.1f}%)'.replace('.', ',')


def frequencias(serie):
    """Frequências sobre as respostas válidas; brancos vão para o fim como 'Sem informação'."""
    validos = serie.dropna()
    total = len(validos)
    tabela = validos.value_counts().rename_axis('Categoria').reset_index(name='n')
    tabela['%'] = [porcento(n, total) for n in tabela['n']]
    faltantes = int(serie.isna().sum())
    if faltantes:
        tabela.loc[len(tabela)] = ['Sem informação', faltantes, None]
    return tabela


def validos(tabela):
    return tabela[tabela['Categoria'] != 'Sem informação']


def nota_faltantes(tabela):
    faltantes = tabela.loc[tabela['Categoria'] == 'Sem informação', 'n']
    return f' (sem informação: {int(faltantes.iloc[0])})' if len(faltantes) else ''


# ---------------------------------------------------------------------------
# Padronização das categorias (respostas livres -> categorias de análise)
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
    if 'biomedic' in v:
        return 'Biomédico(a)'
    if 'medic' in v and 'veterin' in v:
        return 'Médico(a) veterinário(a)'
    if 'medic' in v:
        return 'Médico(a)'
    if 'biolog' in v:
        return 'Biólogo(a)'
    if 'psicolog' in v:
        return 'Psicólogo(a)'
    if 'nutricion' in v:
        return 'Nutricionista'
    if 'dentista' in v or 'odontolog' in v:
        return 'Cirurgião(ã)-dentista'
    if 'administrativ' in v:
        return 'Auxiliar/assistente administrativo'
    if 'digitador' in v:
        return 'Digitador(a)'
    return str(valor).strip()


def padronizar_vinculo(valor):
    if pd.isna(valor):
        return pd.NA
    v = normalizar(valor)
    if 'servidor' in v and 'publ' in v:
        if 'municip' in v:
            return 'Servidor público municipal'
        if 'estad' in v:
            return 'Servidor público estadual'
        if 'feder' in v:
            return 'Servidor público federal'
        return 'Servidor público (esfera não informada)'
    if 'privad' in v:
        return 'Serviço privado'
    if 'resident' in v:
        return 'Residente'
    if 'estagi' in v:
        return 'Estagiário(a)'
    if 'tempor' in v:
        return 'Contrato temporário'
    return str(valor).strip()


def padronizar_local(valor):
    """Agrupa o local de atuação (texto livre) em áreas de atuação."""
    if pd.isna(valor):
        return pd.NA
    v = normalizar(valor)
    if 'hospital' in v or 'nveh' in v:
        return 'Serviços hospitalares'
    if 'epidemiolog' in v:
        return 'Vigilância Epidemiológica'
    if 'sanitari' in v:
        return 'Vigilância Sanitária'
    if 'ambiental' in v:
        return 'Vigilância Ambiental'
    if 'saude do trabalhador' in v:
        return 'Saúde do Trabalhador'
    if 'vigilancia em saude' in v:
        return 'Vigilância em Saúde (sem especificar)'
    if 'atencao primaria' in v or re.search(r'\b(aps|ubs)\b', v) or 'centro de saude' in v:
        return 'Atenção Primária à Saúde'
    if re.search(r'\bupa\b', v) or 'urgencia' in v or 'regulacao' in v:
        return 'Urgência/emergência e regulação'
    if 'secretaria' in v or re.search(r'\bsms\b', v) or 'regional' in v or 'gestor' in v:
        return 'Secretaria/Regional de Saúde (setor não especificado)'
    return 'Outros'


def padronizar_experiencia(valor):
    if pd.isna(valor):
        return pd.NA
    v = normalizar(valor)
    numeros = [int(n) for n in re.findall(r'\d+', v)]
    if 'sem' in v or 'nenhum' in v or v in ('nao', 'nao possui', '0'):
        return 'Sem experiência'
    if ('>' in v or 'mais de' in v or 'acima' in v) and numeros and max(numeros) >= 5:
        return '> 5 anos'
    if 'ate' in v.split() or 'menos de' in v or '<' in v:
        return 'Até 2 anos'
    if len(numeros) >= 2:  # faixa "02 a 05 anos"
        return '2 a 5 anos' if max(numeros) <= 5 else '> 5 anos'
    if numeros:
        anos = numeros[0]
        if anos == 0:
            return 'Sem experiência'
        if anos <= 2:
            return 'Até 2 anos'
        if anos <= 5:
            return '2 a 5 anos'
        return '> 5 anos'
    return str(valor)


# ---------------------------------------------------------------------------
# Resumos por variável
# ---------------------------------------------------------------------------

def resumo_categorias(tabela, ordem=None, top=None, rotulo_outras='Outras'):
    """Texto 'Cat: n (%) • Cat: n (%)'; categorias abaixo do top e 'Outras' viram rotulo_outras."""
    nota = nota_faltantes(tabela)
    tabela = validos(tabela)
    total = int(tabela['n'].sum())
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
    return ' • '.join(partes) + nota


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


def mapeamento(original, padronizado, variavel):
    tabela = pd.DataFrame({'Resposta original': original, 'Categoria usada': padronizado}).dropna()
    tabela = tabela.value_counts().reset_index(name='n')
    tabela.insert(0, 'Variável', variavel)
    return tabela.sort_values(['Categoria usada', 'n'], ascending=[True, False])


def analisar(df, separador_local=None, top_profissoes=4, top_locais=3):
    col = {chave: localizar_coluna(df, nome, obrigatoria=chave not in OPCIONAIS)
           for chave, nome in COLUNAS.items()}

    bruto = {chave: limpar_texto(df[col[chave]]) for chave in ('sexo', 'profissao', 'vinculo', 'local', 'experiencia')}
    local = bruto['local']
    if separador_local:
        local = local.str.split(separador_local).explode().str.strip()
        local = local.mask(local == '')

    dados = {
        'sexo': bruto['sexo'].map(padronizar_sexo),
        'idade': pd.to_numeric(df[col['idade']].astype('string').str.replace(',', '.'), errors='coerce'),
        'profissao': bruto['profissao'].map(padronizar_profissao),
        'vinculo': bruto['vinculo'].map(padronizar_vinculo),
        'local': local.map(padronizar_local),
        'experiencia': bruto['experiencia'].map(padronizar_experiencia),
    }

    total = len(df)
    freq = {
        'Sexo': frequencias(dados['sexo']),
        'Profissão': frequencias(dados['profissao']),
        'Vínculo': frequencias(dados['vinculo']),
        'Experiência': frequencias(dados['experiencia']),
        'Local de atuação': frequencias(dados['local']),
    }
    if col['turma']:
        freq['Turmas'] = frequencias(limpar_texto(df[col['turma']]))
    freq['Mapeamento'] = pd.concat([
        mapeamento(bruto['profissao'], dados['profissao'], 'Profissão'),
        mapeamento(bruto['vinculo'], dados['vinculo'], 'Vínculo'),
        mapeamento(local, dados['local'], 'Local de atuação'),
        mapeamento(bruto['experiencia'], dados['experiencia'], 'Experiência'),
    ], ignore_index=True)

    # Número de participantes, por turma
    texto_n = f'{total} egressos'
    if col['turma']:
        turmas = validos(freq['Turmas']).sort_values('Categoria')
        texto_n += ' (' + ' • '.join(f"{t}: {n}" for t, n in zip(turmas['Categoria'], turmas['n'])) + ')'

    idade = dados['idade'].dropna()
    texto_idade = (f'Média: {idade.mean():.0f} anos • Mediana: {idade.median():.0f} anos • '
                   f'Mín: {idade.min():.0f} • Máx: {idade.max():.0f}')
    if len(idade) < total:
        texto_idade += f' (sem informação: {total - len(idade)})'

    # Vínculo: soma os servidores públicos de todas as esferas
    vinc = validos(freq['Vínculo'])
    n_vinc = int(vinc['n'].sum())
    publico = vinc[vinc['Categoria'].str.startswith('Servidor público')]
    n_publico = int(publico['n'].sum())
    detalhe = ' • '.join(f"{c.replace('Servidor público ', '')}: {n}"
                         for c, n in zip(publico['Categoria'], publico['n']))
    texto_vinculo = (f'Serviço público: {pct(n_publico, n_vinc)} [{detalhe}] • '
                     f'Outros vínculos: {pct(n_vinc - n_publico, n_vinc)}' + nota_faltantes(freq['Vínculo']))

    locais = validos(freq['Local de atuação'])
    locais = locais[locais['Categoria'] != 'Outros'].head(top_locais)
    n_local = int(validos(freq['Local de atuação'])['n'].sum())
    texto_local = ('Predomínio de atuação em '
                   + juntar(f'{c}: {pct(int(n), n_local)}' for c, n in zip(locais['Categoria'], locais['n']))
                   + nota_faltantes(freq['Local de atuação']))

    sexo_modal = validos(freq['Sexo'])['Categoria'].iloc[0]
    prof_modal = validos(freq['Profissão'])['Categoria'].iloc[0]
    exp_modal = validos(freq['Experiência'])['Categoria'].iloc[0]
    feminino = sexo_modal == 'Feminino'
    if exp_modal == 'Sem experiência':
        texto_exp = 'sem experiência prévia em vigilância'
    else:
        texto_exp = f'com experiência prévia em vigilância ({exp_modal})'
    texto_servico = ('atuando em serviços públicos de saúde' if n_publico > n_vinc / 2
                     else f"vínculo predominante: {vinc['Categoria'].iloc[0].lower()}")
    perfil = (f"{'Mulher' if feminino else 'Homem'}, {flexionar(prof_modal, feminino)}, "
              f"{idade.mean():.0f} anos em média, {texto_exp}, {texto_servico}")

    resumo = pd.DataFrame([
        ('Número de participantes', texto_n),
        ('Sexo', resumo_categorias(freq['Sexo'])),
        ('Idade', texto_idade),
        ('Profissão (mais frequentes)', resumo_categorias(freq['Profissão'], top=top_profissoes,
                                                          rotulo_outras='Outras profissões')),
        ('Vínculo no momento do curso', texto_vinculo),
        ('Tempo de experiência na Vigilância', resumo_categorias(freq['Experiência'], ordem=ORDEM_EXPERIENCIA)),
        ('Local de atuação no momento do curso', texto_local),
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
    parser.add_argument('arquivos', nargs='+', help='Planilhas de participantes (.xlsx ou .csv), uma ou mais turmas')
    parser.add_argument('--aba', help='Nome da aba do Excel (padrão: a primeira)')
    parser.add_argument('--saida', default='resultados/perfil_egressos', help='Pasta de saída')
    parser.add_argument('--excluir-turmas', nargs='+', default=[],
                        help='Turmas a deixar de fora (ex.: MMAR_04, turma em andamento)')
    parser.add_argument('--somente-concluintes', action='store_true',
                        help='Mantém só quem recebeu declaração de conclusão (Sim)')
    parser.add_argument('--separador-local', default=None,
                        help='Separador quando "Local de atuação" tem várias respostas (ex.: ";")')
    parser.add_argument('--top-profissoes', type=int, default=4)
    parser.add_argument('--top-locais', type=int, default=3)
    args = parser.parse_args()

    df = pd.concat([ler_planilha(arquivo, args.aba) for arquivo in args.arquivos], ignore_index=True)

    # Descarta linhas sem nenhuma das variáveis analisadas preenchida
    col_vars = [localizar_coluna(df, COLUNAS[chave]) for chave in VARIAVEIS]
    df = df[df[col_vars].apply(limpar_texto).notna().any(axis=1)]
    print(f'Linhas com participante: {len(df)}')

    if args.excluir_turmas:
        col_turma = localizar_coluna(df, COLUNAS['turma'])
        excluir = {normalizar(t) for t in args.excluir_turmas}
        df = df[~limpar_texto(df[col_turma]).map(lambda t: not pd.isna(t) and normalizar(t) in excluir)]
        print(f'Sem as turmas {", ".join(args.excluir_turmas)}: {len(df)}')

    if args.somente_concluintes:
        col_conclusao = localizar_coluna(df, COLUNAS['conclusao'])
        df = df[limpar_texto(df[col_conclusao]).map(lambda v: not pd.isna(v) and normalizar(v).startswith('s'))]
        print(f'Concluintes (declaração = Sim): {len(df)}')

    resumo, freq = analisar(df, args.separador_local, args.top_profissoes, args.top_locais)

    print()
    print(para_markdown(resumo))
    for nome, tabela in freq.items():
        if nome != 'Mapeamento':
            print(f'\n--- {nome} ---')
            print(tabela.to_string(index=False))

    pasta = salvar(resumo, freq, args.saida)
    print(f'\nArquivos salvos em: {pasta.resolve()}')


if __name__ == '__main__':
    main()
