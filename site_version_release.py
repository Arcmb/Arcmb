"""Set the public-facing Meu Cronograma Qi version after all legacy builders."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
PUBLIC_VERSION = "3.7.14"

def main():
    path=ROOT/"static"/"app.html"
    html=path.read_text(encoding="utf-8")
    # Legacy builders intentionally keep internal compatibility identifiers.
    # The public label is finalized here, at the end of the build.
    html=re.sub(r"(?i)\bv\.?\s*2\.8(?:\.1)?\b", f"v{PUBLIC_VERSION}", html)
    html=re.sub(r"(?i)Meu Cronograma(?: Qi)?\s+2\.8(?:\.1)?\b", f"Meu Cronograma Qi v{PUBLIC_VERSION}", html)
    html=html.replace("Meu Cronograma v"+PUBLIC_VERSION, "Meu Cronograma Qi v"+PUBLIC_VERSION)
    path.write_text(html,encoding="utf-8")

    # Keep the legacy selective verifier functional, but align only its
    # release-label assertion with the new public version.
    verifier=ROOT/"verify_selective.py"
    source=verifier.read_text(encoding="utf-8")
    pattern=r"require\('v[0-9.]+'in source and '/static/selective\.js'in source,'[^']*assets missing\.'\)"
    replacement=(
        "require('v"+PUBLIC_VERSION+"'in source and '/static/selective.js'in source,"
        "'v"+PUBLIC_VERSION+" assets missing.')"
    )
    source,count=re.subn(pattern,replacement,source,count=1)
    if count!=1:
        raise RuntimeError("Legacy selective release-label assertion was not found exactly once.")
    verifier.write_text(source,encoding="utf-8")

    print(
        f"MEUCRONOGRAMA_PUBLIC_VERSION_READY: public UI and selective release-label assertion aligned to v{PUBLIC_VERSION}; functional checks unchanged.",
        flush=True,
    )

if __name__=="__main__":
    main()
