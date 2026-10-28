# Hive

[![CI](https://github.com/sohamghodake/Hive/actions/workflows/ci.yml/badge.svg)](https://github.com/sohamghodake/Hive/actions/workflows/ci.yml)

A self-hosted multi-agent platform. Define agents as a system prompt plus a scoped
set of tools, give them a task — review this contract, review this pull request,
answer this question from the database — and watch each run execute step by step.
Every model call, tool invocation, token count, and the structured result is written
to PostgreSQL, where it can be inspected or queried later.

Agents reach the outside world only through four **Model Context Protocol servers**
(file, database, web search, HTTP), each its own Docker service. An agent can call a
tool only if its configuration grants it, and that boundary is enforced at run time.

```
┌──────────────┐        ┌──────────────┐        ┌────────────────────────────┐
│  Next.js UI  │ ─────▶ │  FastAPI     │ ─────▶ │  LangGraph orchestrator    │──▶ Groq (LLM)
│  :3000       │  REST  │  :8000       │        │  think → act → finalize    │
└──────────────┘  +SSE  └──────┬───────┘        └─────────────┬──────────────┘
                               │                              │ MCP (streamable HTTP)
                        ┌──────▼───────┐              ┌───────▼────────┐
                        │  PgBouncer   │◀─────────────│  mcp-file      │
                        │  transaction │              │  mcp-db  (RAG) │
                        │  pooling     │              │  mcp-search    │
                        └──────┬───────┘              │  mcp-api       │
                        ┌──────▼───────┐              └────────────────┘
                        │  PostgreSQL  │
                        │  + pgvector  │
                        └──────────────┘
```

Eight services: `api`, `frontend`, `postgres`, `pgbouncer`, and the four MCP servers.

**Measured results** — agent accuracy on labelled tasks (with gpt-oss-120b), retrieval
quality, prompt-injection resistance, concurrency and cost per task — are in
[evals/RESULTS.md](evals/RESULTS.md); [evals/README.md](evals/README.md) explains how
to rerun each one.

---

## Quickstart

**Requires:** Docker with Compose, and a free [Groq API key](https://console.groq.com/keys).

```bash
git clone <your-repo-url> hive && cd hive
cp .env.example .env          # then set LLM_API_KEY=gsk_...
docker compose up -d          # all 8 services — do not filter to a subset
docker compose exec api python scripts/seed.py
```

Open **http://localhost:3000**. The first build downloads a ~130 MB embedding model
into the `api` and `mcp-db` images, so it takes a few minutes; later starts are fast.

### Try the three knowledge-work agents

| Agent | Try | What it does |
|---|---|---|
| `contract-reviewer` | Upload a contract PDF on **Documents**, then run *"Review <file> from the customer's perspective"* | Semantic search for each clause type, risk rating per clause, report to `reviews/`, findings as JSON |
| `pr-reviewer` | *"Review pallets/click#2800"* | Fetches the PR diff, reviews for bugs → security → maintainability, writes `reviews/pr-…md`, verdict as JSON |
| `sql-analyst` | *"Which agent has the most failed runs, and what share failed?"* | Inspects the schema, writes and runs read-only SQL, retries on errors, returns the SQL with the answer |

Each finishes with a ```` ```json ```` block that the orchestrator parses into
`runs.output->'data'` (JSONB), so results are queryable:

```sql
SELECT output->'data'->>'overall_risk', output->'data'->'findings'
FROM runs r JOIN agents a ON a.id = r.agent_id
WHERE a.name = 'contract-reviewer' AND status = 'completed';
```

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

- **think** calls the model bound to *only* this agent's tools. It asks for whatever
  output budget the per-minute token limit leaves after the prompt (see below), and
  records token usage and `finish_reason` on the step.
- **act** runs each requested tool as an MCP `tools/call`, recording duration and the
  serving MCP server. A tool the agent was not granted is refused here.
- **finalize** takes the final answer, parses a trailing JSON block into
  `output.data`, and flags `truncated` (ran out of tokens) or `stopped_early` (hit
  `max_steps`) so a partial result is never presented as complete.

The graph runs with `astream`, and each node's step is **committed as soon as the
node finishes**. The `/api/runs/{id}/stream` SSE endpoint polls for new steps with a
fresh short session per poll, so the dashboard shows progress while the run is still
going rather than everything at the end.

Runs execute in-process. If the API restarts mid-run, startup marks those runs
`failed` with an explanation instead of leaving them "running" forever.

---

## Model Context Protocol servers

Each server is a [FastMCP](https://gofastmcp.com) app speaking MCP over streamable
HTTP at `/mcp` (`initialize`, `tools/list`, `tools/call`), so any MCP client can use
it, not just Hive's orchestrator. Each also serves `GET /health` for Compose healthchecks.

| Server | Tools | Notes |
|---|---|---|
| `mcp-file` | `read_file`, `write_file`, `list_files`, `delete_file` | Sandboxed to `/workspace` |
| `mcp-db` | `query`, `list_tables`, `describe_table`, `list_documents`, `read_document`, `search_documents` | Read-only SQL; pgvector semantic search |
| `mcp-search` | `web_search` | Tavily or Brave; errors clearly if neither key is set |
| `mcp-api` | `http_get`, `http_post` | Public addresses only (SSRF guard) |

Ports are not published (the servers have no auth). To point an external MCP client
at one, publish its port temporarily and connect to `http://localhost:<port>/mcp`.

The agent-facing tool registry (`orchestrator/tools.py`) wraps these as LangChain
tools through a thin MCP client (`orchestrator/mcp_client.py`).

---

## Retrieval (pgvector RAG)

1. **Upload** — `POST /api/documents`. PDFs are text-extracted with `pypdf`; other
   files are decoded as UTF-8. The response returns immediately.
2. **Index** — a background task splits the text into ~1000-character chunks with
   150-character overlap (breaking on paragraphs, then sentences, then words),
   embeds them with **BAAI/bge-small-en-v1.5** via fastembed (local ONNX on CPU, no
   API key), and stores 384-dimension vectors in `embeddings`. The Documents page
   shows *indexing…* until it is done.
3. **Search** — `search_documents` embeds the query with the same model (bge's
   query prefix applied) and runs cosine-distance nearest-neighbour search on an
   **HNSW** index, optionally scoped to one document.

The agent tool accepts several queries in one call — a contract review asks about
eight clause types in one round trip — and keeps the highest-scoring passages that
fit a character budget, rather than truncating the result list blindly.

Ingestion embeds in slices of 64 chunks with two ONNX threads. Unbounded, a 400 KB
CSV once pushed the API past the kernel's OOM limit; bounded, it indexes 586 chunks
at a peak of ~870 MiB while `/health` stays under 60 ms.

The API shares one `rag/` module with `mcp-db` (both images build from the repo
root), so documents and queries are always embedded by the same model.

---

## Data layer and PgBouncer

- **SQLAlchemy 2.0 async + asyncpg** throughout, with **one engine per process**.
  Runs previously each created their own engine, so N concurrent runs opened N pools.
- **PgBouncer in transaction pooling mode** sits between every application
  connection (API, runs, SSE, mcp-db) and Postgres. Alembic migrations bypass it
  and connect directly.
- Transaction pooling shares a server connection between clients, so asyncpg is
  configured with no client-side statement cache and random prepared-statement
  names (`db/session.py`), and PgBouncer tracks protocol-level prepared statements
  (`max_prepared_statements`).

### Load test

`scripts/load_test.py` runs the real pipeline — LangGraph, MCP tool calls, per-step
persistence — with only the LLM stubbed (400 ms per turn; real concurrent runs would
measure Groq's rate limiter). A separate connection samples `pg_stat_activity`.

`scripts/load_sweep.py` runs 1, 2 and 4 simulated API workers (separate processes)
at 10, 50 and 100 concurrent runs each, against Postgres' default `max_connections = 100`:

| Path | Runs completed | Peak Postgres backends |
|---|---|---|
| Through PgBouncer, all 9 configurations | **2,450 / 2,450** | **12–31**, flat as workers are added |
| Direct, 4 workers × 50 | 316 / 400 | 99 — `sorry, too many clients already` |

PgBouncer does not make a run faster; it keeps backend usage flat as workers are added.
Throughput varied about 2× between identical sweeps on the WSL2 machine used, so it is
not quoted here; full tables are in [evals/RESULTS.md](evals/RESULTS.md).

On WSL2, the sweep was measured with PgBouncer's `query_wait_timeout` and
`client_login_timeout` set to 0. Under load, WSL2 steps the wall clock back about a second
every ~30 s. PgBouncer times client waits with the wall clock, so each step disconnects
every waiting client at once (2–10% of runs at 4 workers), even though no client had
waited more than a second. This is an environment artifact, not a pooling limit.

```bash
docker compose exec api python scripts/load_test.py --runs 200 --concurrency 100
docker compose exec -e DATABASE_URL=postgresql+asyncpg://hive:hivepass@postgres:5432/hive \
  api python scripts/load_test.py --runs 200 --concurrency 100    # direct, for comparison
```

---

## Security boundaries

- **Tool scoping.** The model is bound only to the agent's tools, and `act` refuses
  any tool not granted, so the call never reaches an MCP server.
- **SQL.** `mcp-db` connects as `hive_reader` (migration 003), a role with `SELECT`
  on the six application tables and nothing else. `READ ONLY` alone was not enough:
  it stops writes, but as the `hive` superuser the model's SQL could still call
  `pg_read_file()` on the database server. Each query also runs in a `READ ONLY`
  transaction with a 5 s `statement_timeout`, and a cursor stops the server after
  200 rows instead of materialising the whole result. A keyword filter in front
  refuses stacked statements and CTE-wrapped writes (`WITH t AS (...) DELETE ...`).
- **Files.** Paths resolve and must stay inside `/workspace`, compared by path
  component — a string-prefix check would accept the sibling `/workspace_evil`.
- **Outbound HTTP.** `http_get` resolves the host and refuses anything that is not a
  public address: loopback, private ranges (which covers `postgres` and the other
  services on the Docker network), and `169.254.169.254` cloud metadata. Redirects
  are followed by hand and re-checked at every hop. DNS rebinding between the check
  and the connection is not yet closed.
- **Network.** MCP server ports are not published to the host. Postgres is published
  on `127.0.0.1` only.

---

## Configuration

All settings live in `.env`; `docker-compose.yml` reads them with defaults.

| Variable | Default | Notes |
|---|---|---|
| `LLM_API_KEY` | — | **Required.** Groq API key. |
| `LLM_MODEL` | `openai/gpt-oss-120b` | Must support tool calling. |
| `LLM_TPM_BUDGET` | `8000` | Groq's tokens-per-minute limit; raise on a paid tier. |
| `LLM_MAX_OUTPUT_TOKENS` | `4096` | Cap on the per-call output budget. |
| `LLM_REASONING_EFFORT` | `low` | gpt-oss spends output tokens on hidden reasoning. |
| `MAX_TOOL_OUTPUT_CHARS` | `6000` | Longer tool output is cut at a line boundary, with a marker. |
| `TAVILY_API_KEY` / `BRAVE_API_KEY` | — | Needed for `web_search`. |
| `EMBED_BATCH_SIZE` / `EMBED_THREADS` | `16` / `2` | Bounds embedding memory. |

### The free-tier token budget

Groq's free tier allows 8000 tokens per minute, and `max_tokens` is *reserved*
against that budget: prompt + `max_tokens` must fit or the request fails with 413.
A fixed value is wrong both ways — too high and long conversations 413, too low and
answers are cut off mid-sentence. So each call requests the budget left after an
estimate of its prompt, between 512 and `LLM_MAX_OUTPUT_TOKENS`.

On 429, Hive waits the time Groq's error states ("try again in 7.5s") rather than
guessing. On 413 it fails with an actionable message, since retrying cannot help. When
the *daily* limit is spent, Groq asks for a wait of up to hours; the run fails at once
instead of spending more of the daily request allowance on retries. Each think step
records its model time, rate-limit wait and retries, so slow runs can be attributed.

### Choosing a model

```bash
curl -s https://api.groq.com/openai/v1/models \
  -H "Authorization: Bearer $LLM_API_KEY" | python3 -m json.tool | grep '"id"'
```

Agents need tool calling: `openai/gpt-oss-120b` and `openai/gpt-oss-20b` support it;
`groq/compound` does not.

---

## API

| Method | Path | Purpose |
|---|---|---|
| `GET/POST` | `/api/agents` | List / create agents |
| `GET/PATCH/DELETE` | `/api/agents/{id}` | Fetch / update / delete |
| `GET/POST` | `/api/runs` | List runs / submit a task |
| `GET/DELETE` | `/api/runs/{id}` | Run detail with steps and tool calls |
| `GET` | `/api/runs/{id}/stream` | Live step events (SSE) |
| `GET/POST` | `/api/documents` | List / upload (PDF or text; indexed in background) |
| `GET` | `/api/documents/{id}/content` | Full document text |
| `POST` | `/api/documents/{id}/reindex` | Rebuild a document's embeddings |
| `GET/DELETE` | `/api/workspace/files` | Files agents produced |

Interactive docs at **http://localhost:8000/docs**.

---

## Development

```bash
make dev            # docker compose up --build
make logs           # tail API logs
make psql           # psql shell
docker compose exec api python scripts/seed.py --update   # refresh starter agents' prompts/tools
```

### Dependencies

`pyproject.toml` lists what the code imports, and `uv.lock` pins those and everything
they pull in. The api image installs from the lock with `uv sync --locked`, which fails
the build if the two disagree. Each MCP image installs its own `requirements.txt`,
exported from the same lock with hashes. After changing a dependency, run `make lock`
and commit the regenerated files with it.

### Tests

The suite covers tool scoping, step budgets, the SQL/file/SSRF guards, all four MCP
servers over the real protocol (fastmcp's in-memory client), the read-only database
role, whole runs through `run_agent` with a scripted model, upload → index → search,
chunking, structured-output parsing, rate-limit handling, and the API. CI
([`ci.yml`](.github/workflows/ci.yml)) runs it on every push and pull request against a
pgvector service container, along with ruff and a check that the lock files are current.

Locally it needs [uv](https://docs.astral.sh/uv/) and a `hive_test` database:

```bash
docker compose up -d postgres
docker compose exec postgres createdb -U hive hive_test
make install    # the locked environment, plus pytest and ruff
make test
make lint
```

The `hive_reader` privilege test is skipped unless `TEST_READER_DATABASE_URL` points at
a database migrated to head. CI sets it. Against the compose stack, run
`TEST_READER_DATABASE_URL=postgresql://hive_reader:hivereader@localhost:5432/hive make test`.

To run the same checks before every commit and push, install the git hooks once with
`lefthook install` (see `lefthook.yml`).

---

## Troubleshooting

**`model_not_found` (404)** — the model was retired or your key lacks access. Set
`LLM_MODEL`; existing agents keep their stored model, so also update them
(`UPDATE agents SET model='openai/gpt-oss-120b';`).

**Run is slow, logs show "rate limited, retrying"** — the 8000 TPM budget is spent;
Hive waits the time Groq asks for. Multi-step agents on the free tier routinely
pause between turns.

**Result marked "cut off"** — the model hit its output limit. Lower
`LLM_REASONING_EFFORT` or shorten the task.

**Agent says it can't use a tool** — that agent wasn't granted it.

**`web_search` says it is not configured** — set `TAVILY_API_KEY` or `BRAVE_API_KEY`,
then `docker compose up -d mcp-search`.

**Document stuck on "indexing…"** — check `docker compose logs api | grep -i index`,
then `POST /api/documents/{id}/reindex`. Scanned PDFs have no text layer and are
rejected at upload.

---

## Known gaps

1. **No authentication.** Every endpoint is open. Fine locally; not deployable as-is.
2. **Runs execute in-process** (`BackgroundTasks`). A restart fails in-flight runs
   rather than resuming them; a durable queue is the fix.
3. **SSE polls** the database every 0.5 s; LISTEN/NOTIFY would push instead.
4. **DNS rebinding** can slip past the SSRF check between resolution and connection.
5. **Free-tier limits** cap tool output (6000 chars), so very large PR diffs are
   reviewed partially; the agent is told when content was cut.
6. **No agent editing in the UI** — the `PATCH` endpoint exists but nothing calls it.

---

## Layout

```
api/            FastAPI app — routers, models, schemas, ingestion service
orchestrator/   LangGraph graph and nodes, MCP client, agent tool registry
mcp_servers/    Four FastMCP servers (file, db, search, api), one image each
rag/            Chunking + embeddings, shared by api and mcp-db
pgbouncer/      PgBouncer image and config (transaction pooling)
db/             Engine and session setup
migrations/     Alembic — applied automatically on API start (direct to Postgres)
scripts/        seed.py (starter agents), load_test.py, load_sweep.py
evals/          retrieval, search-coverage and live agent evals; RESULTS.md
frontend/       Next.js 15 App Router, TanStack Query, plain CSS tokens
tests/          pytest suites
```
