"""Apply migrations, then serve the API on 0.0.0.0:$PORT."""

import os
import sys

import uvicorn


def main() -> None:
    from alembic import command
    from alembic.config import Config

    alembic_config = Config("alembic.ini")
    command.upgrade(alembic_config, "head")

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, factory=False)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
