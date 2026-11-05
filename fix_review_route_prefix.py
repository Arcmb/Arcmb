from pathlib import Path

ROOT=Path(__file__).resolve().parent
OLD_BATCH='/api/review-errors/sync-batch'
NEW_BATCH='/api/model-data/review-errors-sync-batch'
OLD_ONE='/api/review-errors/sync'
NEW_ONE='/api/model-data/review-errors-sync'


def patch(path):
    text=path.read_text(encoding='utf-8')
    before=text
    text=text.replace(OLD_BATCH,NEW_BATCH).replace(OLD_ONE,NEW_ONE)
    if text!=before:
        path.write_text(text,encoding='utf-8')
    return text


def main():
    model=patch(ROOT/'model_data.py')
    app=patch(ROOT/'static'/'app.js')
    importer=patch(ROOT/'static'/'result_import.js')
    verifier=ROOT/'verify_exam_review_sync.py'
    if verifier.exists():
        text=verifier.read_text(encoding='utf-8')
        marker="require('EXAM ERROR REVIEW SYNC V1' in js and 'Atualizar erros dos simulados' in js,'Review UI sync is missing.')"
        replacement=marker+"\n            require('/api/model-data/review-errors-sync' in js,'Review sync must use the model-data dispatcher prefix.')"
        if marker in text and 'model-data/review-errors-sync' not in text:
            verifier.write_text(text.replace(marker,replacement,1),encoding='utf-8')
    if NEW_ONE not in model or NEW_ONE not in app:
        raise RuntimeError('Review sync route prefix was not applied.')
    if OLD_ONE in model or OLD_ONE in app or OLD_ONE in importer:
        raise RuntimeError('Legacy review sync route remains in generated assets.')
    print('MEUCRONOGRAMA_REVIEW_ROUTE_READY: review sync now uses the model-data dispatcher and no longer returns 404.',flush=True)


if __name__=='__main__':
    main()
