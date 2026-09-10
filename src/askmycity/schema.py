"""Describes the cached dataset's columns and turns that description into
Anthropic tool-use JSON schemas for the two analytics tools.

Everything the agent knows about *which columns exist* lives in one
`DatasetSchema` instance. That keeps `tools.py` (the actual computation)
fully generic, and means wiring up the researcher's real dataset is a matter
of editing `REAL_SCHEMA` below (or building a new `DatasetSchema`) rather than
touching the agent loop, the tool functions, or the Streamlit UI.

TODO(researcher-handoff): replace `ACTIVE_SCHEMA` with a schema built from
the real column names once `data/DATA_DICTIONARY.md` lands, and point
`askmycity.data.load_dataset` at the cached file.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    description: str
    example_values: tuple[str, ...] = ()


@dataclass(frozen=True)
class DatasetSchema:
    """Everything the agent/tool layer needs to know about the dataset shape."""

    dataset_name: str
    row_description: str
    date_col: str
    categorical_cols: tuple[ColumnSpec, ...] = field(default_factory=tuple)
    numeric_metric_cols: tuple[ColumnSpec, ...] = field(default_factory=tuple)

    def column_names(self) -> set[str]:
        names = {self.date_col}
        names.update(c.name for c in self.categorical_cols)
        names.update(c.name for c in self.numeric_metric_cols)
        return names

    def describe_columns(self) -> str:
        """Human-readable column reference injected into the agent's system prompt."""
        lines = [f"- `{self.date_col}` (date): when the request was created."]
        for c in self.categorical_cols:
            examples = f" e.g. {', '.join(c.example_values)}" if c.example_values else ""
            lines.append(f"- `{c.name}` (category): {c.description}{examples}")
        for c in self.numeric_metric_cols:
            lines.append(f"- `{c.name}` (number): {c.description}")
        return "\n".join(lines)


# --- Placeholder schema -----------------------------------------------------
# Generic shape of a 311-style civic service-request dataset, used so the
# agent, tools, and UI are all buildable/testable before the researcher's
# specific city dataset and DATA_DICTIONARY.md land. Swap for the real thing
# in one place: build a new DatasetSchema and repoint ACTIVE_SCHEMA.
PLACEHOLDER_SCHEMA = DatasetSchema(
    dataset_name="city 311 service requests (placeholder shape)",
    row_description="one row per resident-reported service request",
    date_col="created_date",
    categorical_cols=(
        ColumnSpec(
            "category",
            "type of request",
            ("pothole", "noise complaint", "graffiti", "streetlight outage"),
        ),
        ColumnSpec("agency", "city agency responsible", ("DOT", "Parks", "Sanitation")),
        ColumnSpec("status", "current status", ("open", "closed", "in progress")),
        ColumnSpec("neighborhood", "neighborhood/borough where reported"),
    ),
    numeric_metric_cols=(
        ColumnSpec("resolution_days", "days between created_date and closed_date"),
    ),
)

ACTIVE_SCHEMA = PLACEHOLDER_SCHEMA


def build_tool_definitions(schema: DatasetSchema) -> list[dict]:
    """Anthropic `tools` param: JSON schemas for filter_and_aggregate and top_n.

    Column names are documented in the description text rather than as strict
    JSON-schema enums, because the categorical values in the real dataset
    aren't fixed yet — validation of the actual column/value happens in
    `tools.py` at call time, where a bad column raises a clear ValueError
    that gets fed back to the model as a tool error.
    """
    all_group_cols = [c.name for c in schema.categorical_cols]
    metric_cols = [c.name for c in schema.numeric_metric_cols]
    column_ref = schema.describe_columns()

    filters_schema = {
        "type": "object",
        "description": (
            "Exact-match filters, e.g. {\"category\": \"pothole\"} or "
            '{"category": ["pothole", "graffiti"]} for an OR match on that column.'
        ),
        "additionalProperties": {
            "anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]
        },
    }

    agg_enum = ["count", "sum", "mean", "median", "min", "max"]

    return [
        {
            "name": "filter_and_aggregate",
            "description": (
                f"Filter {schema.row_description} from {schema.dataset_name} by date range "
                "and/or column filters, then aggregate — optionally grouped by one column. "
                f"Available columns:\n{column_ref}\n"
                "Use this for questions like totals, averages, or breakdowns by category."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "ISO date, inclusive."},
                    "end_date": {"type": "string", "description": "ISO date, inclusive."},
                    "filters": filters_schema,
                    "group_by": {
                        "type": "string",
                        "enum": all_group_cols,
                        "description": "Optional column to group results by.",
                    },
                    "agg": {
                        "type": "string",
                        "enum": agg_enum,
                        "description": "Aggregation function. Use 'count' to count requests.",
                    },
                    "metric": {
                        "type": "string",
                        "enum": metric_cols,
                        "description": "Numeric column to aggregate. Omit when agg='count'.",
                    },
                },
                "required": ["agg"],
            },
        },
        {
            "name": "top_n",
            "description": (
                f"Rank groups of {schema.row_description} and return the top N — "
                "e.g. 'top 5 neighborhoods by number of complaints'. "
                f"Available columns:\n{column_ref}"
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "group_by": {
                        "type": "string",
                        "enum": all_group_cols,
                        "description": "Column to rank by group.",
                    },
                    "agg": {
                        "type": "string",
                        "enum": agg_enum,
                        "description": "Aggregation function. Use 'count' to count requests.",
                    },
                    "metric": {
                        "type": "string",
                        "enum": metric_cols,
                        "description": "Numeric column to aggregate. Omit when agg='count'.",
                    },
                    "n": {"type": "integer", "description": "How many top groups to return."},
                    "ascending": {
                        "type": "boolean",
                        "description": "True for bottom-N instead of top-N.",
                    },
                    "start_date": {"type": "string", "description": "ISO date, inclusive."},
                    "end_date": {"type": "string", "description": "ISO date, inclusive."},
                    "filters": filters_schema,
                },
                "required": ["group_by", "agg"],
            },
        },
    ]
