"""Hotfix v3.7.9: strict A-E import normalization only."""
from pathlib import Path

ROOT=Path(__file__).resolve().parent
PY_MARKER="# === STRICT A-E IMPORT V3.7.9 ==="

def main():
    model=ROOT/'model_data.py'
    source=model.read_text(encoding='utf-8')
    if PY_MARKER not in source:
        anchor="    text = str(value).strip().upper()\n"
        if source.count(anchor) != 1:
            raise RuntimeError(
                f'Expected exactly one answer-normalization anchor, found {source.count(anchor)}.'
            )
        strict=(
            "    text = str(value).strip().upper()\n"
            "    # === STRICT A-E IMPORT V3.7.9 ===\n"
            "    # Only one isolated alternative is valid. Everything else is error = 0.\n"
            "    if text in ('A', 'B', 'C', 'D', 'E'):\n"
            "        return text\n"
            "    return 0\n"
        )
        source=source.replace(anchor,strict,1)
        source=source.replace(
            "resposta deve ser A, B, C, D, E, 1, 0, ponto (.), x/x, asterisco (*) ou vazio.",
            "somente A, B, C, D ou E são alternativas válidas; qualquer outro conteúdo é considerado erro (0).",
        )
        model.write_text(source,encoding='utf-8')

    for path in (ROOT/'static'/'model_data.js', ROOT/'static'/'result_import.js'):
        if not path.exists():
            continue
        text=path.read_text(encoding='utf-8')
        text=text.replace(
            'Célula em branco, ponto (.), x/x ou asterisco (*) será considerada erro quando houver gabarito válido.',
            'Somente uma alternativa isolada A, B, C, D ou E é válida. Qualquer outro conteúdo (ex.: A/A, A|A, A | A, x, x/x, números, símbolos ou texto) será considerado erro (0).'
        )
        path.write_text(text,encoding='utf-8')

    site=ROOT/'site_version_release.py'
    if site.exists():
        text=site.read_text(encoding='utf-8').replace('PUBLIC_VERSION="3.7.8"','PUBLIC_VERSION="3.7.9"')
        site.write_text(text,encoding='utf-8')

    vsite=ROOT/'verify_site_version.py'
    if vsite.exists():
        text=vsite.read_text(encoding='utf-8').replace('v3.7.8','v3.7.9')
        vsite.write_text(text,encoding='utf-8')

    print(
        "MEUCRONOGRAMA_STRICT_AE_IMPORT_READY: only isolated A-E remain valid; every other answer/gabarito pattern becomes error 0.",
        flush=True,
    )

if __name__=='__main__':
    main()
