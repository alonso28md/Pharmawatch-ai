#!/usr/bin/env python
"""Write the FastAPI OpenAPI schema to frontend/openapi.json (no server, no model calls).

The frontend generates its typed client from this file:
    python scripts/export_openapi.py && (cd frontend && npm run gen:api)
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.api.main import app  # noqa: E402


def main() -> None:
    target = ROOT / "frontend" / "openapi.json"
    target.write_text(
        json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote {target.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
