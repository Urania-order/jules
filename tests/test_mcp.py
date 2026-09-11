import asyncio
import pytest
from smos.core.mcp_server import mcp

@pytest.mark.asyncio
async def test_mcp():
    tools = await mcp.list_tools()
    print(f"Registered tools: {[t.name for t in tools]}")
    assert "search_memory" in [t.name for t in tools]

    result = await mcp.call_tool("create_jules_session", {"task": "Verify MCP"})
    print(f"Tool call result: {result}")
    assert "Jules session created" in str(result)

if __name__ == "__main__":
    asyncio.run(test_mcp())
