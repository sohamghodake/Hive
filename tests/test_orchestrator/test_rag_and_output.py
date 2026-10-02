from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage

from orchestrator import nodes, tools
from rag.embeddings import chunk_text, to_pgvector


# ── Chunking ──────────────────────────────────────────────────────────────────

def test_chunks_respect_size_and_keep_all_text():
    text = "\n\n".join(f"Clause {i}. " + "word " * 60 for i in range(10))
    chunks = chunk_text(text, size=400, overlap=50)
    assert len(chunks) > 1
    assert all(len(c) <= 400 + 60 for c in chunks)  # a piece may carry its overlap tail
    for i in range(10):
        assert any(f"Clause {i}." in c for c in chunks)


def test_overlap_starts_on_a_word_boundary():
    text = "alpha beta gamma delta. " * 40
    for chunk in chunk_text(text, size=200, overlap=40)[1:]:
        assert chunk.split(" ", 1)[0] in {"alpha", "beta", "gamma", "delta."}


def test_empty_text_has_no_chunks():
    assert chunk_text("   \n\n ") == []


def test_pgvector_literal():
    assert to_pgvector([0.5, -1.0]) == "[0.5000000,-1.0000000]"


# ── Structured output ─────────────────────────────────────────────────────────

def _final(text, **extra):
    return {"run_id": "r", "messages": [AIMessage(content=text, **extra)]}


async def test_finalize_extracts_last_json_block():
    text = 'Summary.\n```json\n{"a": 1}\n```\nmore\n```json\n{"overall_risk": "high"}\n```'
    out = (await nodes.finalize(_final(text)))["final_output"]
    assert out["data"] == {"overall_risk": "high"}
    assert out["text"] == text


async def test_finalize_tolerates_malformed_json():
    out = (await nodes.finalize(_final("x\n```json\n{not json}\n```")))["final_output"]
    assert "data" not in out


async def test_finalize_flags_runs_cut_off_by_step_budget():
    state = {"run_id": "r", "messages": [
        AIMessage(content="partial answer"),
        AIMessage(content="", tool_calls=[{"id": "t", "name": "read_file", "args": {}}]),
    ]}
    out = (await nodes.finalize(state))["final_output"]
    assert out == {"text": "partial answer", "stopped_early": True}


# ── Rate-limit backoff ────────────────────────────────────────────────────────

def test_parses_groq_retry_after():
    assert nodes._suggested_wait(Exception("Please try again in 7.52s.")) == 7.52
    assert nodes._suggested_wait(Exception("try again in 1m2.5s")) == 62.5
    assert nodes._suggested_wait(Exception("something else")) is None


# ── Batched semantic search ───────────────────────────────────────────────────

async def test_search_documents_batches_queries_and_dedupes():
    def hit(chunk, score):
        return {"document_id": "d1", "document_name": "msa.pdf", "chunk_index": chunk,
                "chunk_text": f"chunk {chunk}", "score": score}

    responses = {
        "liability cap": [hit(3, 0.9), hit(4, 0.7)],
        "indemnity": [hit(4, 0.8), hit(9, 0.6)],  # chunk 4 overlaps
    }
    fake = AsyncMock(side_effect=lambda server, tool, args: responses[args["query"]])

    with patch.object(tools, "call_tool", fake):
        out = await tools.search_documents.ainvoke(
            {"queries": ["liability cap", "indemnity"], "document_id": "d1"}
        )

    assert [h["chunk_index"] for h in out] == [3, 4, 9]
    assert fake.await_count == 2
    assert all(c.args[2]["document_id"] == "d1" for c in fake.await_args_list)


async def test_search_keeps_highest_scores_within_budget():
    hits = [{"document_id": "d", "document_name": "n", "chunk_index": i,
             "chunk_text": "x" * 1000, "score": i / 100} for i in range(20)]
    with patch.object(tools, "call_tool", AsyncMock(return_value=hits)):
        out = await tools.search_documents.ainvoke({"queries": ["q"]})

    kept = {h["chunk_index"] for h in out}
    assert kept == set(range(20 - len(kept), 20))  # the top scores, nothing lower
    assert sum(len(h["chunk_text"]) + 160 for h in out) <= tools.SEARCH_CHAR_BUDGET
    assert all(len(h["chunk_text"]) <= tools.SEARCH_PASSAGE_CHARS for h in out)


def test_truncation_ends_on_a_line_with_a_marker(monkeypatch):
    monkeypatch.setattr(nodes, "MAX_TOOL_CHARS", 100)
    text = "\n".join(f"line {i:03d} with sub_ctx usage" for i in range(20))
    out = nodes._truncate(text)
    body, marker = out.split("\n\n[TOOL OUTPUT TRUNCATED", 1)
    assert body.endswith("usage")          # whole line, no "sub_" fragment
    assert "more characters were not shown" in marker
