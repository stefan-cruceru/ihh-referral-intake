"""Every test run uses a throwaway settings folder, so this computer's own settings (say, production
mode turned on for a demo) never change what a test sees. The repo root is on the path for demo/."""
import os
import sys
import tempfile
from pathlib import Path

os.environ["LOCALAPPDATA"] = tempfile.mkdtemp()
os.environ.pop("CAREBRIDGE_PRODUCTION", None)
# The practice patients sit in demo/ at the repo root, apart from the app.
sys.path.append(str(Path(__file__).resolve().parents[2]))
