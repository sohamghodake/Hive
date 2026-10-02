"""Exercise the tool servers over the Model Context Protocol itself.

fastmcp's Client accepts a server object and connects in-memory, so these run
the real initialize → tools/list → tools/call exchange without Docker.
"""
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from tests.test_mcp._load import load_server


@pytest.fixture
def mcp_file(tmp_path, monkeypatch):
    server = load_server("mcp_file")
    monkeypatch.setattr(server, "WORKSPACE", tmp_path.resolve())
    return server


@pytest.mark.parametrize(
    "name, expected",
    [
        ("mcp_file", {"read_file", "write_file", "list_files", "delete_file"}),
        ("mcp_db", {"query", "list_tables", "describe_table", "list_documents", "read_document", "search_documents"}),
        ("mcp_search", {"web_search"}),
        ("mcp_api", {"http_get", "http_post"}),
    ],
)
async def test_servers_advertise_tools_over_mcp(name, expected):
    async with Client(load_server(name).mcp) as client:
        tools = {t.name for t in await client.list_tools()}
    assert tools == expected


async def test_file_roundtrip_over_mcp(mcp_file):
    async with Client(mcp_file.mcp) as client:
        await client.call_tool("write_file", {"path": "reports/a.md", "content": "hello"})
        listing = (await client.call_tool("list_files", {"directory": "reports"})).data
        content = (await client.call_tool("read_file", {"path": "reports/a.md"})).data

    assert content == "hello"
    assert listing == [{"path": "reports/a.md", "is_dir": False, "size": 5}]


async def test_sandbox_escape_is_a_tool_error_over_mcp(mcp_file):
    async with Client(mcp_file.mcp) as client:
        with pytest.raises(ToolError, match="escapes workspace"):
            await client.call_tool("read_file", {"path": "../etc/passwd"})


async def test_ssrf_is_refused_over_mcp():
    async with Client(load_server("mcp_api").mcp) as client:
        with pytest.raises(ToolError, match="not allowed"):
            await client.call_tool("http_get", {"url": "http://169.254.169.254/latest/meta-data/"})


async def test_search_without_provider_is_explicit(monkeypatch):
    server = load_server("mcp_search")
    monkeypatch.setattr(server, "TAVILY_API_KEY", "")
    monkeypatch.setattr(server, "BRAVE_API_KEY", "")
    async with Client(server.mcp) as client:
        with pytest.raises(ToolError, match="not configured"):
            await client.call_tool("web_search", {"query": "x"})
