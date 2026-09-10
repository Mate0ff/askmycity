"""Agent-loop tests using a fake Anthropic client — no network/API key needed.

These test the tool-use *loop* wiring (dispatch, error feedback, turn
budget), not the LLM's judgement, since that's covered separately by the
eval question set once the real dataset lands.
"""

from __future__ import annotations

from askmycity.agent import ask


class FakeBlock:
    def __init__(self, type, *, text=None, id=None, name=None, input=None):
        self.type = type
        self.text = text
        self.id = id
        self.name = name
        self.input = input


class FakeResponse:
    def __init__(self, content, stop_reason):
        self.content = content
        self.stop_reason = stop_reason


class FakeMessages:
    def __init__(self, responses):
        self._responses = list(responses)

    def create(self, **kwargs):
        return self._responses.pop(0)


class FakeClient:
    def __init__(self, responses):
        self.messages = FakeMessages(responses)


def test_ask_happy_path_one_tool_call(sample_df):
    responses = [
        FakeResponse(
            content=[
                FakeBlock(
                    "tool_use",
                    id="call_1",
                    name="top_n",
                    input={"group_by": "category", "agg": "count", "n": 2},
                )
            ],
            stop_reason="tool_use",
        ),
        FakeResponse(
            content=[FakeBlock("text", text="Potholes were the top category.")],
            stop_reason="end_turn",
        ),
    ]
    result = ask(question="top categories?", df=sample_df, client=FakeClient(responses))

    assert result.text == "Potholes were the top category."
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "top_n"
    assert result.tool_calls[0].error is None
    assert result.chart_table is not None
    assert result.chart_kind == "bar"


def test_ask_feeds_tool_error_back_and_recovers(sample_df):
    responses = [
        FakeResponse(
            content=[
                FakeBlock(
                    "tool_use",
                    id="call_1",
                    name="filter_and_aggregate",
                    input={"agg": "count", "filters": {"not_a_column": "x"}},
                )
            ],
            stop_reason="tool_use",
        ),
        FakeResponse(
            content=[
                FakeBlock(
                    "tool_use",
                    id="call_2",
                    name="filter_and_aggregate",
                    input={"agg": "count", "filters": {"category": "pothole"}},
                )
            ],
            stop_reason="tool_use",
        ),
        FakeResponse(
            content=[FakeBlock("text", text="There were 3 pothole requests.")],
            stop_reason="end_turn",
        ),
    ]
    result = ask(question="how many potholes?", df=sample_df, client=FakeClient(responses))

    assert result.text == "There were 3 pothole requests."
    assert len(result.tool_calls) == 2
    assert result.tool_calls[0].error is not None
    assert result.tool_calls[1].error is None


def test_ask_stops_after_max_tool_turns(sample_df):
    # The fake model never stops calling tools; the loop must still terminate.
    responses = [
        FakeResponse(
            content=[
                FakeBlock(
                    "tool_use", id=f"call_{i}", name="filter_and_aggregate", input={"agg": "count"}
                )
            ],
            stop_reason="tool_use",
        )
        for i in range(10)
    ]
    result = ask(
        question="loop forever?",
        df=sample_df,
        client=FakeClient(responses),
        max_tool_turns=3,
    )

    assert "ran out of tool-call turns" in result.text
    assert len(result.tool_calls) == 3
