import asyncio
import pytest
from smos.core.mcp_server import mcp

def test_mcp():
    import anyio
    async def _run():
        tools = await mcp.list_tools()
        print(f"Registered tools: {[t.name for t in tools]}")
        assert "search_memory" in [t.name for t in tools]

        result = await mcp.call_tool("create_jules_session", {"task": "Verify MCP"})
        print(f"Tool call result: {result}")
        assert "Jules session created" in str(result)
    anyio.run(_run)

if __name__ == "__main__":
    asyncio.run(test_mcp())
