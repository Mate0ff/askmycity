"""AskMyCity — Streamlit entrypoint.

Ask a natural-language question about a city's 311-style service requests;
a tool-use LLM agent (Groq/GPT-OSS-120B) answers it by calling deterministic,
testable analytics tools (never arbitrary code) against the cached dataset.

UI follows docs/UI_DESIGN.md — dark theme (see .streamlit/config.toml),
CSS injected below, example-question chips wired via session state.
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

st.set_page_config(page_title="AskMyCity", page_icon="🏙️", layout="centered")

GITHUB_URL = "https://github.com/Mate0ff/askmycity"

# (question, answer-type tag) — one of each type so clicking all three in
# order shows both chart kinds. Order: simplest/broadest first. See
# docs/UI_DESIGN.md §3.3.
EXAMPLE_QUESTIONS = [
    ("How many 311 requests were filed in total?", "Count"),
    ("What are the top 10 most common request types?", "Ranked list"),
    ("How many requests per month were filed over the year?", "Trend"),
]

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

html, body, [class*="css"] {
    font-family: "Inter", -apple-system, "Segoe UI", sans-serif;
}

.block-container {
    max-width: 760px;
}

h1 {
    font-size: 1.9rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em;
}

.askmycity-header {
    border-bottom: 1px solid #232D38;
    padding-bottom: 1rem;
    margin-bottom: 1.5rem;
}

.askmycity-tagline {
    font-size: 0.95rem;
    font-weight: 400;
    color: #9AA7B2;
    margin-top: -0.75rem;
}

.askmycity-section-label {
    font-size: 0.8rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #9AA7B2;
    margin-bottom: 0.5rem;
}

/* "Card" look shared by the explainer box and the transparency expander. */
.askmycity-card, div[data-testid="stExpander"] {
    background-color: #131A22;
    border: 1px solid #232D38 !important;
    border-radius: 10px;
}
.askmycity-card {
    padding: 16px;
    margin-bottom: 1.5rem;
}

/* Example-question chips (st.button(type="secondary")). Full question text
   should be readable, not ellipsis-truncated to one line — override
   Streamlit's default single-line button text. */
button[kind="secondary"] {
    border-radius: 999px !important;
    background-color: transparent !important;
    border: 1px solid #232D38 !important;
    color: #9AA7B2 !important;
    height: auto !important;
    min-height: 3rem;
    white-space: normal !important;
    overflow-wrap: break-word;
    line-height: 1.3;
    padding: 0.6rem 0.9rem;
    transition: border-color 0.15s ease, color 0.15s ease, background-color 0.15s ease;
}
button[kind="secondary"] p {
    white-space: normal !important;
    overflow-wrap: break-word;
}
button[kind="secondary"]:hover {
    border-color: #38BDF8 !important;
    color: #38BDF8 !important;
    background-color: rgba(56, 189, 248, 0.08) !important;
}

.askmycity-chip-tag {
    text-align: center;
    font-size: 0.7rem;
    color: #9AA7B2;
    margin-top: 0.25rem;
    margin-bottom: 1rem;
}

/* Ask box */
.stTextInput input {
    border-radius: 8px !important;
    background-color: #131A22 !important;
    border: 1px solid #232D38 !important;
}
.stTextInput input:focus {
    border-color: #38BDF8 !important;
    box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.15) !important;
}
button[kind="primary"] {
    border-radius: 8px !important;
}

.askmycity-footer {
    color: #9AA7B2;
    font-size: 0.75rem;
    text-align: center;
    padding-top: 2rem;
}
.askmycity-footer a {
    color: #9AA7B2;
}
</style>
"""

_EXPLAINER_HTML = """
<div class="askmycity-card">
<strong>What's Austin 311?</strong><br>
311 is the non-emergency line (and app) Austin residents use to report stuff
like potholes, missed trash pickup, graffiti, or a stray dog — anything that
needs the city's attention but isn't a 911 emergency. Every request becomes a
public record: what was reported, where, when, and how long it took to
resolve. This app lets you ask questions about that record in plain English
instead of writing SQL. The dataset here covers <strong>Sept 2025 – Aug
2026</strong>.
</div>
"""


@st.cache_data(show_spinner=False)
def _load_data():
    return load_dataset()


def _submit_example(question: str) -> None:
    st.session_state["question"] = question
    st.session_state["auto_submit"] = True


def _render_header() -> None:
    st.markdown('<div class="askmycity-header">', unsafe_allow_html=True)
    st.title("🏙️ AskMyCity")
    st.markdown(
        '<p class="askmycity-tagline">Ask plain-English questions about Austin\'s '
        "311 data. An LLM agent turns your question into calls to a small set of "
        "deterministic analytics tools — no arbitrary code execution.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)


def _render_example_chips() -> None:
    st.markdown('<div class="askmycity-section-label">Try asking:</div>', unsafe_allow_html=True)
    cols = st.columns(3)
    for col, (question, tag) in zip(cols, EXAMPLE_QUESTIONS):
        with col:
            st.button(
                question,
                key=f"example_{tag}",
                type="secondary",
                use_container_width=True,
                on_click=_submit_example,
                args=(question,),
            )
            st.markdown(f'<div class="askmycity-chip-tag">{tag}</div>', unsafe_allow_html=True)


def _render_chart(answer) -> None:
    if answer.chart_table is None or answer.chart_table.empty:
        return
    if answer.chart_kind == "line":
        table = answer.chart_table.set_index(answer.chart_table.columns[0])
        st.line_chart(table)
    elif answer.chart_kind == "bar":
        cat_col, val_col = answer.chart_table.columns[0], answer.chart_table.columns[-1]
        chart = (
            alt.Chart(answer.chart_table)
            .mark_bar(color="#38BDF8")
            .encode(
                # sort='-y' ranks bars by value, matching top_n's order,
                # regardless of the category column's own sort order.
                x=alt.X(
                    f"{cat_col}:N",
                    sort="-y",
                    title=None,
                    # Vertical labels take far less horizontal room per bar
                    # than an angled label, so all of them fit without
                    # Vega-Lite silently dropping the crowded ones (what a
                    # -40° angle did with 5+ categories).
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


def _render_footer() -> None:
    st.markdown(
        '<div class="askmycity-footer">Built with an LLM tool-use agent over real '
        f'Austin 311 open data · <a href="{GITHUB_URL}" target="_blank">GitHub</a></div>',
        unsafe_allow_html=True,
    )


def main() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    _render_header()
    st.markdown(_EXPLAINER_HTML, unsafe_allow_html=True)

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

    _render_example_chips()

    st.session_state.setdefault("question", "")
    st.markdown('<div class="askmycity-section-label">Ask a question</div>', unsafe_allow_html=True)
    input_col, button_col = st.columns([5, 1], vertical_alignment="bottom")
    with input_col:
        question = st.text_input(
            "Ask a question",
            key="question",
            placeholder="e.g. What were the top 5 complaint categories last month?",
            label_visibility="collapsed",
        )
    with button_col:
        ask_clicked = st.button(
            "Ask", type="primary", disabled=not question, use_container_width=True
        )
    auto_submit = st.session_state.pop("auto_submit", False)
    submitted = ask_clicked or auto_submit

    if submitted:
        with st.spinner("Thinking..."):
            try:
                answer = ask(question, df)
            except Exception as exc:  # surfaced to the user rather than a stack trace
                st.error(f"Something went wrong answering that: {exc}")
                answer = None

        if answer is not None:
            st.markdown(answer.text)
            _render_chart(answer)

            if answer.tool_calls:
                with st.expander("How I got this"):
                    for call in answer.tool_calls:
                        st.markdown(f"**`{call.name}`**")
                        st.json(call.input)
                        if call.error:
                            st.error(call.error)
                        elif call.result_summary:
                            st.caption(call.result_summary)

    _render_footer()


if __name__ == "__main__":
    main()
