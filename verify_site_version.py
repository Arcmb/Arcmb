"""Verify the public version shown by Meu Cronograma Qi."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent

def require(value,message):
    if not value:
        raise RuntimeError(message)

def main():
    html=(ROOT/"static"/"app.html").read_text(encoding="utf-8")
    selective=(ROOT/"verify_selective.py").read_text(encoding="utf-8")
    require("v3.2.2" in html,"Public version v3.2.2 is not present in app.html.")
    require(not re.search(r"(?i)\bv\.?\s*2\.8(?:\.1)?\b",html),"Legacy public v2.8 label is still present.")
    require("'v3.2.2'in source and '/static/selective.js'in source" in selective,"Legacy selective release-label assertion was not aligned.")
    print("MEUCRONOGRAMA_PUBLIC_VERSION_CHECK_OK: visible site version and legacy release-label verifier are aligned to v3.2.2.",flush=True)

if __name__=="__main__":
    main()
