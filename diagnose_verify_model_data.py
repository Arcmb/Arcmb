"""Temporary diagnostic wrapper for the legacy model-data verifier."""
import traceback
import verify_model_data

try:
    verify_model_data.main()
except Exception as exc:
    print('MEUCRONOGRAMA_V27_DIAGNOSTIC: ' + repr(exc), flush=True)
    traceback.print_exc()
    raise SystemExit(16)
