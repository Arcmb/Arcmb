from pathlib import Path
p=Path("static/tri_scores.js")
s=p.read_text(encoding="utf-8")
needle="tri-import-confirm"
i=s.find(needle)
print("=== TRI_CONFIRM_GENERATED_JS_BEGIN ===", flush=True)
print(s[max(0,i-3500):i+6000] if i>=0 else "tri-import-confirm not found", flush=True)
print("=== TRI_CONFIRM_GENERATED_JS_END ===", flush=True)
