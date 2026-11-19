"""Correção de divergências das importações na própria interface (v3.17.0).

Quando uma planilha de importação (respostas dos alunos, gabarito ou notas TRI) tem
divergências, o servidor devolve a lista completa delas, cada uma apontando a aba, a linha,
a coluna e o valor encontrado. A interface mostra uma janela onde o usuário corrige cada
valor (ou ignora a linha) e envia a lista de correções junto com o mesmo arquivo.

As correções são aplicadas sobre as células lidas da planilha, antes de qualquer validação:
todas as regras de importação continuam valendo, e o arquivo original não é alterado.

Formatos aceitos em data['fixes']:
  {'sheet': aba, 'line': linha, 'col': coluna, 'value': texto}  → troca o valor de uma célula
  {'sheet': aba, 'line': linha, 'skip': True}                     → ignora a linha inteira
  {'sheet': aba, 'col': coluna, 'from': texto, 'to': texto}       → troca um valor em toda a coluna
Linhas contam a partir de 1, como no Excel; colunas contam a partir de 0.
"""
import hashlib
import json
import unicodedata

MAX_FIXES = 5000
MAX_ISSUES = 400
MAX_VALUE = 500


def _norm(value):
    text = unicodedata.normalize('NFKD', str(value if value is not None else '')).encode('ascii', 'ignore').decode()
    return ' '.join(text.lower().split())


class CellIssue(ValueError):
    """Problema num campo de uma linha. Continua sendo um ValueError com a mesma mensagem."""

    def __init__(self, message, field=None, options=None, suggest=None):
        super().__init__(message)
        self.field = field
        self.options = options
        self.suggest = suggest


class ImportIssues(ValueError):
    """Várias divergências encontradas de uma vez; o servidor devolve a lista para a interface."""

    def __init__(self, issues, message=None):
        issues = list(issues)
        self.total = len(issues)
        self.issues = issues[:MAX_ISSUES]
        if message is None:
            first = ' · '.join(i.get('message', '') for i in self.issues[:3])
            more = f' (e mais {self.total - 3})' if self.total > 3 else ''
            message = (f'Encontramos {self.total} divergência(s) no arquivo: {first}{more}. '
                       'Corrija na janela de correção ou ajuste o arquivo e envie de novo.')
        super().__init__(message)


def normalize(raw):
    """Valida a lista de correções vinda da interface."""
    if raw in (None, ''):
        return []
    if not isinstance(raw, list) or len(raw) > MAX_FIXES:
        raise ValueError('Lista de correções inválida.')
    out = []
    for fix in raw:
        if not isinstance(fix, dict):
            raise ValueError('Correção inválida.')
        sheet = str(fix.get('sheet') or '')[:100]
        if 'from' in fix:
            col = fix.get('col')
            if type(col) is not int or not 0 <= col <= 2000:
                raise ValueError('Correção inválida: coluna.')
            out.append({'sheet': sheet, 'col': col, 'from': str(fix.get('from') if fix.get('from') is not None else '')[:MAX_VALUE],
                        'to': str(fix.get('to') if fix.get('to') is not None else '')[:MAX_VALUE]})
            continue
        line = fix.get('line')
        if type(line) is not int or not 1 <= line <= 200000:
            raise ValueError('Correção inválida: linha.')
        if fix.get('skip') is True:
            out.append({'sheet': sheet, 'line': line, 'skip': True})
            continue
        col = fix.get('col')
        if type(col) is not int or not 0 <= col <= 2000:
            raise ValueError('Correção inválida: coluna.')
        value = fix.get('value')
        out.append({'sheet': sheet, 'line': line, 'col': col,
                    'value': '' if value is None else str(value)[:MAX_VALUE]})
    return out


def digest(raw):
    """Impressão digital das correções, para que a confirmação use exatamente as mesmas."""
    fixes = normalize(raw)
    if not fixes:
        return ''
    return hashlib.sha256(json.dumps(fixes, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def apply(rows, sheet, raw):
    """Aplica as correções da aba "sheet" sobre as linhas lidas (lista de listas)."""
    fixes = [f for f in normalize(raw) if f['sheet'] == str(sheet or '')]
    if not fixes:
        return rows
    rows = [list(r) for r in rows]
    for fix in fixes:
        if 'from' in fix:
            wanted = _norm(fix['from'])
            for index, row in enumerate(rows):
                if index == 0:
                    continue
                if fix['col'] < len(row) and _norm(row[fix['col']]) == wanted:
                    row[fix['col']] = fix['to']
            continue
        index = fix['line'] - 1
        if index >= len(rows):
            continue
        if fix.get('skip'):
            rows[index] = [None] * len(rows[index])
            continue
        row = rows[index]
        while len(row) <= fix['col']:
            row.append(None)
        row[fix['col']] = fix['value']
    return rows


def cell_text(value):
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)[:MAX_VALUE]


def issue(sheet, line, col, header, value, message, options=None, kind='cell', suggest=None):
    """Uma divergência que a interface consegue mostrar e corrigir.

    "options" lista os valores válidos; "suggest" é um palpite do servidor (ex.: o nome do
    simulado usado no resto do arquivo), que a interface já deixa escolhido.
    """
    out = {'kind': kind, 'sheet': sheet, 'line': line, 'col': col, 'header': cell_text(header),
           'value': cell_text(value), 'message': str(message)}
    if options is not None:
        out['options'] = [cell_text(o) for o in options]
    if suggest is not None:
        out['suggest'] = cell_text(suggest)
    return out


def general(message):
    """Divergência sem uma célula específica (corrigida no arquivo ou com outra correção)."""
    return {'kind': 'general', 'sheet': '', 'line': None, 'col': None, 'header': '', 'value': '', 'message': str(message)}
