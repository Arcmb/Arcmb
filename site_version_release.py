"""Set the public-facing Meu Cronograma Qi version after all legacy builders."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
PUBLIC_VERSION="3.2.0"

def main():
    path=ROOT/"static"/"app.html"
    html=path.read_text(encoding="utf-8")
    # Legacy builders intentionally keep internal compatibility at 2.8.
    # Only the version shown to the user is modernized here, at the end of build.
    html=re.sub(r"(?i)\bv\.?\s*2\.8(?:\.1)?\b", f"v{PUBLIC_VERSION}", html)
    html=re.sub(r"(?i)Meu Cronograma(?: Qi)?\s+2\.8(?:\.1)?\b", f"Meu Cronograma Qi v{PUBLIC_VERSION}", html)
    html=html.replace("Meu Cronograma v"+PUBLIC_VERSION, "Meu Cronograma Qi v"+PUBLIC_VERSION)
    path.write_text(html,encoding="utf-8")
    print(f"MEUCRONOGRAMA_PUBLIC_VERSION_READY: public UI version is v{PUBLIC_VERSION}; internal compatibility identifiers are unchanged.",flush=True)

if __name__=="__main__":
    main()
