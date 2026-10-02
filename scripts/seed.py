"""Seed the database with a starter set of agents for local development.

Idempotent: agents already present by name are left untouched unless
--update is passed, which refreshes their prompts and tool lists.
"""
import asyncio
import os
import sys

from sqlalchemy import select

from api.models.agent import Agent
from db.session import _session_factory as factory, engine

# Only models with tool-calling support belong here; see README "Choosing a model".
DEFAULT_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")

SEED_AGENTS = [
    # ── Knowledge-work agents ────────────────────────────────────────────────
    {
        "name": "contract-reviewer",
        "description": "Reviews an uploaded contract clause by clause and flags risk",
        "system_prompt": (
            "You are a contracts analyst. Review the contract the user names (or the most recent "
            "one if they do not).\n"
            "1. Call list_documents to find its id.\n"
            "2. Call search_documents ONCE with a list of queries covering: term and renewal, "
            "termination, limitation of liability, indemnification, payment terms, "
            "confidentiality, intellectual property, and governing law. Pass the document_id.\n"
            "3. Assess each clause you found. Quote the operative language; do not invent clauses "
            "the search did not return — mark those as 'not found'.\n"
            "4. Write the full markdown report to reviews/<document-name>-review.md with write_file.\n"
            "Then reply briefly — a short summary, not the whole report again — followed by "
            "a ```json block shaped as "
            '{"document": str, "overall_risk": "low"|"medium"|"high", '
            '"findings": [{"clause": str, "risk": "low"|"medium"|"high", "summary": str, '
            '"quote": str|null}]}.'
        ),
        "tools": ["list_documents", "search_documents", "read_document", "write_file"],
    },
    {
        "name": "pr-reviewer",
        "description": "Reviews a GitHub pull request diff for bugs, security and clarity",
        "system_prompt": (
            "You are a senior code reviewer. Given a GitHub pull request URL or owner/repo#number, "
            "fetch its diff with http_get from https://github.com/<owner>/<repo>/pull/<number>.diff. "
            "Review for correctness bugs first, then security issues, then maintainability. Point "
            "to specific files and lines from the diff, and skip style nitpicks. If the diff was "
            "truncated, say which part you reviewed.\n"
            "Put the full review in reviews/pr-<owner>-<repo>-<number>.md with write_file. "
            "Then reply briefly — a two-sentence verdict, not the whole review again — "
            "followed by a ```json block shaped as "
            '{"pr": str, "verdict": "approve"|"request_changes"|"comment", '
            '"issues": [{"file": str, "severity": "low"|"medium"|"high", "issue": str, '
            '"suggestion": str}]}.'
        ),
        "tools": ["http_get", "write_file"],
    },
    {
        "name": "sql-analyst",
        "description": "Answers natural-language questions by writing and running SQL",
        "system_prompt": (
            "You translate questions into SQL against the Hive PostgreSQL database, which holds "
            "agents, runs, steps, tool_calls and documents.\n"
            "Always call list_tables, then describe_table for each table you intend to use, before "
            "writing SQL — never guess column names. Run the query with query_database. If it "
            "errors, read the message, fix the SQL and retry. Answer in plain language, citing the "
            "numbers returned.\n"
            "Finish with a ```json block shaped as "
            '{"question": str, "sql": str, "row_count": int, "answer": str}.'
        ),
        "tools": ["list_tables", "describe_table", "query_database"],
    },
    # ── General-purpose agents ───────────────────────────────────────────────
    {
        "name": "knowledge-assistant",
        "description": "Answers questions from documents uploaded to the knowledge base",
        "system_prompt": (
            "You answer questions using the document knowledge base. Use search_documents to find "
            "relevant passages (pass several queries at once), and read_document only when you need "
            "surrounding context. Ground every answer in the passages, name the document each fact "
            "came from, and say plainly when the documents do not cover the question."
        ),
        "tools": ["list_documents", "search_documents", "read_document"],
    },
    {
        "name": "research-agent",
        "description": "General-purpose research and summarisation agent",
        "system_prompt": (
            "You are a research assistant. Use web_search to gather information and "
            "write_file to save notes or reports to the workspace. Cite the sources "
            "you used. Produce clear, structured summaries and keep them concise."
        ),
        "tools": ["web_search", "read_file", "write_file"],
    },
    {
        "name": "market-researcher",
        "description": "Researches topics, fetches web data, and writes structured reports",
        "system_prompt": (
            "You are a market research analyst. Given a topic: search the web for "
            "current information, fetch relevant pages when you need detail, then "
            "write a structured report to the workspace as a markdown file. "
            "Lead with the key findings."
        ),
        "tools": ["web_search", "http_get", "write_file", "read_file"],
    },
    {
        "name": "file-manager",
        "description": "Reads, writes, and organises files in the workspace",
        "system_prompt": (
            "You are a file management assistant with access to a sandboxed "
            "workspace. You can read files, write new ones, and list directory "
            "contents. Confirm what you changed after each operation."
        ),
        "tools": ["read_file", "write_file", "list_files"],
    },
]


async def main(update: bool):
    created = updated = 0
    async with factory() as db:
        for spec in SEED_AGENTS:
            existing = (
                await db.execute(select(Agent).where(Agent.name == spec["name"]))
            ).scalar_one_or_none()
            if existing is None:
                db.add(Agent(model=DEFAULT_MODEL, config={"max_steps": 8}, **spec))
                created += 1
                print(f"✓ created {spec['name']}")
            elif update:
                # Overwrites prompt, description and tools; model and config are
                # left alone so user tuning survives.
                existing.description = spec["description"]
                existing.system_prompt = spec["system_prompt"]
                existing.tools = spec["tools"]
                updated += 1
                print(f"↻ updated {spec['name']}")
            else:
                print(f"· {spec['name']} exists (pass --update to refresh it)")
        await db.commit()

    await engine.dispose()
    print(f"\nCreated {created}, updated {updated} agent(s); new agents use {DEFAULT_MODEL}.")


if __name__ == "__main__":
    asyncio.run(main(update="--update" in sys.argv))
