from pathlib import Path

def dump(path, needle, before=3500, after=7000):
    p=Path(path)
    s=p.read_text(encoding="utf-8")
    i=s.find(needle)
    print(f"=== DEBUG_BEGIN {path} {needle} ===", flush=True)
    print(s[max(0,i-before):i+after] if i>=0 else f"{needle} not found", flush=True)
    print(f"=== DEBUG_END {path} {needle} ===", flush=True)

dump("static/tri_scores.js", "tri-import-confirm")
dump("model_data.py", "/api/model-data/tri-confirm", 5000, 10000)
