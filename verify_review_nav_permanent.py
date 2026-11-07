"""Verify that the review-table menu entry is part of the base app navigation."""
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def require(value,message):
    if not value:raise RuntimeError(message)


def main():
    app=(ROOT/'static'/'app.js').read_text(encoding='utf-8')
    html=(ROOT/'static'/'app.html').read_text(encoding='utf-8')
    marker="['review-table','Tabela de revisões']"
    require(marker in app,'Tabela de revisões is missing from the base navigation.')
    reviews_positions=[position for token in ("['reviews','Minhas revisões']",'["reviews","Minhas revisões"]') if (position:=app.find(token))>=0]
    require(reviews_positions,'Minhas revisões navigation entry was not found.')
    require(min(reviews_positions)<app.find(marker),'Tabela de revisões must follow Minhas revisões.')
    require('/static/app.js?v=2.9.5' in html,'Base app cache key was not updated.')
    require('/static/review_table_page.js?v=5.4.1' in html,'Review-table cache key was not updated.')
    print('MEUCRONOGRAMA_REVIEW_NAV_CHECK_OK: permanent menu entry and cache keys passed.',flush=True)


if __name__=='__main__':main()
