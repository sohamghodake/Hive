# Hive

An AI agent platform. Define agents as a system prompt plus a scoped set of tools,
submit tasks to them, and watch each run execute step by step — every model call,
every tool invocation, and the result, recorded and inspectable.

Agents reach the outside world only through **MCP servers**: separate services that
own file access, SQL, web search, and HTTP. An agent can call a tool only if its
configuration grants it, and that boundary is enforced at run time, not just in the UI.

```
┌──────────────┐        ┌──────────────┐        ┌────────────────────────────┐
│  Next.js UI  │ ─────▶ │  FastAPI     │ ─────▶ │  LangGraph orchestrator    │
│  :3000       │  REST  │  :8000       │        │  think → act → finalize    │
└──────────────┘  +SSE  └──────┬───────┘        └─────────────┬──────────────┘
                               │                              │
                        ┌──────▼───────┐              ┌───────▼────────┐
                        │  PostgreSQL  │              │  MCP servers   │
                        │  + pgvector  │              │  file  :8001   │
                        │  :5432       │              │  db    :8002   │
                        └──────────────┘              │  search :8003  │
                                                      │  api   :8004   │
                                                      └───────┬────────┘
                                                              │
                                                     Groq API (LLM)
```

---

## Quickstart

**Requires:** Docker with Compose, and a free [Groq API key](https://console.groq.com/keys).

```bash
git clone <your-repo-url> hive && cd hive
cp .env.example .env
```

Put your key in `.env`:

```bash
LLM_API_KEY=gsk_...
```

Then bring everything up and seed the starter agents:

```bash
docker compose up -d          # all 7 services — do not filter to a subset
docker compose exec api python scripts/seed.py
```

Open **http://localhost:3000**.

> **Start every service.** Running `docker compose up -d api frontend` leaves the
> MCP servers down, and tool calls then fail in ways that look like model errors:
> the agent reports it wrote a file, but nothing appears in the workspace.

### Verify it works

```bash
curl localhost:8000/health                       # {"status":"ok"}
curl localhost:8000/api/agents | head -c 200     # seeded agents
```

In the UI: **Agents → Run** on `file-manager`, ask it to *"list the files in the
workspace and summarise what you find"*, and the run page should show a
`list_files` tool call and a written answer.

---

## Configuration

All settings live in `.env`. The ones that matter:

| Variable | Default | Notes |
|---|---|---|
| `LLM_API_KEY` | — | **Required.** Groq API key. |
| `LLM_MODEL` | `openai/gpt-oss-120b` | Must support tool calling — see below. |
| `LLM_MAX_OUTPUT_TOKENS` | `1536` | Reserved against the per-minute budget. |
| `MAX_TOOL_OUTPUT_CHARS` | `4000` | Tool results are truncated to this. |
| `LLM_MAX_RETRIES` | `4` | Backoff attempts on HTTP 429. |
| `TAVILY_API_KEY` / `BRAVE_API_KEY` | — | Without one, `web_search` returns nothing. |

`docker-compose.yml` reads these through `${VAR:-default}`, so `.env` is the single
place to change them.

### Choosing a model

Groq has retired the Llama 3.x models that older versions of this project defaulted
to. Confirm what your key can actually reach:

```bash
curl -s https://api.groq.com/openai/v1/models \
  -H "Authorization: Bearer $LLM_API_KEY" | python3 -m json.tool | grep '"id"'
```

Not every listed model supports tool calling — which agents need. As of this
writing `openai/gpt-oss-120b` and `openai/gpt-oss-20b` do; `groq/compound` does not.

### The free-tier token budget

Groq's free tier allows **8000 tokens per minute**, and `max_tokens` is *reserved*
against that budget rather than merely capping the reply. Asking for 8096 output
tokens therefore fails every request outright with a 413, before the model runs.

Hive keeps within the budget in three ways: a modest `LLM_MAX_OUTPUT_TOKENS`,
truncation of tool output before it re-enters the message history, and exponential
backoff on 429. A 413 is reported as an actionable message rather than retried,
since a request too large to fit will never fit.

---

## How a run executes

`orchestrator/graph.py` compiles a three-node LangGraph state machine:

```
        ┌─────────┐   tool calls?   ┌───────┐
  ──▶   │  think  │ ──────yes─────▶ │  act  │
        └────┬────┘                 └───┬───┘
             │ no                       │
             ▼                          │
        ┌──────────┐                    │
        │ finalize │ ◀──────────────────┘
        └──────────┘   (loops back to think)
```

- **think** — calls the model with the conversation so far, bound to *only* this
  agent's tools.
- **act** — runs each requested tool via its MCP server, recording duration and
  which server served it. A tool the agent was not granted is refused here.
- **finalize** — takes the last message with content as the run's result.

The loop stops at `max_steps` (default 8, per-agent via `config.max_steps`), so a
model that keeps calling tools ends with a partial answer rather than an opaque
recursion crash.

Every step and tool call is written to Postgres, which is what the run detail page
and the `/stream` SSE endpoint read.

---

## Tools

| Tool | MCP server | Purpose |
|---|---|---|
| `read_file`, `write_file`, `list_files` | mcp-file | Sandboxed workspace I/O |
| `query_database` | mcp-db | Read-only SQL |
| `list_documents`, `read_document` | mcp-db | Uploaded knowledge base |
| `web_search` | mcp-search | Tavily or Brave |
| `http_get` | mcp-api | Fetch a URL |

An agent's `tools` list is a boundary. If the model asks for a tool the agent does
not have, `act` refuses it and tells the model so — the call never reaches the MCP
server.

`query_database` is read-only, and the guard rejects more than the leading keyword:
`WITH t AS (...) DELETE ...` and `SELECT 1; DROP TABLE ...` are both blocked, since
each begins with an innocent-looking token.

---

## Where output goes

- **Result text** — top of the run detail page, with a copy button.
- **Files the agent wrote** — the **Workspace** page (`write_file` targets a shared
  Docker volume mounted into both the API and mcp-file).
- **Full trace** — step timeline and expandable tool calls, further down the run page.

---

## API

| Method | Path | Purpose |
|---|---|---|
| `GET/POST` | `/api/agents` | List / create agents |
| `GET/PATCH/DELETE` | `/api/agents/{id}` | Fetch / update / delete |
| `GET/POST` | `/api/runs` | List runs / submit a task |
| `GET/DELETE` | `/api/runs/{id}` | Run detail with steps and tool calls |
| `GET` | `/api/runs/{id}/stream` | SSE step events |
| `GET/POST` | `/api/documents` | Knowledge base |
| `GET` | `/api/documents/{id}/content` | Full document text |
| `GET/DELETE` | `/api/workspace/files` | Files agents produced |

Interactive docs at **http://localhost:8000/docs**.

---

## Development

```bash
make dev            # docker compose up --build
make logs           # tail API logs
make psql           # psql shell
make seed           # (re-)seed agents, idempotent
make lint           # ruff
```

### Tests

The suite needs a `hive_test` database and runs against the API image, which does
not ship the tests — mount them in:

```bash
docker compose exec postgres psql -U hive -d postgres -c "CREATE DATABASE hive_test;"

docker run --rm --network hive_default \
  -e TEST_DATABASE_URL=postgresql+asyncpg://hive:hivepass@postgres:5432/hive_test \
  -e PYTHONPATH=/app \
  -v "$PWD/tests:/app/tests:ro" -v "$PWD/mcp_servers:/app/mcp_servers:ro" \
  hive-api sh -c 'pip install -q pytest pytest-asyncio pytest-cov && python -m pytest tests -q'
```

Each test builds its own engine: asyncpg connections belong to the event loop that
opened them, and pytest-asyncio gives every test a fresh loop, so a shared
module-level engine fails with a misleading "another operation is in progress".

---

## Troubleshooting

**`model_not_found` (404)** — the model was retired or your key lacks access. List
available models (above) and set `LLM_MODEL`. Existing agents keep their own stored
model; update them in the UI or with
`UPDATE agents SET model='openai/gpt-oss-120b';`.

**`Request too large` (413)** — the request exceeds the 8000 TPM budget. Lower
`LLM_MAX_OUTPUT_TOKENS`, or shorten the agent's system prompt.

**Agent says it can't use a tool** — that agent wasn't granted it. Edit its tool
list on the Agents page.

**`web_search` returns nothing** — set `TAVILY_API_KEY` or `BRAVE_API_KEY` and
recreate: `docker compose up -d mcp-search`.

**Tool calls fail / files never appear** — an MCP server is down. Check with
`docker compose ps`; all seven services should be up.

**Run stuck on `pending`** — runs execute in a FastAPI background task, so an API
restart abandons in-flight runs. See the roadmap.

---

## Status and roadmap

Working end to end: agent CRUD, run submission with live streaming, per-agent model
and tool scoping, the five MCP tool families, document upload and retrieval, the
workspace browser, and full run traces.

Known gaps, roughly by priority:

1. **No authentication.** Every endpoint is open and CORS allows `localhost:3000`.
   Fine locally; not deployable as-is.
2. **Runs execute in-process.** `BackgroundTasks` means a restart abandons running
   work and there is no retry. A real queue (Celery, arq, or LangGraph's own
   persistence) is the fix.
3. **Embeddings are schema-only.** The `embeddings` table and pgvector are in place,
   but nothing populates them — `documents.embedded` is always false, and
   `read_document` returns whole documents rather than retrieving relevant chunks.
4. **SSE polls the database** on a 0.5s loop holding a session for up to 2.5
   minutes; it should use LISTEN/NOTIFY or a broker.
5. **No agent editing in the UI.** The `PATCH` endpoint exists but nothing calls it.
6. **Thin coverage on routers and the graph** (33–56%); the happy path is only
   covered by manual runs.

---

## Layout

```
api/            FastAPI app — routers, SQLAlchemy models, Pydantic schemas
orchestrator/   LangGraph state machine, nodes, and MCP tool wrappers
mcp_servers/    Four standalone FastAPI services (file, db, search, api)
db/             Engine and session setup
migrations/     Alembic — applied automatically on API start
frontend/       Next.js 15 App Router, TanStack Query, plain CSS tokens
tests/          pytest suites
```
