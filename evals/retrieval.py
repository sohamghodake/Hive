"""Retrieval quality of the RAG path. Uses no LLM tokens.

Chunks and embeds the eval corpus (evals/data/docs) with the production code in
rag/embeddings.py, asks each labelled question in evals/data/retrieval_questions.json,
and checks whether a passage containing that question's evidence phrase comes back.
Labels are phrases rather than chunk ids so the same set scores any chunk size.

Two settings, because the agents use both:
  global  — search every document. Hard on purpose: three contracts share clause
            types, so "notice to cancel" matches all of them.
  scoped  — search only the right document, as contract-reviewer does with document_id.

--pgvector also loads the production configuration into Postgres (hive_test) with
an HNSW index and runs the same SQL as mcp-db, to check that the database path
agrees with exact search and to time it.

    docker run --rm --network hive_default --user "$(id -u):$(id -g)" -e HOME=/tmp \
      -v "$PWD:/app" -w /app hive-api-test python -m evals.retrieval --pgvector
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import time

import numpy as np

from evals._util import DATA, norm, pct, save
from rag.embeddings import CHUNK_CHARS, CHUNK_OVERLAP, chunk_text, embed_passages, embed_query, to_pgvector

# (chunk size, overlap, context prefix); the first is what production uses.
# "filename" prepends the upload's file name (all a PDF reliably has); "title" and
# "title+heading" prepend the document's title (and the section heading in effect
# where the chunk starts). Only the embedded text changes; the stored and
# returned chunk is the same.
CONFIGS = [
    (CHUNK_CHARS, CHUNK_OVERLAP, None),
    (500, 100, None),
    (1500, 200, None),
    (1000, 0, None),
    (CHUNK_CHARS, CHUNK_OVERLAP, "filename"),
    (CHUNK_CHARS, CHUNK_OVERLAP, "title"),
    (CHUNK_CHARS, CHUNK_OVERLAP, "title+heading"),
]
_HEADING = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
KS = (1, 3, 5)
MRR_DEPTH = 10


def load():
    docs = {p.name: p.read_text() for p in sorted((DATA / "docs").glob("*.md"))}
    questions = json.loads((DATA / "retrieval_questions.json").read_text())
    for q in questions:  # a typo in a label would silently count as a miss
        assert norm(q["evidence"]) in norm(docs[q["doc"]]), f"evidence not in {q['doc']}: {q['id']}"
    return docs, questions


def unit(vectors) -> np.ndarray:
    m = np.asarray(vectors, dtype=np.float32)
    return m / np.linalg.norm(m, axis=1, keepdims=True)


def first_relevant(order, chunks, q) -> int | None:
    """1-based rank of the first chunk from the right document holding the evidence."""
    target = norm(q["evidence"])
    for rank, i in enumerate(order[:MRR_DEPTH], 1):
        doc, _, text = chunks[i]
        if doc == q["doc"] and target in norm(text):
            return rank
    return None


def score(ranks: list[int | None]) -> dict:
    n = len(ranks)
    out = {f"hit@{k}": round(sum(1 for r in ranks if r and r <= k) / n, 3) for k in KS}
    out[f"mrr@{MRR_DEPTH}"] = round(sum(1 / r for r in ranks if r) / n, 3)
    return out


def with_context(docs, chunks, mode):
    """Text to embed for each chunk: the chunk itself, or prefixed with context."""
    if mode is None:
        return [c for _, _, c in chunks]
    out, heading, current_doc = [], None, None
    for doc, _, c in chunks:
        if doc != current_doc:
            current_doc, heading = doc, None
            m = _HEADING.search(docs[doc])
            title = m.group(1) if m and mode != "filename" else doc.rsplit(".", 1)[0].replace("-", " ")
        prefix = title if mode == "title" or not heading or heading == title else f"{title} — {heading}"
        out.append(f"{prefix}\n{c}")
        found = _HEADING.findall(c)
        if found:  # the heading in effect where the next chunk starts
            heading = found[-1]
    return out


def evaluate(docs, questions, size, overlap, context, qvecs):
    chunks = [(name, i, c) for name, text in docs.items() for i, c in enumerate(chunk_text(text, size, overlap))]
    started = time.perf_counter()
    pvecs = unit(embed_passages(with_context(docs, chunks, context)))
    embed_s = time.perf_counter() - started
    # A boundary that cuts the evidence phrase makes the question unanswerable
    # from any single passage, whatever the ranking does.
    split = sum(1 for q in questions
                if not any(d == q["doc"] and norm(q["evidence"]) in norm(t) for d, _, t in chunks))

    sims = qvecs @ pvecs.T
    by_doc = np.array([d for d, _, _ in chunks])
    global_ranks, scoped_ranks, doc_top1, misses = [], [], 0, []
    for qi, q in enumerate(questions):
        order = list(np.argsort(-sims[qi]))
        rank = first_relevant(order, chunks, q)
        global_ranks.append(rank)
        doc_top1 += chunks[order[0]][0] == q["doc"]
        scoped = [i for i in order if by_doc[i] == q["doc"]]
        scoped_ranks.append(first_relevant(scoped, chunks, q))
        if rank != 1:
            top_doc, top_idx, top_text = chunks[order[0]]
            misses.append({"id": q["id"], "rank": rank, "top1": f"{top_doc}#{top_idx}: {top_text[:90]!r}"})

    return {
        "chunk_chars": size, "overlap": overlap, "context": context, "chunks": len(chunks),
        "evidence_split": split,
        "global": score(global_ranks) | {"doc@1": round(doc_top1 / len(questions), 3)},
        "scoped": score(scoped_ranks),
        "embed_chunks_per_s": round(len(chunks) / embed_s, 1),
        "misses": misses,
    }, chunks, pvecs


async def pgvector_check(chunks, pvecs, qvecs, questions) -> dict:
    """Same SQL shape as mcp-db's search_documents, on an HNSW index in hive_test."""
    import asyncpg

    url = os.getenv("TEST_DATABASE_URL", "postgresql://hive:hivepass@postgres:5432/hive_test")
    conn = await asyncpg.connect(url.replace("+asyncpg", ""))
    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        await conn.execute(
            "CREATE TEMP TABLE eval_chunks (pos int, doc text, chunk text, embedding vector(384))"
        )
        await conn.executemany(
            "INSERT INTO eval_chunks VALUES ($1, $2, $3, $4::vector)",
            [(i, d, t, to_pgvector(v.tolist())) for i, ((d, _, t), v) in enumerate(zip(chunks, pvecs))],
        )
        await conn.execute("CREATE INDEX ON eval_chunks USING hnsw (embedding vector_cosine_ops)")
        await conn.execute("ANALYZE eval_chunks")

        sql = "SELECT pos FROM eval_chunks ORDER BY embedding <=> $1::vector LIMIT $2"
        ann_ranks, overlap, latencies = [], [], []
        for qv, q in zip(qvecs, questions):
            vec = to_pgvector(qv.tolist())
            async with conn.transaction():
                # At this corpus size the planner would pick a sequential scan;
                # force the index so the ANN path is what gets measured.
                await conn.execute("SET LOCAL enable_seqscan = off")
                t = time.perf_counter()
                ann = [r["pos"] for r in await conn.fetch(sql, vec, MRR_DEPTH)]
                latencies.append((time.perf_counter() - t) * 1000)
            async with conn.transaction():
                await conn.execute("SET LOCAL enable_indexscan = off")
                exact = [r["pos"] for r in await conn.fetch(sql, vec, MRR_DEPTH)]
            ann_ranks.append(first_relevant(ann, chunks, q))
            overlap.append(len(set(ann[:5]) & set(exact[:5])) / 5)
    finally:
        await conn.close()

    return {
        "global": score(ann_ranks),
        "ann_vs_exact_overlap@5": round(sum(overlap) / len(overlap), 3),
        "sql_ms": {"p50": round(pct(latencies, 50), 2), "p95": round(pct(latencies, 95), 2)},
    }


def main(with_pgvector: bool) -> None:
    docs, questions = load()

    latencies = []
    qvecs = []
    for q in questions:
        t = time.perf_counter()
        qvecs.append(embed_query(q["question"]))
        latencies.append((time.perf_counter() - t) * 1000)
    qvecs = unit(qvecs)

    results = []
    production = None
    for size, overlap, context in CONFIGS:
        res, chunks, pvecs = evaluate(docs, questions, size, overlap, context, qvecs)
        results.append(res)
        if production is None:
            production = (chunks, pvecs)

    report = {
        "corpus": {"documents": len(docs), "chars": sum(map(len, docs.values())), "questions": len(questions)},
        # The first call loads the ONNX model; leave it out of the latency figures.
        "query_embed_ms": {"p50": round(pct(latencies[1:], 50), 1), "p95": round(pct(latencies[1:], 95), 1)},
        "configs": results,
    }
    if with_pgvector:
        report["pgvector_hnsw"] = asyncio.run(pgvector_check(*production, qvecs, questions))

    path = save("retrieval.json", report)

    print(f"\nRetrieval eval — {len(questions)} questions over {len(docs)} documents "
          f"({report['corpus']['chars']:,} chars)\n")
    print("| chunk / overlap | context | chunks | split | global hit@1 | hit@3 | hit@5 | MRR@10 | right doc @1 | scoped hit@1 | scoped hit@3 |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in results:
        g, s = r["global"], r["scoped"]
        print(f"| {r['chunk_chars']} / {r['overlap']} | {r['context'] or '-'} | {r['chunks']} | {r['evidence_split']} | "
              f"{g['hit@1']:.0%} | {g['hit@3']:.0%} | {g['hit@5']:.0%} | {g['mrr@10']:.2f} | {g['doc@1']:.0%} | "
              f"{s['hit@1']:.0%} | {s['hit@3']:.0%} |")
    print(f"\nquery embedding p50 {report['query_embed_ms']['p50']} ms · p95 {report['query_embed_ms']['p95']} ms; "
          f"passage embedding {results[0]['embed_chunks_per_s']} chunks/s (2 ONNX threads)")
    if with_pgvector:
        pg = report["pgvector_hnsw"]
        print(f"pgvector HNSW (production chunking): hit@3 {pg['global']['hit@3']:.0%}, "
              f"ANN/exact top-5 overlap {pg['ann_vs_exact_overlap@5']:.0%}, "
              f"SQL p50 {pg['sql_ms']['p50']} ms · p95 {pg['sql_ms']['p95']} ms")
    print(f"\nmisses at production chunking (rank of first relevant passage, None = not in top {MRR_DEPTH}):")
    for m in results[0]["misses"]:
        print(f"  {m['id']:<36} rank {m['rank']}  top-1 {m['top1']}")
    print(f"\nwrote {path.relative_to(path.parents[2])}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pgvector", action="store_true", help="also measure the HNSW/SQL path in hive_test")
    main(ap.parse_args().pgvector)
