"""Every test run uses a throwaway settings folder, so this computer's own settings (say, production
mode turned on for a demo) never change what a test sees."""
import os
import tempfile

os.environ["LOCALAPPDATA"] = tempfile.mkdtemp()
os.environ.pop("CAREBRIDGE_PRODUCTION", None)
