# RareMed AI

Version 0.6 adds a bounded Cytoscape explorer in the admin knowledge-graph page. Staff can search, filter, expand, inspect provenance, and highlight asserted paths without downloading the full Neo4j graph. Load and rollback stay admin-only. Version 0.5 retrieval, Version 0.4 ingestion, Version 0.3 sign-in, and Version 0.2 local Ollama chat remain.

The model is a language and demonstration assistant. It does not interpret symptoms as a diagnosis, rank diseases, or invent citations. Graph relations come only from imported datasets. The product is decision support. It is not a clinically validated diagnostic tool.

## Version 0.2 chat

Install the model once:

```powershell
ollama pull qwen3:4b
```

If PowerShell does not find `ollama`, the Windows app is usually here:

```powershell
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" pull qwen3:4b
```

The default is `qwen3:4b` in `backend/app/ai/model.json`: temperature `0.6`, context `2048`, extended thinking off. Set `OLLAMA_THINK=true` to enable thinking. `OLLAMA_BASE_URL` points at Ollama (`http://localhost:11434` on the host, `http://host.docker.internal:11434` from the backend container).

`POST /api/v1/chat` streams tokens as server-sent events. The workspace shows them as they arrive, and Stop and Regenerate control the current reply. `GET /api/v1/models` reports whether `qwen3:4b` is installed. The older `POST /api/v1/conversations/{id}/messages` route still stores the fixed foundation reply and does not call the model.

Chat can answer in English, French, Arabic, and Moroccan Darija. A reply is not saved when PostgreSQL is down, but generation still runs.

### See whether the model is on the GPU

Start a reply, then in another terminal:

```powershell
ollama ps
```

The `PROCESSOR` column shows `GPU` when the model is on the graphics card, and `100% CPU` when it is not. On an NVIDIA machine, `nvidia-smi` lists the Ollama process and its GPU memory while a reply is streaming. Windows Task Manager, under Performance → GPU, moves at the same time.

## Version 0.3 accounts

Create an account at `/register`, then sign in at `/login`. The API sets an HTTP-only `raremed_session` cookie. The browser does not store the session token in `localStorage`. Logout revokes the server session and clears the cookie.

Registration always creates a `user` account. A `clinician` or `admin` role is assigned in the database or through `PATCH /api/v1/admin/users/{id}` after you sign in as an admin. Set `ADMIN_EMAIL` and `ADMIN_PASSWORD` if you want the API to create the first admin on startup.

Every conversation is scoped to the signed-in owner. Another account receives `conversation_not_found` rather than the other person's messages. Admin routes (`/api/v1/datasets`, `/api/v1/graph/status`, `/api/v1/admin/users`) are checked by FastAPI.

`GET /api/v1/conversations` supports search (`q`), archive filters, and offset pagination. `GET /api/v1/conversations/{id}` returns the newest page of messages and `has_more` for older pages. Interrupted replies are stored with `status=interrupted` so a refresh can regenerate them. Message `extra` is reserved for later medical evidence, HPO entities, and diagnostic sessions; those fields stay empty in this version.

Alembic revision `0002_auth_sessions` adds users, sessions, ownership, archive, and message metadata. Apply it with `alembic upgrade head` from `backend`.

Keep this version on a private machine.

## Version 0.4 ingestion

Download official files yourself into `data/raw/`. The pipeline never overwrites them and never uses a language model to invent missing medical relationships.

Expected named files:

- `data/raw/hpo/hp.obo`
- `data/raw/hpo/phenotype.hpoa`

This checkout also accepts present alternatives when those names are absent: `hp.json`, official Orphadata XML (product 1 and product 4), and MONDO `json` / `obo` / `owl`. Missing required names are reported. `python -m app.ingestion run --strict` fails if `hp.obo` or `phenotype.hpoa` is absent.

From `backend`:

```powershell
$env:PYTHONPATH = "backend"
backend\.venv\Scripts\python -m app.ingestion inspect
backend\.venv\Scripts\python -m app.ingestion run
backend\.venv\Scripts\python -m app.ingestion status
backend\.venv\Scripts\python -m app.ingestion rollback
```

Outputs:

- `data/processed/runs/<id>/` — entities, relationships, mappings, warnings, manifest
- `data/imports/runs/<id>/` — graph nodes and edges
- `data/processed/current.json` and `data/imports/current.json` — current successful run

Staff accounts can open `/admin/ingestion` to see source path, version, import status, counts, warnings, and the last successful import. Alembic revision `0003_ingestion_runs` stores run history when PostgreSQL is available.

## Version 0.5 knowledge graph

`python -m app.graph load` reads `data/imports/current.json`, applies Neo4j uniqueness constraints, and writes batched parameterized Cypher. Repeated loads are idempotent. A failed job rolls back nodes and relationships created by that run. Schema: [docs/graph-schema.md](docs/graph-schema.md).

From `backend`:

```powershell
$env:PYTHONPATH = "backend"
backend\.venv\Scripts\python -m app.graph load
backend\.venv\Scripts\python -m app.graph stats
backend\.venv\Scripts\python -m app.graph rollback
```

Staff accounts can open `/admin/knowledge-graph` to explore a bounded neighborhood: search, kind and source filters, lazy expansion, path highlighting, evidence inspection, and PNG export. The browser never receives the complete graph. Load and rollback require an admin account. Variant and diagnostic-test nodes are created only when a verified source record exists.

## Version 0.6 graph explorer

Explorer routes live under `/api/v1/graph/explore/` and require a clinician or admin session. They return paginated search hits and capped neighborhoods (80 nodes / 120 edges on the canvas, 24 neighbors per expand). Public clinical retrieval stays on `/api/v1/graph/diseases`, `/phenotypes`, `/neighborhood`, and `/provenance`. Graph exploration is read-only. Any later edit operation must go through an explicit review workflow.

## What you need

- Docker Desktop, for the full stack
- Optional, for tests and host-side development: Python 3.12 and Node.js 20

Ollama is not part of Compose. Leave it on Windows and point the API at it. Version 0.1 only checks that it answers. It does not ask it to write a reply.

## Launch with Docker

From this folder:

```powershell
copy .env.example .env
docker compose up --build
```

Then open:

- Workspace: http://localhost:3000
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/health
- Status: http://localhost:8000/api/v1/status
- Neo4j browser: http://localhost:7474 (user `neo4j`, password `raremed-neo4j`)

The first start waits for Postgres and Neo4j, applies the Alembic migration, then serves the API. The development passwords in `docker-compose.yml` and `.env.example` are local only.

Stop the stack with `docker compose down`. Database volumes remain until `docker compose down -v`.

### Ollama from a container

Compose sets `OLLAMA_BASE_URL` to `http://host.docker.internal:11434`. Start Ollama on Windows first if you want the status page to show it as connected. The chat still uses the fixed Version 0.1 reply.

For a host-side API process, use `http://localhost:11434` instead.

## Launch without Docker

Start Postgres and Neo4j yourself, or run only those two services:

```powershell
docker compose up postgres neo4j
copy .env.example .env
python -m venv backend\.venv
backend\.venv\Scripts\pip install -r backend\requirements-dev.txt
$env:PYTHONPATH = "backend"
backend\.venv\Scripts\alembic -c backend\alembic.ini upgrade head
backend\.venv\Scripts\uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
```

In another terminal:

```powershell
cd frontend
copy .env.example .env.local
npm install
npm run dev
```

The dev server binds to port 3000. The browser calls `http://localhost:8000`.

## Try the workspace

1. Open http://localhost:3000 and read the decision-support notice.
2. Create an account, sign in, then open Workspace. The header shows whether `qwen3:4b` is ready. Insert the synthetic test message and send it. Tokens appear as they arrive. Stop interrupts the reply. Refresh the page to reload the same thread. The sidebar groups threads by date and can search, rename, archive, or delete them.
3. Open Settings to see the signed-in account, then switch theme and language. Arabic uses a right-to-left layout.
4. Open Admin with a clinician or admin account. Source files already in `data/raw/` are listed by name and size on Overview. Open Ingestion to inspect versions and run an import. A user account is rejected by the API.
5. Open Knowledge graph. Load the current import into Neo4j, then search a disease or HPO term. Neighborhoods are bounded. The page does not rank diagnoses.

The paperclip does not upload anything.

## Datasets

Download medical sources yourself and leave them in:

- `data/raw/hpo/`
- `data/raw/orphadata/`
- `data/raw/mondo/`
- `data/raw/literature/`

`data/processed/` and `data/imports/` receive ingestion output. `data/samples/` contains one synthetic interface fixture and is safe to keep in git. Raw downloads are gitignored. The application does not modify raw files.

Files already present under `data/raw/` are left as they are.

## Tests

Backend, from the repository root:

```powershell
backend\.venv\Scripts\pip install -r backend\requirements-dev.txt
backend\.venv\Scripts\python -m pytest
```

Health, conversation, discovery, and an in-memory database round trip run without Docker. The PostgreSQL connectivity test runs when Postgres answers on `DATABASE_URL`, and it is skipped when nothing is listening.

Frontend:

```powershell
cd frontend
npm install
npm test
npm run build
```

`npm test` covers the landing and admin links, the decision-support label, and the disabled upload notice.

After the stack is up:

```powershell
python scripts\check_stack.py
```

## Layout

```
frontend/     Next.js workspace
backend/      FastAPI, Alembic, Neo4j and Ollama probes
data/         raw sources, reserved folders, synthetic samples
tests/        backend pytest suite; frontend navigation tests run from the frontend package
scripts/      local status check
```

Later clinical features can extend `backend/app/services/assistant.py`, `backend/app/graph/`, and `backend/app/ingestion/` without changing the conversation or discovery contracts. Another inference backend can replace Ollama by setting `INFERENCE_PROVIDER` to `openai` or `vllm` and the matching base URL. Both use the OpenAI-compatible chat API. The chat route calls that provider through `backend/app/ai/providers/` rather than calling Ollama itself.
