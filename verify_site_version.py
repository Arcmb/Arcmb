"""Verify the public version shown by Meu Cronograma Qi."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent

def require(value,message):
    if not value:
        raise RuntimeError(message)

def main():
    html=(ROOT/"static"/"app.html").read_text(encoding="utf-8")
    require("v3.2.0" in html,"Public version v3.2.0 is not present in app.html.")
    require(not re.search(r"(?i)\bv\.?\s*2\.8(?:\.1)?\b",html),"Legacy public v2.8 label is still present.")
    print("MEUCRONOGRAMA_PUBLIC_VERSION_CHECK_OK: visible site version is v3.2.0.",flush=True)

if __name__=="__main__":
    main()
