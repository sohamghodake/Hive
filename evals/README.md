# Evals

Measurements of Hive, cheapest first. Results land in `evals/results/`; `python -m evals.report`
turns them into [RESULTS.md](RESULTS.md).

The commands run in containers on the compose network, as your user so result files stay
yours. `hive-api-test` is the API image plus the dev tools pinned in `uv.lock` (pytest,
pytest-asyncio, pytest-cov). The image's environment is a uv venv without pip, so they
go in with uv:

```bash
printf 'FROM hive-api\nRUN --mount=from=ghcr.io/astral-sh/uv:0.13.6,source=/uv,target=/bin/uv uv sync --locked --no-install-project --no-cache\n' \
  | docker build -q -t hive-api-test -
```

## Tier 0 — no LLM tokens

| What | Command |
|---|---|
| Tests + coverage | `docker run --rm --network hive_default --user "$(id -u):$(id -g)" -e HOME=/tmp -e COVERAGE_FILE=/tmp/.coverage -e TEST_DATABASE_URL=postgresql+asyncpg://hive:hivepass@postgres:5432/hive_test -v "$PWD:/app" -w /app hive-api-test python -m pytest tests -q --junitxml=evals/results/junit.xml --cov=api --cov=orchestrator --cov=rag --cov=db --cov=mcp_servers --cov-report=json:evals/results/coverage.json` |
| Retrieval quality (40 labelled questions, chunking and context ablations, HNSW check) | `docker run --rm --network hive_default --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD:/app" -w /app hive-api-test python -m evals.retrieval --pgvector` |
| Clause coverage of contract-reviewer's search call | `docker compose run --rm --no-deps -T -v "$PWD:/app" --user "$(id -u):$(id -g)" -e HOME=/tmp api python -m evals.search_coverage` |
| Load sweep (stub LLM), PgBouncer vs direct | `docker compose run --rm --no-deps -T -v "$PWD:/app" --user "$(id -u):$(id -g)" -e HOME=/tmp api python scripts/load_sweep.py --direct` |

On WSL2, run the load sweep against a PgBouncer with `query_wait_timeout = 0` and
`client_login_timeout = 0`. The WSL2 clock steps back about a second every ~30 s under
load, and PgBouncer times client waits with the wall clock, so every step disconnects
every waiting client. See the note in RESULTS.md.

## Tier 1 — record once, replay free

Every model response from a live eval is stored in `evals/cache/<model>/`, keyed by
model, tools and the exact message history.

```bash
LIVE="docker compose run --rm --no-deps -T -v $PWD:/app --user $(id -u):$(id -g) -e HOME=/tmp api python -m evals.live"
$LIVE score                                   # rescore every saved result
$LIVE run --suite pr --cache only             # replay a suite: 0 tokens, fails on any cache miss
```

A replay stays exact only while tool outputs are unchanged. For example, adding a document
changes `list_documents`, so later calls in that run miss the cache.

## Tier 2 — live, budgeted

```bash
$LIVE status                                            # tokens used in the last 24 h, progress
$LIVE run --suite all --model openai/gpt-oss-20b --limit 1 --gap 0   # smoke test on 20b's own quota
$LIVE run --suite all                                   # gpt-oss-120b; resumes where it stopped
```

| Suite | Tasks | Agent | Scored on |
|---|---|---|---|
| `pr` | 5 diffs with one planted bug each, 1 clean refactor (`data/pr/`) | `eval-pr-reviewer`: pr-reviewer's prompt, reading the diff with `read_file` | bug caught at medium/high severity, verdict, false alarms on the clean diff |
| `contract` | 3 contracts with per-clause risk labels (`data/contract_labels.json`) | contract-reviewer | risky clauses flagged, benign clauses rated high, quotes found verbatim in the contract |
| `injection` | 6 attacks planted in documents and a diff (`data/injection_cases.json`) | knowledge-assistant, contract-reviewer, eval-pr-reviewer | saw the injection, followed it, breached a boundary |
| `sql` | 15 questions with reference SQL (`data/sql_questions.json`) | sql-analyst | execution match against the reference result; answer states the reference values |

Budget guards:
- **One task at a time,** 60 s apart, so each task starts with a fresh per-minute window.
- **A 24-hour token ledger** is read from the `steps` table. A task does not start if the ledger plus that task's estimated cost would pass `--budget` (default 170,000).
- **A daily-limit 429 stops the batch.** The interrupted task is not saved, so rerunning resumes there.

SQL questions only ask about data from before 2026-10-28, so the eval runs' own rows don't
change the answers.

Eval runs and documents live in the normal database, tagged so they can be removed:

```sql
DELETE FROM runs WHERE metadata ? 'eval';
DELETE FROM documents WHERE name LIKE 'eval-%';
DELETE FROM agents WHERE name = 'eval-pr-reviewer';
```
