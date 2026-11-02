"""Usage: uv run python -m seed   (requires SEED_DEMO_PASSWORD)."""

import sys

from app.core.config import get_settings
from app.core.db import SessionLocal
from seed import run


def main() -> int:
    password = get_settings().seed_demo_password
    if not password:
        print("SEED_DEMO_PASSWORD is not set", file=sys.stderr)
        return 1
    with SessionLocal() as db:
        report = run(db, password)
    print(f"created: {report.created}")
    print(f"skipped: {report.skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
