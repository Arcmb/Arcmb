"""Verificação estática da v3.7.17. Não cria contas nem grava no banco."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    webapp = (ROOT / 'webapp.py').read_text(encoding='utf-8')
    for needle, label in (
        ('import provisional_access as PROVISIONAL', 'import'),
        ('PROVISIONAL.schema(self,c)', 'schema'),
        ('PROVISIONAL.expired(self,c,user):\n                        error=PROVISIONAL.EXPIRED_MESSAGE', 'login'),
        ("if path!='/api/logout' and PROVISIONAL.expired(self,c,user)", 'session'),
        ("PROVISIONAL.clear(self,c,user['id'])", 'password change'),
        ("'account_created_by_coordinator');PROVISIONAL.start(", 'coordinator create'),
        ("PROVISIONAL.start(app, c, target_id, user.get('id'))", 'bulk create'),
        ("if path.startswith('/api/provisional'):", 'route'),
        ("'provisional_renewal.js':'application/javascript", 'static allowlist'),
    ):
        require(needle in webapp, f'v3.7.17 {label} hook missing.')
    require(webapp.count("PROVISIONAL.start_if_student(self,c,target_id,user['id'])") == 2, 'Master create/edit hooks missing.')
    require("PROVISIONAL.start_if_student(self,c,account['id'],user['id'])" in webapp, 'Master password reset hook missing.')
    require((ROOT / 'static' / 'provisional_renewal.js').exists(), 'Renewal asset missing.')
    html = (ROOT / 'static' / 'app.html').read_text(encoding='utf-8')
    require('/static/provisional_renewal.js?v=' in html, 'Renewal script tag missing.')
    import provisional_access as PA
    require(PA.VALIDITY_SECONDS == 7 * 86400, 'Validity must be 7 days.')
    print('MEUCRONOGRAMA_V3717_PROVISIONAL_EXPIRY_CHECK_OK: 7-day provisional password hooks present.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('MEUCRONOGRAMA_V3717_PROVISIONAL_EXPIRY_CHECK_FAILED:', exc, flush=True)
        sys.exit(1)
