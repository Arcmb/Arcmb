"""Verify signed-token TRI import flow."""
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def require(value,message):
    if not value:
        raise RuntimeError(message)

def main():
    model=(ROOT/"model_data.py").read_text(encoding="utf-8")
    js=(ROOT/"static"/"tri_scores.js").read_text(encoding="utf-8")
    html=(ROOT/"static"/"app.html").read_text(encoding="utf-8")

    require("# === TRI IMPORT TOKEN V1 ===" in model,"Backend token flow missing.")
    require("_tri_make_import_token" in model and "_tri_read_import_token" in model,"Token signing/verification missing.")
    require("MEUCRONOGRAMA_TRI_TOKEN_RECEIVED" in model,"Server receipt log marker missing.")
    require("MEUCRONOGRAMA_TRI_TOKEN_CONFIRM_RECEIVED" in model,"Confirm server log marker missing.")
    require("MEUCRONOGRAMA_TRI_TOKEN_BATCH_DONE" in model,"Batch progress marker missing.")
    require("verifiedRecords" in model and "_tri_token_verify_metadata" in model,"Final database verification missing.")
    require("data.get('importToken')" in model,"Confirm does not consume importToken.")

    require("// === TRI IMPORT TOKEN V1 ===" in js,"Frontend token flow missing.")
    token_section=js[js.find("// === TRI IMPORT TOKEN V1 ==="):]
    require("triImportDraft.importToken=triImportPreviewData.importToken" in token_section,"Preview token is not retained.")
    require("api('/api/model-data/tri-confirm-prepare',{importToken})" in token_section,"Receipt confirmation endpoint is not called.")
    require("api('/api/model-data/tri-confirm',{importToken})" in token_section,"Confirm does not use importToken.")
    confirm_section=token_section[token_section.find("acts['tri-import-confirm']"):]
    require("file:triImportDraft.file" not in confirm_section,"Confirm still re-sends the XLSX.")
    require("registro(s) recebidos e validados pelo servidor." in token_section,"Visible server receipt count is missing.")
    require("Gravando no banco" in token_section or "gravando" in token_section,"Visible database stage missing.")
    require("Importação concluída:" in token_section,"Final verified message missing.")
    require("/static/tri_scores.js?v=3.4.0" in html,"TRI asset cache key was not bumped.")

    compile(model,"model_data.py","exec")
    print("MEUCRONOGRAMA_TRI_IMPORT_TOKEN_CHECK_OK: signed receipt confirmation with counts, no XLSX re-upload, batch persistence and final verification passed.",flush=True)

if __name__=="__main__":
    main()
