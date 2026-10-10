import os
import shutil
import sys
import tempfile
from pathlib import Path

# Configure an isolated, offline environment BEFORE the app is imported.
_TMP = Path(tempfile.mkdtemp(prefix="scriptline-test-"))
os.environ.update({
    "LLM_PROVIDER": "mock",
    "DATA_DIR": str(_TMP / "data"),
    "OUTPUT_DIR": str(_TMP / "output"),
    "SCRIPT_WORKERS": "1",
})
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TMP, ignore_errors=True)
