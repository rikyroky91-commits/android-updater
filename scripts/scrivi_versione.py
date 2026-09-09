"""Metadati dell'immagine, generati una volta durante la build Docker."""
from datetime import datetime, timezone
from pathlib import Path
import json
import os

if __name__ == "__main__":
    (Path(__file__).resolve().parent.parent / "release.json").write_text(
        json.dumps({"commit": os.environ.get("RENDER_GIT_COMMIT") or None,
                    "build_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}),
        encoding="utf-8")
