"""Agent-loop tests using a fake Groq (OpenAI-compatible) client — no
network/API key needed.

These test the tool-use *loop* wiring (dispatch, error feedback, turn
budget), not the LLM's judgement, since that's covered separately by the
eval question set once a real GROQ_API_KEY is available.
"""

from __future__ import annotations

import json

from askmycity.agent import ask


class FakeFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments  # a JSON string, like the real API


class FakeToolCall:
    def __init__(self, id, name, arguments: dict):
        self.id = id
        self.type = "function"
        self.function = FakeFunction(name, json.dumps(arguments))


class FakeMessage:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class FakeChoice:
    def __init__(self, message):
        self.message = message


class FakeResponse:
    def __init__(self, message):
        self.choices = [FakeChoice(message)]


class FakeCompletions:
    def __init__(self, responses):
        self._responses = list(responses)

    def create(self, **kwargs):
        return self._responses.pop(0)


class FakeChat:
    def __init__(self, responses):
        self.completions = FakeCompletions(responses)


class FakeClient:
    def __init__(self, responses):
        self.chat = FakeChat(responses)


def test_ask_happy_path_one_tool_call(sample_df):
    responses = [
        FakeResponse(
            FakeMessage(
                tool_calls=[
                    FakeToolCall(
                        "call_1", "top_n", {"group_by": "category", "agg": "count", "n": 2}
                    )
                ]
            )
        ),
        FakeResponse(FakeMessage(content="Potholes were the top category.")),
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
            FakeMessage(
                tool_calls=[
                    FakeToolCall(
                        "call_1",
                        "filter_and_aggregate",
                        {"agg": "count", "filters": {"not_a_column": "x"}},
                    )
                ]
            )
        ),
        FakeResponse(
            FakeMessage(
                tool_calls=[
                    FakeToolCall(
                        "call_2",
                        "filter_and_aggregate",
                        {"agg": "count", "filters": {"category": "pothole"}},
                    )
                ]
            )
        ),
        FakeResponse(FakeMessage(content="There were 3 pothole requests.")),
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
            FakeMessage(
                tool_calls=[FakeToolCall(f"call_{i}", "filter_and_aggregate", {"agg": "count"})]
            )
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
