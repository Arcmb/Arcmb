"""Verify student search, responsive review layout and Qi logo delivery."""
from pathlib import Path
import os
from webapp import App
from verify_release import Client, require

ROOT=Path(__file__).resolve().parent


def main():
    html=(ROOT/'static'/'app.html').read_text(encoding='utf-8')
    js=(ROOT/'static'/'responsive_ui_refinement.js').read_text(encoding='utf-8')
    css=(ROOT/'static'/'style.css').read_text(encoding='utf-8')
    webapp=(ROOT/'webapp.py').read_text(encoding='utf-8')
    for marker in ('Pesquisar aluno','account-search-list','installAccountSearch'):
        require(marker in js,'Missing account-search marker: '+marker)
    for marker in ('RESPONSIVE UI SEARCH AND QI LOGO V1','min-width:1450px','--review-discipline-width','table-layout:fixed'):
        require(marker in css,'Missing responsive-table marker: '+marker)
    require('/static/responsive_ui_refinement.js?v=5.2.0' in html,'Responsive UI script is not loaded.')
    require('/static/qi-logo.svg?v=5.2.0' in html,'Qi logo cache key is missing.')
    require("'qi-logo.svg':'image/svg+xml; charset=utf-8'" in webapp,'Qi logo is not served.')
    require("'responsive_ui_refinement.js':'application/javascript; charset=utf-8'" in webapp,'Responsive UI script is not served.')
    app=App();host=os.getenv('RENDER_EXTERNAL_HOSTNAME') or sorted(app.hosts)[0];client=Client(app,host)
    require(client.request('/static/qi-logo.svg')['status']==200,'Qi logo did not return HTTP 200.')
    require(client.request('/static/responsive_ui_refinement.js')['status']==200,'Responsive UI script did not return HTTP 200.')
    require(client.request('/static/review_history.js')['status']==200,'Review history asset did not return HTTP 200.')
    require(client.request('/static/review_calendar_table.js')['status']==200,'Review calendar asset did not return HTTP 200.')
    print('MEUCRONOGRAMA_RESPONSIVE_UI_CHECK_OK: student search, responsive review table and Qi logo HTTP delivery passed.',flush=True)


if __name__=='__main__':main()
