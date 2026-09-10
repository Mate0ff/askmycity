"""AskMyCity — Streamlit entrypoint.

Ask a natural-language question about a city's 311-style service requests;
a tool-use LLM agent (Groq/GPT-OSS-120B) answers it by calling deterministic,
testable analytics tools (never arbitrary code) against the cached dataset.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import altair as alt
import streamlit as st

# Make `src/` importable when run as `streamlit run app/streamlit_app.py`
# without an editable install.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from askmycity.agent import ask  # noqa: E402
from askmycity.data import DatasetNotReadyError, load_dataset  # noqa: E402
from askmycity.schema import ACTIVE_SCHEMA  # noqa: E402

st.set_page_config(page_title="AskMyCity", page_icon="🏙️", layout="centered")


@st.cache_data(show_spinner=False)
def _load_data():
    return load_dataset()


def main() -> None:
    st.title("🏙️ AskMyCity")
    st.caption(
        f"Ask questions in plain English about {ACTIVE_SCHEMA.dataset_name}. "
        "An LLM agent turns your question into calls to a small set of "
        "deterministic analytics tools — no arbitrary code execution."
    )

    if not os.environ.get("GROQ_API_KEY"):
        st.warning(
            "No `GROQ_API_KEY` found. Set it as an environment variable locally, "
            "or as a Streamlit Cloud secret before deploying. See the README."
        )
        st.stop()

    try:
        df = _load_data()
    except DatasetNotReadyError as exc:
        st.info(f"Dataset not ready yet: {exc}")
        st.stop()
        return

    question = st.text_input(
        "Ask a question", placeholder="e.g. What were the top 5 complaint categories last month?"
    )
    submitted = st.button("Ask", type="primary", disabled=not question)

    if not submitted:
        return

    with st.spinner("Thinking..."):
        try:
            answer = ask(question, df)
        except Exception as exc:  # surfaced to the user rather than a stack trace
            st.error(f"Something went wrong answering that: {exc}")
            return

    st.markdown(answer.text)

    if answer.chart_table is not None and not answer.chart_table.empty:
        table = answer.chart_table.set_index(answer.chart_table.columns[0])
        if answer.chart_kind == "line":
            st.line_chart(table)
        elif answer.chart_kind == "bar":
            cat_col, val_col = answer.chart_table.columns[0], answer.chart_table.columns[-1]
            chart = (
                alt.Chart(answer.chart_table)
                .mark_bar()
                .encode(
                    # sort='-y' ranks bars by value, matching top_n's order,
                    # regardless of the category column's own sort order.
                    x=alt.X(
                        f"{cat_col}:N",
                        sort="-y",
                        title=None,
                        # Vertical labels take far less horizontal room per
                        # bar than an angled label, so all of them fit
                        # without Vega-Lite silently dropping the crowded
                        # ones (what a -40° angle did with 5+ categories).
                        axis=alt.Axis(labelAngle=-90, labelLimit=200, labelOverlap=False),
                    ),
                    y=alt.Y(f"{val_col}:Q", title=val_col),
                    tooltip=list(answer.chart_table.columns),
                )
                .properties(height=420)
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.dataframe(answer.chart_table, use_container_width=True)

    if answer.tool_calls:
        with st.expander("How I got this"):
            for call in answer.tool_calls:
                st.markdown(f"**`{call.name}`**")
                st.json(call.input)
                if call.error:
                    st.error(call.error)
                elif call.result_summary:
                    st.caption(call.result_summary)


if __name__ == "__main__":
    main()
