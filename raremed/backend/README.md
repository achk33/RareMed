# RareMed AI backend

FastAPI service for Version 0.1. Clinical reasoning is not implemented.

From the repository root, with PostgreSQL running:

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\pip install -r backend\requirements-dev.txt
$env:PYTHONPATH = "backend"
backend\.venv\Scripts\alembic -c backend\alembic.ini upgrade head
backend\.venv\Scripts\uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
```

The Docker image runs migrations, then binds to `0.0.0.0:$PORT`.

Interactive API docs: http://localhost:8000/docs

See the repository README for the full stack.
