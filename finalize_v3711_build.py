"""Final build guard for management-filter v3.7.11."""
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def main():
    html_path=ROOT/'static'/'app.html'
    html=html_path.read_text(encoding='utf-8')
    html=html.replace('/static/student_summary.js?v=3.7.111','/static/student_summary.js?v=3.7.11')
    html_path.write_text(html,encoding='utf-8')

    for verifier in ROOT.glob('verify_*.py'):
        source=verifier.read_text(encoding='utf-8')
        source=source.replace('v3.7.111','v3.7.11')
        source=source.replace('student_summary.js?v=3.7.111','student_summary.js?v=3.7.11')
        verifier.write_text(source,encoding='utf-8')

    print('MEUCRONOGRAMA_V3711_FINAL_GUARD_READY: final cache/version assertions normalized after public versioning.',flush=True)

if __name__=='__main__':
    main()
