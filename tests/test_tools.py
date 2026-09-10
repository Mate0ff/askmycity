from __future__ import annotations

import pandas as pd
import pytest

from askmycity.tools import ToolInputError, filter_and_aggregate, infer_chart_kind, top_n


def test_count_all_rows(sample_df):
    result = filter_and_aggregate(sample_df, agg="count")
    assert result.table.iloc[0, 0] == len(sample_df)


def test_count_with_filter(sample_df):
    result = filter_and_aggregate(sample_df, agg="count", filters={"category": "pothole"})
    assert result.table.iloc[0, 0] == 3


def test_count_with_filter_list_is_or(sample_df):
    result = filter_and_aggregate(
        sample_df, agg="count", filters={"category": ["pothole", "graffiti"]}
    )
    assert result.table.iloc[0, 0] == 4


def test_date_range_filter(sample_df):
    result = filter_and_aggregate(
        sample_df,
        agg="count",
        date_col="created_date",
        start_date="2026-02-01",
        end_date="2026-02-28",
    )
    assert result.table.iloc[0, 0] == 3


def test_group_by_count(sample_df):
    result = filter_and_aggregate(sample_df, agg="count", group_by="category")
    counts = dict(zip(result.table["category"], result.table["count"]))
    assert counts == {"pothole": 3, "noise": 2, "graffiti": 1}


def test_group_by_mean_metric(sample_df):
    result = filter_and_aggregate(
        sample_df, agg="mean", metric="resolution_days", group_by="neighborhood"
    )
    by_neighborhood = dict(zip(result.table["neighborhood"], result.table["resolution_days"]))
    assert by_neighborhood["north"] == pytest.approx((2 + 1 + 10) / 3)
    assert by_neighborhood["south"] == pytest.approx((5 + 3 + 4) / 3)


def test_non_count_agg_requires_metric(sample_df):
    with pytest.raises(ToolInputError, match="metric is required"):
        filter_and_aggregate(sample_df, agg="mean")


def test_unknown_column_raises(sample_df):
    with pytest.raises(ToolInputError, match="Unknown column"):
        filter_and_aggregate(sample_df, agg="count", filters={"nope": "x"})


def test_unknown_agg_raises(sample_df):
    with pytest.raises(ToolInputError, match="Unknown agg"):
        filter_and_aggregate(sample_df, agg="bogus")


def test_top_n_basic(sample_df):
    result = top_n(sample_df, group_by="category", agg="count", n=2)
    assert list(result.table["category"]) == ["pothole", "noise"]
    assert len(result.table) == 2


def test_top_n_ascending(sample_df):
    result = top_n(sample_df, group_by="category", agg="count", n=1, ascending=True)
    assert list(result.table["category"]) == ["graffiti"]


def test_tool_result_to_json_shape(sample_df):
    result = filter_and_aggregate(sample_df, agg="count", group_by="category")
    payload = result.to_json()
    assert set(payload) == {"summary", "columns", "rows", "truncated"}
    assert payload["truncated"] is False
    assert len(payload["rows"]) == len(result.table)


def test_infer_chart_kind_bar_for_group_by(sample_df):
    result = filter_and_aggregate(sample_df, agg="count", group_by="category")
    assert infer_chart_kind(result.table) == "bar"


def test_infer_chart_kind_none_for_single_value(sample_df):
    result = filter_and_aggregate(sample_df, agg="count")
    assert infer_chart_kind(result.table) is None


def test_sort_by_group_orders_chronologically():
    df = pd.DataFrame(
        {
            "created_month": ["2026-03", "2026-01", "2026-02", "2026-01"],
            "category": ["pothole"] * 4,
        }
    )
    result = filter_and_aggregate(df, agg="count", group_by="created_month", sort_by="group")
    assert list(result.table["created_month"]) == ["2026-01", "2026-02", "2026-03"]


def test_sort_by_default_orders_by_value_desc(sample_df):
    result = filter_and_aggregate(sample_df, agg="count", group_by="category")
    assert list(result.table["count"]) == sorted(result.table["count"], reverse=True)


def test_sort_by_invalid_raises(sample_df):
    with pytest.raises(ToolInputError, match="sort_by"):
        filter_and_aggregate(sample_df, agg="count", group_by="category", sort_by="bogus")


def test_infer_chart_kind_line_for_chronological_col():
    table = pd.DataFrame({"created_month": ["2026-01", "2026-02"], "count": [3, 5]})
    assert infer_chart_kind(table, chronological_cols={"created_month"}) == "line"
