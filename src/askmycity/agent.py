"""The tool-use loop: turns a natural-language question into calls against
the deterministic tools in `tools.py`, then a short NL answer.

Uses Groq's OpenAI-compatible chat completions API (function/tool calling)
as the LLM. The model never executes arbitrary code and never sees the raw
dataframe — it only ever picks a tool name + JSON arguments (validated
against `schema.py`), and gets back a small JSON table + summary to reason
over.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
from groq import Groq, RateLimitError

from .schema import ACTIVE_SCHEMA, DatasetSchema, build_tool_definitions
from .tools import ToolInputError, ToolResult, filter_and_aggregate, infer_chart_kind, top_n

DEFAULT_MODEL = os.environ.get("ASKMYCITY_MODEL", "openai/gpt-oss-120b")
MAX_TOOL_TURNS = 4
MAX_RATE_LIMIT_RETRIES = 3

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


def _to_openai_tools(tools: list[dict]) -> list[dict]:
    """Wraps schema.py's flat {name, description, input_schema} tool defs in
    OpenAI/Groq's {"type": "function", "function": {...}} shape."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in tools
    ]


def _run_tool(
    name: str, tool_input: dict[str, Any], df: pd.DataFrame, schema: DatasetSchema
) -> ToolResult:
    # Some models (observed with gpt-oss's Harmony response format on Groq)
    # occasionally leak a "<|channel|>..." marker onto the end of the tool
    # name — strip it rather than fail on an otherwise-valid call.
    clean_name = name.split("<|")[0]
    impl = _TOOL_IMPLS.get(clean_name)
    if impl is None:
        raise ToolInputError(f"Unknown tool '{name}'")
    # date_col isn't exposed to the model (schema.py only exposes
    # start_date/end_date/group_by/etc) — it's always the schema's date
    # column, so inject it here rather than relying on the model to guess
    # an internal parameter name for it. `tool_input` wins nothing here:
    # if the model somehow guesses the key "date_col" too, ours overrides
    # rather than raising a duplicate-keyword TypeError.
    return impl(df, **{**tool_input, "date_col": schema.date_col})


def _call_model(client: Groq, **kwargs: Any):
    """chat.completions.create with a short retry-with-backoff on 429s —
    the free tier's tokens-per-minute limit is easy to hit with a handful
    of tool-result round trips."""
    for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
        try:
            return client.chat.completions.create(**kwargs)
        except RateLimitError:
            if attempt == MAX_RATE_LIMIT_RETRIES:
                raise
            time.sleep(2**attempt)


def _chart_kind_for(schema: DatasetSchema, table: pd.DataFrame) -> str | None:
    chronological = {c.name for c in schema.time_bucket_cols}
    return infer_chart_kind(table, date_col=schema.date_col, chronological_cols=chronological)


def ask(
    question: str,
    df: pd.DataFrame,
    *,
    schema: DatasetSchema = ACTIVE_SCHEMA,
    client: Groq | None = None,
    model: str = DEFAULT_MODEL,
    max_tool_turns: int = MAX_TOOL_TURNS,
) -> AgentAnswer:
    """Ask the agent a natural-language question about `df`.

    Requires GROQ_API_KEY in the environment unless `client` is passed
    explicitly (e.g. a fake/mock client in tests).
    """
    client = client or Groq()
    tools = _to_openai_tools(build_tool_definitions(schema))
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _system_prompt(schema)},
        {"role": "user", "content": question},
    ]

    call_log: list[ToolCallRecord] = []
    last_result: ToolResult | None = None

    for _ in range(max_tool_turns):
        response = _call_model(
            client,
            model=model,
            max_tokens=1024,
            tools=tools,
            messages=messages,
            # gpt-oss on Groq sometimes sends `null` for an omitted optional
            # arg (e.g. group_by: null), which Groq's strict pre-flight
            # schema check 400s on. Our own tool functions already treat
            # None as "not provided", so let those calls through and
            # validate ourselves.
            disable_tool_validation=True,
        )
        message = response.choices[0].message
        tool_calls = getattr(message, "tool_calls", None)

        if not tool_calls:
            chart_kind = _chart_kind_for(schema, last_result.table) if last_result else None
            return AgentAnswer(
                text=(message.content or "").strip() or "I wasn't able to produce an answer.",
                tool_calls=call_log,
                chart_table=last_result.table if last_result is not None else None,
                chart_kind=chart_kind,
            )

        messages.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in tool_calls
                ],
            }
        )

        for tc in tool_calls:
            record = ToolCallRecord(name=tc.function.name, input={})
            try:
                tool_input = json.loads(tc.function.arguments or "{}")
                record.input = tool_input
                result = _run_tool(tc.function.name, tool_input, df, schema)
                last_result = result
                record.result_summary = result.summary
                content = json.dumps(result.to_json())
            except (ToolInputError, TypeError, json.JSONDecodeError) as exc:
                # TypeError covers a model passing an argument name that
                # doesn't exist on the tool (e.g. a hallucinated kwarg) —
                # fed back the same way so it can retry with valid args.
                record.error = str(exc)
                content = f"Error: {exc}"
            call_log.append(record)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": content})

    chart_kind = _chart_kind_for(schema, last_result.table) if last_result else None
    return AgentAnswer(
        text="I ran out of tool-call turns without reaching a final answer.",
        tool_calls=call_log,
        chart_table=last_result.table if last_result is not None else None,
        chart_kind=chart_kind,
    )
