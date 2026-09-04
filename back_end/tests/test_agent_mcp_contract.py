import pytest
from types import SimpleNamespace

from app.agent_harness.mcp import (
    FORBIDDEN_PYTHON,
    MCPGateway,
    MockSteamMCPServer,
    _extract_agent_result,
)


@pytest.mark.asyncio
async def test_data_analyst_tools_have_bounded_contracts():
    tools = {tool.name: tool for tool in await MockSteamMCPServer().list_tools()}
    assert tools["describe_steam_table"].input_schema["properties"]["sample_size"]["maximum"] == 10
    assert "analyze_with_python" in tools
    assert "start_month" in tools["monthly_game_releases"].input_schema["properties"]
    assert "chart_type" in tools["monthly_game_releases"].input_schema["properties"]
    assert {"create_chart", "search_saved_charts", "get_saved_chart"}.issubset(tools)


def test_python_result_parser_ignores_non_result_output():
    execution = {
        "results": [],
        "logs": ["debug output", '__AGENT_RESULT__{"summary":"ok","statistics":{"mean":2.5}}'],
    }
    assert _extract_agent_result(execution)["statistics"]["mean"] == 2.5


def test_python_contract_blocks_network_and_file_access():
    assert FORBIDDEN_PYTHON.search("import requests\nresult = {}")
    assert FORBIDDEN_PYTHON.search("result = open('secret').read()")
    assert not FORBIDDEN_PYTHON.search("result = {'summary': str(df.shape)}")


@pytest.mark.asyncio
async def test_gateway_injects_trusted_context_outside_model_arguments():
    class CaptureServer:
        async def handle(self, request):
            context = request["params"]["arguments"].get("__agent_context")
            return {"jsonrpc": "2.0", "id": request["id"], "result": {"context": context}}

    gateway = MCPGateway(CaptureServer(), agent_context={"user_id": 7, "session_id": "s"})
    result = await gateway.call_tool("anything", {"value": 1})
    assert result["context"] == {"user_id": 7, "session_id": "s"}


def test_legacy_plotly_chart_is_normalized_for_current_frontend():
    row = SimpleNamespace(
        config={"figure": {"data": [{"type": "bar", "x": ["A", "B"], "y": [1, 2]}]}},
        chart_type="plotly", chart_title="Legacy", x_axis_label="Category", y_axis_label="Count",
    )
    chart = MockSteamMCPServer._chart_from_record(row)
    assert chart == {
        "type": "bar", "title": "Legacy", "x": ["A", "B"], "y": [1, 2],
        "x_label": "Category", "y_label": "Count",
    }
