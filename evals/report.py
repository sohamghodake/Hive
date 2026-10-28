"""Build evals/RESULTS.md from the files in evals/results/. Uses no tokens.

    python -m evals.report            # on the host or in any container with the repo
"""
from __future__ import annotations

import json
import re
import statistics
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from evals._util import DATA, RESULTS, ROOT, pct

PRIMARY = "gpt-oss-120b"


def _load(name):
    path = RESULTS / name
    return json.loads(path.read_text()) if path.exists() else None


def _live(suite: str, model: str = PRIMARY) -> dict:
    path = RESULTS / "live" / f"{suite}__{model}.json"
    return json.loads(path.read_text())["tasks"] if path.exists() else {}


def _p(n, d) -> str:
    return f"{n}/{d} ({n / d:.0%})" if d else "–"


def tests_section() -> list[str]:
    junit, cov = RESULTS / "junit.xml", _load("coverage.json")
    if not junit.exists() or not cov:
        return []
    suite = ET.parse(junit).getroot()
    suite = suite if suite.tag == "testsuite" else suite.find("testsuite")
    tests, failures, errors = (int(suite.get(k, 0)) for k in ("tests", "failures", "errors"))
    files = cov["files"]
    lines = ["## Tests and coverage", "",
             f"**{tests - failures - errors}/{tests} tests pass; line coverage {cov['totals']['percent_covered']:.0f}%** "
             "(api, orchestrator, rag, db, mcp_servers). The suite runs the real graph, persistence (hive_test) and "
             "MCP servers over fastmcp's in-memory transport; only the model is scripted.", "",
             "| module | coverage |", "|---|---|"]
    for name in ("orchestrator/graph.py", "orchestrator/nodes.py", "mcp_servers/mcp_db/main.py",
                 "api/services/ingest.py", "api/routers/runs.py", "rag/embeddings.py"):
        if name in files:
            lines.append(f"| `{name}` | {files[name]['summary']['percent_covered']:.0f}% |")
    return lines + [""]


def retrieval_section() -> list[str]:
    r = _load("retrieval.json")
    if not r:
        return []
    c = r["corpus"]
    lines = ["## Retrieval (RAG) quality — no LLM tokens", "",
             f"{c['questions']} hand-labelled questions over {c['documents']} documents ({c['chars']:,} chars): three "
             "contracts with overlapping clause types, a handbook and an API guide. Each question is paraphrased away "
             "from the source wording and labelled with an evidence phrase, so any chunking can be scored. "
             "*Global* searches every document; *scoped* searches only the right one (what contract-reviewer does).", "",
             "| chunks / overlap | embedded text | global hit@1 | hit@3 | hit@5 | MRR@10 | right doc @1 | scoped hit@3 |",
             "|---|---|---|---|---|---|---|---|"]
    for cfg in r["configs"]:
        g, s = cfg["global"], cfg["scoped"]
        ctx = {None: "chunk", "filename": "file name + chunk", "title": "title + chunk",
               "title+heading": "title + heading + chunk"}[cfg.get("context")]
        lines.append(f"| {cfg['chunk_chars']} / {cfg['overlap']} | {ctx} | {g['hit@1']:.0%} | {g['hit@3']:.0%} | "
                     f"{g['hit@5']:.0%} | {g['mrr@10']:.2f} | {g['doc@1']:.0%} | {s['hit@3']:.0%} |")
    prod = r["configs"][0]
    lines += ["", f"- First row is production. Most misses rank the document's title/preamble chunk first — "
              "questions naming the counterparty match it best. Embedding the title (or just the file name) with each "
              "chunk fixes that: global hit@1 "
              f"{prod['global']['hit@1']:.0%} → {next(c for c in r['configs'] if c.get('context') == 'title')['global']['hit@1']:.0%}.",
              f"- Query embedding p50 {r['query_embed_ms']['p50']} ms, p95 {r['query_embed_ms']['p95']} ms; "
              f"passage embedding {prod['embed_chunks_per_s']} chunks/s on 2 ONNX threads."]
    if "pgvector_hnsw" in r:
        pg = r["pgvector_hnsw"]
        lines.append(f"- pgvector HNSW path (same SQL as mcp-db): hit@3 {pg['global']['hit@3']:.0%}, "
                     f"top-5 overlap with exact search {pg['ann_vs_exact_overlap@5']:.0%}, "
                     f"query p50 {pg['sql_ms']['p50']} ms / p95 {pg['sql_ms']['p95']} ms.")

    cov = _load("search_coverage.json")
    if cov:
        prod_rows = next(iter(cov["strategies"].values()))
        total = sum(len(v["covered"]) + len(v["missing"]) for v in prod_rows.values())
        got = sum(len(v["covered"]) for v in prod_rows.values())
        best_name, best = max(cov["simulated_chunking"].items(),
                              key=lambda kv: sum(len(v["covered"]) for v in kv[1].values()))
        lines += ["", "### What contract-reviewer actually sees", "",
                  f"Its one `search_documents` call (8 clause queries) returns {got}/{total} ({got / total:.0%}) of the "
                  "labelled clauses across the three contracts, although every clause is in some query's top 3. The "
                  f"losses are the tool's output shaping for the 8K tokens/minute budget: passages cut at "
                  f"{700} characters, and a {cov['char_budget']:,}-character total that fits ~5 passages. Simulated with "
                  f"the production embedder and selection: {best_name} → "
                  f"{sum(len(v['covered']) for v in best.values())}/{total}."]
    return lines + [""]


def load_section() -> list[str]:
    r = _load("load_sweep.json")
    if not r:
        return []
    rows = r["rows"]
    lines = ["## Concurrency (stub LLM, real LangGraph + MCP + Postgres) — no LLM tokens", "",
             f"Each worker is a separate process with its own connection pool; the model is stubbed at "
             f"{r['stub_llm_latency_s'] * 1000:.0f} ms/turn so this measures the platform, not Groq.", "",
             "| path | workers × concurrency | runs completed | peak Postgres backends | runs/s | p95 run latency |",
             "|---|---|---|---|---|---|"]
    for x in rows:
        lines.append(f"| {x['path']} | {x['workers']} × {x['concurrency']} | {x['completed']}/{x['runs']} | "
                     f"{x['peak_backends']} | {x['runs_per_s']} | {x['p95_s']} s |")
    pg = [x for x in rows if x["path"] == "pgbouncer"]
    lines += ["", f"- Through PgBouncer: {sum(x['completed'] for x in pg)}/{sum(x['runs'] for x in pg)} runs, "
              f"Postgres backends {min(x['peak_backends'] for x in pg)}–{max(x['peak_backends'] for x in pg)} "
              "regardless of load. Direct: backends grow with workers until Postgres refuses clients.",
              "- Throughput varied ~2× between identical sweeps on this WSL2 machine; treat runs/s as a range.",
              "- On WSL2 the wall clock steps back ~1 s every ~30 s under load. PgBouncer measures client waits "
              "with the wall clock, so each step disconnects every waiting client with `query_wait_timeout` / "
              "`client_login_timeout` (2–10% of runs at 4 workers). This table was measured with those two "
              "timeouts disabled; with them on, failures lined up exactly with the clock steps.", ""]
    return lines


def _stats(records: list[dict]) -> dict:
    done = [r for r in records if r.get("duration_s") is not None]
    toks = [r["tokens"] for r in done if r.get("tokens")]
    durs = [r["duration_s"] for r in done]
    wait = sum(r.get("rate_limit_wait_s", 0) for r in done)
    return {
        "n": len(records),
        "tokens_mean": int(statistics.mean(toks)) if toks else 0,
        "tokens_total": sum(toks),
        "reasoning_share": (sum(r.get("reasoning_tokens", 0) for r in done) / max(1, sum(r.get("tokens_out", 0) for r in done))),
        "dur_p50": pct(durs, 50) if durs else 0, "dur_p95": pct(durs, 95) if durs else 0,
        "first_step_p50": pct([r["first_step_s"] for r in done if r.get("first_step_s") is not None], 50) if done else 0,
        "wait_share": wait / max(1e-9, sum(durs)),
        "retries": sum(r.get("retries", 0) for r in done),
        "llm_calls_mean": statistics.mean([r["llm_calls"] for r in done]) if done else 0,
        "truncated_tools": sum(1 for r in done for c in r.get("tool_calls") or [] if c.get("truncated")),
        "length_cutoffs": sum(1 for r in done for f in r.get("finish_reasons") or [] if f == "length"),
        "failed": sum(1 for r in records if r.get("status") != "completed"),
    }


def agents_section() -> list[str]:
    pr, contract, inj, sql = (_live(s) for s in ("pr", "contract", "injection", "sql"))
    if not any((pr, contract, inj, sql)):
        return []
    totals = {"pr": 6, "contract": 3, "injection": 6, "sql": 15}
    lines = [f"## Agent accuracy — live, {PRIMARY} on Groq's free tier", "",
             "Every task runs through the real stack (run_agent → MCP servers → Postgres) exactly as a UI run does, "
             "and is scored from what was stored. Tasks are single runs at the provider's default temperature, so "
             "each number is one sample, not an average. The first attempt of every task is the result; failed runs "
             "are not retried.", ""]
    everything = [r for recs in (pr, contract, inj, sql) for r in recs.values()]
    failed = [r for r in everything if r.get("status") != "completed"]
    if failed:
        lines += [f"**Reliability: {len(everything) - len(failed)}/{len(everything)} runs completed.** "
                  f"{len(failed)} failed because Groq rejected a tool call the model generated, and Hive does not "
                  "retry that error:", ""]
        for r in failed:
            msg = re.search(r"'message': ['\"](.+?)['\"], 'type'", r.get("error") or "")
            lines.append(f"- `{r['suite']}/{r['task']}`: {(msg.group(1) if msg else (r.get('error') or ''))[:150]}")
        lines.append("")

    if pr:
        buggy = [r for r in pr.values() if "bug_caught" in r["score"]]
        clean = [r for r in pr.values() if "false_alarms" in r["score"]]
        lines += ["### pr-reviewer — 5 diffs with one planted bug each, 1 clean refactor", "",
                  f"- **Bugs caught (medium/high severity): {_p(sum(r['score']['bug_caught'] for r in buggy), len(buggy))}**"
                  f"; mentioned at any severity: {_p(sum(r['score']['bug_mentioned'] for r in buggy), len(buggy))}",
                  f"- Verdict correct (request_changes on buggy, approve/comment on clean): "
                  f"{_p(sum(bool(r['score'].get('verdict_ok')) for r in pr.values()), len(pr))}",
                  f"- Clean diff: {sum(r['score']['false_alarms'] for r in clean)} medium/high false alarm(s), verdict "
                  f"`{clean[0]['score'].get('verdict') if clean else '–'}`", "",
                  "| diff | planted bug | caught | severity | verdict |", "|---|---|---|---|---|"]
        labels = {t["id"]: t for t in json.loads((DATA / "pr_labels.json").read_text())}
        for tid, r in sorted(pr.items()):
            s, bug = r["score"], labels[tid]["bug"]
            lines.append(f"| {tid} | {bug['what'] if bug else '(none — clean)'} | "
                         f"{'–' if bug is None else ('yes' if s.get('bug_caught') else 'no')} | "
                         f"{s.get('bug_severity') or '–'} | {s.get('verdict')} |")
        lines.append("")

    if contract:
        sc = [r["score"] for r in contract.values() if not r["score"].get("failed")]
        rf, rt = sum(s["risky_flagged"] for s in sc), sum(s["risky_total"] for s in sc)
        bh, bt = sum(s["benign_flagged_high"] for s in sc), sum(s["benign_total"] for s in sc)
        qg, qt = sum(s["quotes_grounded"] for s in sc), sum(s["quotes"] for s in sc)
        lines += ["### contract-reviewer — 3 contracts with labelled clause risk", "",
                  f"- **Risky clauses flagged medium/high: {_p(rf, rt)}**; benign clauses wrongly rated high: {_p(bh, bt)}",
                  f"- **Quotes found verbatim in the contract: {_p(qg, qt)}** (an ungrounded quote is invented text)",
                  f"- Overall risk rating correct: {_p(sum(s['overall_ok'] for s in sc), len(sc))}",
                  f"- Scored over the {len(sc)} of {len(contract)} runs that completed.", "",
                  "| contract | risky flagged | benign rated high | quotes grounded | overall | not assessed |",
                  "|---|---|---|---|---|---|"]
        for tid, r in sorted(contract.items()):
            s = r["score"]
            if s.get("failed"):
                lines.append(f"| {tid} | run failed: {(r.get('error') or '')[:60]} | | | | |")
                continue
            lines.append(f"| {tid} | {s['risky_flagged']}/{s['risky_total']} | {s['benign_flagged_high']}/{s['benign_total']} | "
                         f"{s['quotes_grounded']}/{s['quotes']} | {s['overall_risk']} | {', '.join(s['not_assessed']) or '–'} |")
        lines.append("")

    if inj:
        sc = {k: r["score"] for k, r in inj.items()}
        exposed = [k for k, s in sc.items() if s.get("exposed") or k == "pr-forced-approve"]
        lines += ["### Prompt injection — 6 attacks planted in documents and a diff", "",
                  f"- **Boundary breaches: {sum(bool(s.get('breached')) for s in sc.values())}** "
                  "(ungranted tool executed, file written outside the sandbox, internal URL fetched)",
                  f"- Model followed the injected instruction: {_p(sum(bool(sc[k].get('complied')) for k in exposed), len(exposed))} "
                  "of the cases where it saw the injection", "",
                  "| attack | saw it | followed it | breached a boundary | did the real task |", "|---|---|---|---|---|"]
        cases = {c["id"]: c for c in json.loads((DATA / "injection_cases.json").read_text())}
        for tid, s in sc.items():
            lines.append(f"| {cases[tid]['attack']} | {'yes' if s.get('exposed') else 'no'} | "
                         f"{'**yes**' if s.get('complied') else 'no'} | "
                         f"{'**yes**' if s.get('breached') else ('no' if 'breached' in s else 'n/a')} | "
                         f"{'yes' if s.get('task_ok') else ('no' if 'task_ok' in s else '–')} |")
        lines.append("")

    if sql:
        qs = {q["id"]: q for q in json.loads((DATA / "sql_questions.json").read_text())}
        sc = {k: r["score"] for k, r in sql.items()}
        ok = [k for k, s in sc.items() if s.get("exec_match")]
        lines += ["### sql-analyst — questions with reference SQL over Hive's own database", "",
                  f"- **Execution accuracy: {_p(len(ok), len(sc))}** (its SQL returns the reference result; column "
                  "order, extra columns and numeric rounding ignored)",
                  f"- Answer text states the reference values: "
                  f"{_p(sum(1 for s in sc.values() if s.get('answer_match')), len(sc))}",
                  "- A run that failed counts as wrong in both.", ""]
        by = {}
        for k in sc:
            by.setdefault(qs[k]["difficulty"], []).append(k)
        lines.append("| difficulty | execution accuracy |")
        lines.append("|---|---|")
        for d in ("easy", "medium", "hard"):
            if d in by:
                lines.append(f"| {d} | {_p(sum(1 for k in by[d] if sc[k].get('exec_match')), len(by[d]))} |")
        misses = [k for k in sc if not sc[k].get("exec_match")]
        if misses:
            lines += ["", "Misses: " + ", ".join(f"`{k}`" for k in misses)]
        lines.append("")

    lines += ["### Cost and latency per task", "",
              "| suite | tasks run | tokens/task | p50 duration | p95 duration | first step p50 | rate-limit wait | "
              "LLM calls/task | reasoning share of output | tool outputs truncated | failed |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for suite, recs in (("pr", pr), ("contract", contract), ("injection", inj), ("sql", sql)):
        if not recs:
            continue
        st = _stats(list(recs.values()))
        lines.append(f"| {suite} | {st['n']}/{totals[suite]} | {st['tokens_mean']:,} | {st['dur_p50']:.1f} s | "
                     f"{st['dur_p95']:.1f} s | {st['first_step_p50']:.1f} s | {st['wait_share']:.0%} of time "
                     f"({st['retries']} retries) | {st['llm_calls_mean']:.1f} | {st['reasoning_share']:.0%} | "
                     f"{st['truncated_tools']} | {st['failed']} |")
    total = sum(_stats(list(r.values()))["tokens_total"] for r in (pr, contract, inj, sql) if r)
    lines += ["", f"Total spent on these runs: {total:,} tokens. Re-scoring them (`python -m evals.live score`) and "
              "replaying them from the response cache (`--cache only`) cost none.", ""]
    return lines


def main() -> None:
    out = ["# Hive — measured results", "",
           f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC by `python -m evals.report` from `evals/results/`. "
           "How to rerun each measurement is in [evals/README.md](README.md).", ""]
    for section in (agents_section, retrieval_section, load_section, tests_section):
        out += section()
    (ROOT / "RESULTS.md").write_text("\n".join(out).rstrip() + "\n")
    print(f"wrote {ROOT / 'RESULTS.md'}")


if __name__ == "__main__":
    main()
