"""
Pre-deploy step for the Cloudflare Worker.
Copies blocks/index.json into worker/src/ so it gets bundled at deploy time.
Run before: wrangler deploy
"""
import shutil
from pathlib import Path

root = Path(__file__).parent.parent
src = root / "blocks" / "index.json"
dst = root / "worker" / "src" / "blocks-index.json"

if not src.exists():
    print("ERROR: blocks/index.json not found. Run scripts/generate_index.py first.")
    raise SystemExit(1)

shutil.copy2(src, dst)
print(f"Bundled {src} -> {dst}")
