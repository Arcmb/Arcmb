"""Verify TRI dashboard v3.3."""
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def require(value,message):
    if not value:
        raise RuntimeError(message)

def main():
    model=(ROOT/"model_data.py").read_text(encoding="utf-8")
    tri=(ROOT/"static"/"tri_scores.js").read_text(encoding="utf-8")
    home=(ROOT/"static"/"student_summary.js").read_text(encoding="utf-8")
    html=(ROOT/"static"/"app.html").read_text(encoding="utf-8")
    css=(ROOT/"static"/"style.css").read_text(encoding="utf-8")

    require("# === TRI DASHBOARD V3.3 ===" in model,"TRI dashboard backend marker missing.")
    require("simulation['triScores']" in model and "'general': scores.get('tri')" in model,"TRI scores are not exposed per simulation.")
    for marker in (
        "// === TRI DASHBOARD V3.3 ===",
        "Simulados exibidos",
        "Notas dos simulados selecionados",
        "Evolução TRI por área",
        "Histórico de redações",
        "data-tri-dashboard-all",
        "data-tri-dashboard-key",
    ):
        require(marker in tri,"Missing TRI dashboard marker: "+marker)
    for marker in (
        "// === TRI HOME DASHBOARD V3.3 ===",
        "Acertos/TCT por área",
        "Evolução da TRI geral",
        "TRI por área",
    ):
        require(marker in home,"Missing home TRI marker: "+marker)
    require("1º" not in home[home.find("// === TRI HOME DASHBOARD V3.3 ==="):],"Ordinal simulation labels still exist in TRI home override.")
    require("/static/tri_scores.js?v=3.7.14" in html,"TRI dashboard cache key is missing.")
    require("/static/student_summary.js?v=3.7.0" in html,"Student summary cache key is missing.")
    require("TRI DASHBOARD V3.3" in css,"TRI dashboard CSS is missing.")
    compile(model,"model_data.py","exec")
    print("MEUCRONOGRAMA_TRI_DASHBOARD_CHECK_OK: area TRI, chronological named evolution, simulation filters and essay history passed.",flush=True)

if __name__=="__main__":
    main()
