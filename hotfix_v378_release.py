"""Hotfix v3.7.8: final TRI template exporter normalization after every later override."""
from pathlib import Path

ROOT=Path(__file__).resolve().parent
MARK="# === TRI TEMPLATE FINAL BYTES V3.7.8 ==="

PATCH=r'''
# === TRI TEMPLATE FINAL BYTES V3.7.8 ===
def _qi_tri_template_workbook():
    headers = [
        'NOME', 'LOGIN (opcional)', 'NOME DO SIMULADO', 'DATA DE APLICAÇÃO', 'TURMA',
        'RANKING', 'NOTA TRI GERAL', 'TRI LINGUAGENS', 'TRI HUMANAS',
        'TRI NATUREZA', 'TRI MATEMÁTICA',
        'TEMA DA REDAÇÃO', 'C1', 'C2', 'C3', 'C4', 'C5', 'NOTA DA REDAÇÃO',
    ]
    rows = [['' for _ in headers] for _ in range(200)]
    help_headers = ['Campo', 'Orientação']
    help_rows = [
        ['NOME', 'Obrigatório. Deve corresponder ao nome usado no resultado já importado.'],
        ['LOGIN', 'Opcional. Serve apenas como apoio; o vínculo principal continua pelo nome.'],
        ['NOME DO SIMULADO', 'Informe o mesmo nome da avaliação já importada.'],
        ['DATA DE APLICAÇÃO', 'Use dd/mm/aaaa ou aaaa-mm-dd.'],
        ['TURMA', 'Use o nome oficial cadastrado no Painel de bordo ou um alias autorizado.'],
        ['RANKING', 'Posição do aluno no simulado, quando disponível.'],
        ['NOTA TRI GERAL', 'Nota oficial geral.'],
        ['TRI POR ÁREA', 'Linguagens, Humanas, Natureza e Matemática. Deixe vazio quando a área não foi aplicada.'],
        ['TEMA DA REDAÇÃO', 'Opcional. Texto do tema/proposta da redação.'],
        ['C1–C5', 'Cada competência deve estar entre 0 e 200.'],
        ['NOTA DA REDAÇÃO', 'De 0 a 1000. Se ficar vazia e C1–C5 estiverem completos, o sistema calcula a soma.'],
        ['REGRA DE ATUALIZAÇÃO', 'Campos vazios não apagam notas existentes. Respostas A–E, acertos, mapa de questões e cronograma são preservados.'],
        ['ARQUIVO', 'Use XLSX sem fórmulas, macros, proteção ou vínculos externos.'],
    ]
    output = T.export(
        headers,
        rows,
        first_name='TRI e Redação',
        extra_sheets=[('Como preencher', help_headers, help_rows)],
    )
    if isinstance(output, tuple):
        output = next(
            (item for item in output if isinstance(item, (bytes, bytearray))),
            None,
        )
    if not isinstance(output, (bytes, bytearray)):
        raise ValueError('Não foi possível gerar o arquivo-modelo TRI e Redação.')
    return bytes(output)
'''

def main():
    model=ROOT/'model_data.py'
    source=model.read_text(encoding='utf-8')
    if MARK not in source:
        model.write_text(source.rstrip()+"\n\n"+PATCH.strip()+"\n",encoding='utf-8')

    site=ROOT/'site_version_release.py'
    source=site.read_text(encoding='utf-8').replace('PUBLIC_VERSION="3.7.7"','PUBLIC_VERSION="3.7.8"')
    site.write_text(source,encoding='utf-8')

    vsite=ROOT/'verify_site_version.py'
    source=vsite.read_text(encoding='utf-8').replace('v3.7.7','v3.7.8')
    vsite.write_text(source,encoding='utf-8')

    print("MEUCRONOGRAMA_TRI_TEMPLATE_FINAL_BYTES_READY: final TRI/Redação workbook exporter returns raw XLSX bytes after all overrides.",flush=True)

if __name__=='__main__':
    main()
