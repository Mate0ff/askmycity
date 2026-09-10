"""Describes the cached dataset's columns and turns that description into
Anthropic tool-use JSON schemas for the two analytics tools.

Everything the agent knows about *which columns exist* lives in one
`DatasetSchema` instance. That keeps `tools.py` (the actual computation)
fully generic — wiring up a different dataset is a matter of building a new
`DatasetSchema` and repointing `ACTIVE_SCHEMA`, not touching the agent loop,
the tool functions, or the Streamlit UI.
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
    # Derived, group-by-able time-bucket columns (e.g. a "YYYY-MM" month
    # column) used for trend/time-series questions — charted as a line.
    time_bucket_cols: tuple[ColumnSpec, ...] = field(default_factory=tuple)
    # Free-text guidance appended to the system prompt: dataset-specific
    # quirks/conventions the model needs but that don't fit a column list
    # (e.g. how to bucket a messy status column).
    notes: str = ""

    def column_names(self) -> set[str]:
        names = {self.date_col}
        names.update(c.name for c in self.categorical_cols)
        names.update(c.name for c in self.numeric_metric_cols)
        names.update(c.name for c in self.time_bucket_cols)
        return names

    def group_by_cols(self) -> list[str]:
        return [c.name for c in (*self.categorical_cols, *self.time_bucket_cols)]

    def describe_columns(self) -> str:
        """Human-readable column reference injected into the agent's system prompt."""
        lines = [f"- `{self.date_col}` (date): when the request was created."]
        for c in self.categorical_cols:
            examples = f" e.g. {', '.join(c.example_values)}" if c.example_values else ""
            lines.append(f"- `{c.name}` (category): {c.description}{examples}")
        for c in self.numeric_metric_cols:
            lines.append(f"- `{c.name}` (number): {c.description}")
        for c in self.time_bucket_cols:
            lines.append(f"- `{c.name}` (time bucket, group_by + sort_by='group'): {c.description}")
        return "\n".join(lines)


# --- Austin 311 dataset ------------------------------------------------------
# Source: data/DATA_DICTIONARY.md (City of Austin Open Data Portal, public
# domain). `sr_department_desc` and the zip/council-district columns are
# normalized at load time in `data.py`; `resolution_days` and `created_month`
# are derived there too — see that module for details.
AUSTIN_311_SCHEMA = DatasetSchema(
    dataset_name="Austin 311 service requests (Sep 2025-Aug 2026)",
    row_description="one row per resident-reported 311 service request",
    date_col="sr_created_date",
    categorical_cols=(
        ColumnSpec(
            "sr_type_desc",
            "request category (146 distinct values)",
            (
                "ARR - Garbage",
                "TPW - Parking Violation Enforcement",
                "Animal Protection - Loose Dog",
            ),
        ),
        ColumnSpec(
            "sr_department_desc",
            "owning city department (names normalized — see notes)",
            (
                "Austin Resource Recovery",
                "Austin Transportation and Public Works",
                "Austin Police Department",
            ),
        ),
        ColumnSpec(
            "sr_method_received_desc",
            "how the request was submitted",
            ("Phone", "Spot311 Interface", "Citizen Web Intake", "E-Mail"),
        ),
        ColumnSpec(
            "sr_status_desc",
            "current status — see notes for open/closed bucketing",
            ("Closed", "Open", "Duplicate (closed)", "Work In Progress"),
        ),
        ColumnSpec("sr_location_zip_code", "ZIP code of the request location (as a string)"),
        ColumnSpec(
            "sr_location_council_district",
            "Austin city council district, 1-10 (as a string; closest thing to a "
            "neighborhood field)",
        ),
    ),
    numeric_metric_cols=(
        ColumnSpec(
            "resolution_days",
            "days between filing and closing; null for requests not yet closed "
            "(right-skewed — prefer agg='median' over 'mean')",
        ),
    ),
    time_bucket_cols=(
        ColumnSpec("created_month", "the request's filing month, as 'YYYY-MM'"),
    ),
    notes=(
        "Status bucketing: treat ['Closed', 'Duplicate (closed)', 'Closed -Incomplete'] as "
        "resolved/closed, and ['Open', 'Duplicate (open)', 'Work In Progress', 'Pending'] as "
        "open/unresolved — use these lists with an OR filter on sr_status_desc, e.g. "
        "filters={'sr_status_desc': ['Open', 'Duplicate (open)', 'Work In Progress', "
        "'Pending']} — rather than assuming the column is a simple open/closed binary.\n"
        "Trend/time-series questions (month by month, over the year, did X spike): "
        "group_by='created_month' with sort_by='group' so results come back in "
        "chronological order.\n"
        "Rankings ('top N', 'most common', 'which X has the most'): use the top_n tool."
    ),
)

ACTIVE_SCHEMA = AUSTIN_311_SCHEMA


def build_tool_definitions(schema: DatasetSchema) -> list[dict]:
    """Anthropic `tools` param: JSON schemas for filter_and_aggregate and top_n.

    Column names are documented in the description text rather than as strict
    JSON-schema enums for filter *values* (categories like sr_type_desc have
    100+ real-world values not worth hardcoding) — validation of the actual
    column/value happens in `tools.py` at call time, where a bad column
    raises a clear ValueError that gets fed back to the model as a tool
    error. group_by/metric *column names*, however, are a small fixed set,
    so those are constrained via enum.
    """
    all_group_cols = schema.group_by_cols()
    metric_cols = [c.name for c in schema.numeric_metric_cols]
    column_ref = schema.describe_columns()
    guidance = f"\n\nGuidance:\n{schema.notes}" if schema.notes else ""

    filters_schema = {
        "type": "object",
        "description": (
            "Exact-match filters, e.g. {\"sr_type_desc\": \"ARR - Garbage\"} or "
            '{"sr_status_desc": ["Open", "Work In Progress"]} for an OR match on that column.'
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
                f"Available columns:\n{column_ref}{guidance}\n"
                "Use this for questions like totals, averages, breakdowns by category, or trends."
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
                    "sort_by": {
                        "type": "string",
                        "enum": ["value", "group"],
                        "description": (
                            "'value' (default) sorts grouped results by the number, "
                            "descending. 'group' sorts by the group_by column ascending — "
                            "use for chronological trends, e.g. group_by='created_month'."
                        ),
                    },
                },
                "required": ["agg"],
            },
        },
        {
            "name": "top_n",
            "description": (
                f"Rank groups of {schema.row_description} and return the top N — "
                "e.g. 'top 5 request categories' or 'which department gets the most requests'. "
                f"Available columns:\n{column_ref}{guidance}"
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
