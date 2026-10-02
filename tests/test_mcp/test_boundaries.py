"""The file sandbox and the outbound-HTTP guard are the two places an LLM-chosen
string decides what the platform touches, so both get pinned by tests."""
import pytest
from fastmcp.exceptions import ToolError

from tests.test_mcp._load import load_server

mcp_file = load_server("mcp_file")
mcp_api = load_server("mcp_api")


# ── File sandbox ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("path", ["notes.md", "reports/q3.md", "a/../b.md", ""])
def test_sandbox_allows_paths_inside_workspace(path):
    assert mcp_file._safe_path(path).is_relative_to(mcp_file.WORKSPACE)


@pytest.mark.parametrize(
    "path",
    [
        "../etc/passwd",
        "/etc/passwd",
        # Sibling directory sharing the workspace's name as a string prefix.
        # A startswith() check accepts this; a component comparison does not.
        f"../{mcp_file.WORKSPACE.name}_evil/x.txt",
    ],
)
def test_sandbox_rejects_escapes(path):
    with pytest.raises(ToolError):
        mcp_file._safe_path(path)


# ── Outbound HTTP (SSRF) ─────────────────────────────────────────────────────
# IP literals keep these tests off the network: getaddrinfo returns them as-is.

@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8002/health",          # loopback
        "http://10.0.0.5/",                      # private
        "http://172.20.0.3:5432/",               # docker bridge (postgres)
        "http://192.168.1.1/",                   # private
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata
        "http://[::1]/",                         # IPv6 loopback
        "http://[::ffff:127.0.0.1]/",            # IPv4-mapped loopback
        "http://0.0.0.0/",                       # unspecified
        "file:///etc/passwd",                    # non-HTTP scheme
        "gopher://8.8.8.8/",
    ],
)
async def test_ssrf_guard_blocks_internal_destinations(url):
    with pytest.raises(ToolError):
        await mcp_api._assert_public(url)


async def test_ssrf_guard_allows_public_ip():
    await mcp_api._assert_public("https://8.8.8.8/")
