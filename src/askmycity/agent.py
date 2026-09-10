"""The Claude tool-use loop: turns a natural-language question into calls
against the deterministic tools in `tools.py`, then a short NL answer.

The model never executes arbitrary code and never sees the raw dataframe —
it only ever picks a tool name + JSON arguments (validated against
`schema.py`), and gets back a small JSON table + summary to reason over.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

import anthropic
import pandas as pd

from .schema import ACTIVE_SCHEMA, DatasetSchema, build_tool_definitions
from .tools import ToolInputError, ToolResult, filter_and_aggregate, infer_chart_kind, top_n

DEFAULT_MODEL = os.environ.get("ASKMYCITY_MODEL", "claude-sonnet-5")
MAX_TOOL_TURNS = 4

_TOOL_IMPLS = {
    "filter_and_aggregate": filter_and_aggregate,
    "top_n": top_n,
}


@dataclass
class ToolCallRecord:
    """One tool call + its outcome, kept for the UI's 'how I got this' panel."""

    name: str
    input: dict[str, Any]
    result_summary: str | None = None
    error: str | None = None


@dataclass
class AgentAnswer:
    text: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    chart_table: pd.DataFrame | None = None
    chart_kind: str | None = None


def _system_prompt(schema: DatasetSchema) -> str:
    return (
        f"You are AskMyCity, an analytics assistant over a cached dataset of "
        f"{schema.row_description} from {schema.dataset_name}.\n\n"
        "Rules:\n"
        "- Always call a tool to get real numbers before answering a question about the data. "
        "Never guess or fabricate numbers.\n"
        "- If a tool call errors (e.g. unknown column), read the error and retry with corrected "
        "arguments instead of giving up.\n"
        "- Once you have the numbers, give a concise final answer (2-4 sentences) that cites "
        "the specific figures and timeframe/filters used.\n\n"
        f"Available columns:\n{schema.describe_columns()}"
    )


def _run_tool(name: str, tool_input: dict[str, Any], df: pd.DataFrame) -> ToolResult:
    impl = _TOOL_IMPLS.get(name)
    if impl is None:
        raise ToolInputError(f"Unknown tool '{name}'")
    return impl(df, **tool_input)


def _chart_kind_for(schema: DatasetSchema, table: pd.DataFrame) -> str | None:
    chronological = {c.name for c in schema.time_bucket_cols}
    return infer_chart_kind(table, date_col=schema.date_col, chronological_cols=chronological)


def ask(
    question: str,
    df: pd.DataFrame,
    *,
    schema: DatasetSchema = ACTIVE_SCHEMA,
    client: anthropic.Anthropic | None = None,
    model: str = DEFAULT_MODEL,
    max_tool_turns: int = MAX_TOOL_TURNS,
) -> AgentAnswer:
    """Ask the agent a natural-language question about `df`.

    Requires ANTHROPIC_API_KEY in the environment unless `client` is passed
    explicitly (e.g. a fake/mock client in tests).
    """
    client = client or anthropic.Anthropic()
    tools = build_tool_definitions(schema)
    system = _system_prompt(schema)
    messages: list[dict[str, Any]] = [{"role": "user", "content": question}]

    call_log: list[ToolCallRecord] = []
    last_result: ToolResult | None = None

    for _ in range(max_tool_turns):
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=system,
            tools=tools,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            text = "".join(b.text for b in response.content if getattr(b, "type", None) == "text")
            chart_kind = None
            if last_result is not None:
                chart_kind = _chart_kind_for(schema, last_result.table)
            return AgentAnswer(
                text=text.strip() or "I wasn't able to produce an answer.",
                tool_calls=call_log,
                chart_table=last_result.table if last_result is not None else None,
                chart_kind=chart_kind,
            )

        tool_results_content = []
        for block in response.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            record = ToolCallRecord(name=block.name, input=block.input)
            try:
                result = _run_tool(block.name, block.input, df)
                last_result = result
                record.result_summary = result.summary
                tool_results_content.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result.to_json()),
                    }
                )
            except ToolInputError as exc:
                record.error = str(exc)
                tool_results_content.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(exc),
                        "is_error": True,
                    }
                )
            call_log.append(record)
        messages.append({"role": "user", "content": tool_results_content})

    chart_kind = None
    if last_result is not None:
        chart_kind = _chart_kind_for(schema, last_result.table)
    return AgentAnswer(
        text="I ran out of tool-call turns without reaching a final answer.",
        tool_calls=call_log,
        chart_table=last_result.table if last_result is not None else None,
        chart_kind=chart_kind,
    )
