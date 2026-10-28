"""How many of contract-reviewer's clause types actually reach the model. No LLM tokens.

contract-reviewer asks search_documents for eight clause types in one call. The
tool keeps the best-scoring passages that fit SEARCH_CHAR_BUDGET (5000 chars,
sized for the free tier's 8K tokens/minute), so strong matches for one query can
crowd out every match for another. This runs the agent's eight queries against
each labelled contract through the real mcp-db server and checks which clauses'
evidence phrases are in what comes back, for the production selection and for
two alternatives computed from the same hits.

    docker compose run --rm --no-deps -T -v "$PWD:/app" --user "$(id -u):$(id -g)" -e HOME=/tmp \\
        api python -m evals.search_coverage
"""
from __future__ import annotations

import asyncio
import json

import numpy as np

from evals._util import DATA, norm, save
from rag.embeddings import chunk_text, embed_passages, embed_query
from evals.live import ensure_document
from db.session import _session_factory, engine
from api.models.document import Document
from orchestrator import tools
from orchestrator.mcp_client import call_tool
from sqlalchemy import select

# The clause list in contract-reviewer's prompt, as the model passes it.
QUERIES = ["term and renewal", "termination", "limitation of liability", "indemnification",
           "payment terms", "confidentiality", "intellectual property", "governing law"]


def fill(hits_by_query: dict[str, list[dict]], per_query_first: bool, passage_chars: int) -> list[dict]:
    """Choose passages within the tool's character budget.

    production: all hits by score, best first, until the budget is spent.
    per-query-first: each query's best hit first (so every clause type gets a
    passage if one exists), then the rest by score.
    """
    best: dict[tuple, dict] = {}
    for q, hits in hits_by_query.items():
        for h in hits:
            key = (h["document_id"], h["chunk_index"])
            if key not in best or h["score"] > best[key]["score"]:
                best[key] = {**h, "query": q, "chunk_text": h["chunk_text"][:passage_chars]}
    ranked = sorted(best.values(), key=lambda h: h["score"], reverse=True)
    if per_query_first:
        firsts = []
        for q, hits in hits_by_query.items():
            if hits:
                top = best[(hits[0]["document_id"], hits[0]["chunk_index"])]
                if top not in firsts:
                    firsts.append(top)
        ranked = firsts + [h for h in ranked if h not in firsts]
    kept, used = [], 0
    for h in ranked:
        size = len(h["chunk_text"]) + 160
        if kept and used + size > tools.SEARCH_CHAR_BUDGET:
            continue
        kept.append(h)
        used += size
    return kept


# Re-chunking options, simulated in memory with the production embedder and the
# production selection, so they can be compared without re-indexing anything.
# (chunk chars, overlap, passage chars shown to the model)
SIMULATED = [(1000, 150, 700), (1000, 150, 1000), (750, 100, 750), (600, 100, 600), (500, 100, 500)]


def simulate(doc_text: str, size: int, overlap: int, passage_chars: int, qvecs) -> list[dict]:
    chunks = chunk_text(doc_text, size, overlap)
    pv = np.asarray(embed_passages(chunks), dtype=np.float32)
    pv /= np.linalg.norm(pv, axis=1, keepdims=True)
    hits = {}
    for q, qv in zip(QUERIES, qvecs):
        sims = pv @ qv
        hits[q] = [{"document_id": "d", "chunk_index": int(i), "chunk_text": chunks[i], "score": float(sims[i])}
                   for i in np.argsort(-sims)[:3]]
    return fill(hits, False, passage_chars)


def covered(passages, evidence: dict[str, str]) -> list[str]:
    text = norm(" ".join(p["chunk_text"] for p in passages))
    return [c for c, phrase in evidence.items() if norm(phrase) in text]


async def main() -> None:
    labels = {k: v for k, v in json.loads((DATA / "contract_labels.json").read_text()).items()
              if not k.startswith("_")}
    strategies = {
        "production (score order, 700-char passages)": (False, tools.SEARCH_PASSAGE_CHARS),
        "per-query first, 700-char passages": (True, tools.SEARCH_PASSAGE_CHARS),
        "per-query first, 500-char passages": (True, 500),
    }
    rows = {name: {} for name in strategies}
    for name, label in labels.items():
        await ensure_document(name, (DATA / "docs" / label["source"]).read_text())
        async with _session_factory() as db:
            doc_id = str((await db.execute(select(Document.id).where(Document.name == name))).scalar_one())

        # Same call the tool makes per query (k=3, scoped to the document).
        hits = {q: await call_tool("mcp-db", "search_documents", {"query": q, "k": 3, "document_id": doc_id})
                for q in QUERIES}
        production = await tools.search_documents.ainvoke({"queries": QUERIES, "document_id": doc_id})
        assert {(h["chunk_index"]) for h in production} == {
            h["chunk_index"] for h in fill(hits, False, tools.SEARCH_PASSAGE_CHARS)}, "replica drifted from tools.py"

        for strategy, (per_query, chars) in strategies.items():
            kept = fill(hits, per_query, chars)
            got = covered(kept, label["evidence"])
            rows[strategy][name] = {"passages": len(kept), "covered": got,
                                    "missing": [c for c in label["evidence"] if c not in got]}

    qvecs = np.asarray([embed_query(q) for q in QUERIES], dtype=np.float32)
    qvecs /= np.linalg.norm(qvecs, axis=1, keepdims=True)
    simulated = {}
    for size, overlap, chars in SIMULATED:
        per_doc = {}
        for name, label in labels.items():
            kept = simulate((DATA / "docs" / label["source"]).read_text(), size, overlap, chars, qvecs)
            got = covered(kept, label["evidence"])
            per_doc[name] = {"passages": len(kept), "covered": got,
                             "missing": [c for c in label["evidence"] if c not in got]}
        simulated[f"{size}/{overlap} chunks, {chars}-char passages"] = per_doc

    report = {"queries": QUERIES, "char_budget": tools.SEARCH_CHAR_BUDGET, "strategies": rows,
              "simulated_chunking": simulated}
    path = save("search_coverage.json", report)
    total = sum(len(v["evidence"]) for v in labels.values())
    print(f"\nClause types reaching contract-reviewer (of {total} across {len(labels)} contracts):\n")
    print("| selection | passages per call | clauses covered | missing |")
    print("|---|---|---|---|")
    for strategy, per_doc in list(rows.items()) + [(f"simulated: {k}", v) for k, v in simulated.items()]:
        n = sum(len(r["covered"]) for r in per_doc.values())
        passages = "/".join(str(r["passages"]) for r in per_doc.values())
        missing = "; ".join(f"{d.split('-')[1]}: {', '.join(r['missing'])}" for d, r in per_doc.items() if r["missing"])
        print(f"| {strategy} | {passages} | {n}/{total} ({n / total:.0%}) | {missing or '-'} |")
    print(f"\nwrote {path}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
