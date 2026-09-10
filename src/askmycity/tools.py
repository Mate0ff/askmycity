"""Deterministic, unit-testable data tools the Claude agent is allowed to call.

This is deliberately NOT arbitrary code execution: the model can only choose
a tool name plus a small set of typed arguments (see `schema.py`). All the
actual computation happens here in plain Python/pandas, so every tool can be
unit-tested without ever calling the LLM.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

VALID_AGGS = {"count", "sum", "mean", "median", "min", "max"}


class ToolInputError(ValueError):
    """Raised for a bad tool call (unknown column, bad agg, etc).

    The message is safe to feed straight back to the model as a tool_result
    error so it can retry with corrected arguments.
    """


@dataclass
class ToolResult:
    """Structured result returned by a tool call.

    `table` is the (small) resulting dataframe, meant for both display/
    charting in the UI and for summarizing back to the LLM. `summary` is a
    short plain-English description of what was computed.
    """

    table: pd.DataFrame
    summary: str

    def to_json(self, max_rows: int = 50) -> dict[str, Any]:
        table = self.table.head(max_rows)
        return {
            "summary": self.summary,
            "columns": list(table.columns),
            "rows": table.to_dict(orient="records"),
            "truncated": len(self.table) > max_rows,
        }


def _require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    unknown = [c for c in columns if c and c not in df.columns]
    if unknown:
        raise ToolInputError(
            f"Unknown column(s): {unknown}. Available columns: {list(df.columns)}"
        )


def _require_agg(agg: str) -> None:
    if agg not in VALID_AGGS:
        raise ToolInputError(f"Unknown agg '{agg}'. Must be one of {sorted(VALID_AGGS)}")


def _parse_date(label: str, value: str) -> pd.Timestamp:
    # A model can hand back an impossible calendar date (e.g. "2026-02-29"
    # in a non-leap year) — surface that as a normal tool error the model
    # can correct, instead of letting pandas' raw ValueError crash the call.
    try:
        return pd.Timestamp(value)
    except (ValueError, TypeError) as exc:
        raise ToolInputError(f"Invalid {label} '{value}': {exc}") from exc


def _apply_date_range(
    df: pd.DataFrame, date_col: str | None, start_date: str | None, end_date: str | None
) -> pd.DataFrame:
    if not (start_date or end_date):
        return df
    if not date_col:
        raise ToolInputError("start_date/end_date given but no date column configured")
    _require_columns(df, [date_col])
    out = df
    if start_date:
        out = out[out[date_col] >= _parse_date("start_date", start_date)]
    if end_date:
        # "end_date" is a calendar day, inclusive of the whole day — so the
        # cutoff is the *start* of the next day, not midnight of end_date
        # itself (which silently dropped every request timestamped later
        # that same day).
        cutoff = _parse_date("end_date", end_date) + pd.Timedelta(days=1)
        out = out[out[date_col] < cutoff]
    return out


def _apply_filters(df: pd.DataFrame, filters: dict[str, Any] | None) -> pd.DataFrame:
    if not filters:
        return df
    _require_columns(df, list(filters.keys()))
    out = df
    for col, value in filters.items():
        if isinstance(value, (list, tuple, set)):
            out = out[out[col].isin(value)]
        else:
            out = out[out[col] == value]
    return out


def _aggregate_series(series: pd.Series, agg: str) -> pd.Series | float:
    return getattr(series, agg)()


def filter_and_aggregate(
    df: pd.DataFrame,
    *,
    agg: str,
    date_col: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    filters: dict[str, Any] | None = None,
    group_by: str | None = None,
    metric: str | None = None,
    sort_by: str = "value",
) -> ToolResult:
    """Filter rows, then aggregate — optionally grouped by one column.

    `agg='count'` counts rows (metric is ignored); any other agg requires
    `metric` to name a numeric column.

    `sort_by` controls how a grouped result is ordered: 'value' (default)
    sorts by the aggregated number descending — for rankings; 'group' sorts
    by the group_by column ascending — for a chronological trend/time series
    (e.g. group_by a month-bucket column).
    """
    _require_agg(agg)
    if sort_by not in ("value", "group"):
        raise ToolInputError("sort_by must be 'value' or 'group'")
    if agg != "count" and not metric:
        raise ToolInputError("metric is required unless agg='count'")
    if metric:
        _require_columns(df, [metric])
    if group_by:
        _require_columns(df, [group_by])

    filtered = _apply_date_range(df, date_col, start_date, end_date)
    filtered = _apply_filters(filtered, filters)

    if group_by:
        grouped = filtered.groupby(group_by, dropna=False)
        if agg == "count":
            result = grouped.size().rename("count").reset_index()
        else:
            result = grouped[metric].agg(agg).rename(metric).reset_index()
        if sort_by == "group":
            result = result.sort_values(group_by, ascending=True)
        else:
            result = result.sort_values(result.columns[-1], ascending=False)
        summary = (
            f"{agg} of {metric or 'rows'} grouped by {group_by}, "
            f"over {len(filtered)} matching rows across {len(result)} groups."
        )
    else:
        value = len(filtered) if agg == "count" else _aggregate_series(filtered[metric], agg)
        result = pd.DataFrame({(metric or "count"): [value]})
        summary = f"{agg} of {metric or 'rows'} over {len(filtered)} matching rows: {value}."

    return ToolResult(table=result, summary=summary)


def top_n(
    df: pd.DataFrame,
    *,
    group_by: str,
    agg: str,
    n: int = 5,
    ascending: bool = False,
    date_col: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    filters: dict[str, Any] | None = None,
    metric: str | None = None,
) -> ToolResult:
    """Rank groups and return the top (or bottom) N."""
    result = filter_and_aggregate(
        df,
        agg=agg,
        date_col=date_col,
        start_date=start_date,
        end_date=end_date,
        filters=filters,
        group_by=group_by,
        metric=metric,
    )
    ranked = result.table.sort_values(result.table.columns[-1], ascending=ascending).head(n)
    direction = "bottom" if ascending else "top"
    summary = f"{direction} {len(ranked)} {group_by} groups by {agg} of {metric or 'rows'}."
    return ToolResult(table=ranked.reset_index(drop=True), summary=summary)


def infer_chart_kind(
    table: pd.DataFrame,
    date_col: str | None = None,
    chronological_cols: set[str] | None = None,
) -> str | None:
    """Cheap heuristic for how the Streamlit UI should chart a tool result.

    Returns 'line' if the table is grouped by the date column or one of
    `chronological_cols` (e.g. a month-bucket column), 'bar' if it has a
    categorical group-by column plus a numeric value column, or None if
    there's nothing chart-worthy (e.g. a single number).
    """
    if table.shape[0] <= 1 or table.shape[1] < 2:
        return None
    first_col = table.columns[0]
    chronological = set(chronological_cols or ())
    if date_col:
        chronological.add(date_col)
    if first_col in chronological:
        return "line"
    return "bar"
