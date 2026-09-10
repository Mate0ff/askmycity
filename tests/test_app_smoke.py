"""Smoke tests for the Streamlit app: it must import and run without
crashing, in whichever state the environment happens to be in (no API key,
API key but no dataset yet, etc). This does NOT exercise the LLM.
"""

from __future__ import annotations

from pathlib import Path

import pytest

st_testing = pytest.importorskip("streamlit.testing.v1")
import streamlit as st  # noqa: E402

APP_PATH = str(Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py")


@pytest.fixture(autouse=True)
def _clear_data_cache():
    # _load_data() is @st.cache_data'd; without clearing, one test's loaded
    # (or missing-file) result would leak into the next via the process-wide
    # cache since the wrapped function takes no arguments.
    st.cache_data.clear()


def test_app_runs_without_api_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    at = st_testing.AppTest.from_file(APP_PATH).run()

    assert not at.exception
    assert any("GROQ_API_KEY" in w.value for w in at.warning)


def test_app_runs_with_api_key_and_loads_real_dataset(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key-not-real")
    # Loading+cleaning the real 280k-row CSV can take longer than
    # AppTest's 3s default, especially on a cold cache.
    at = st_testing.AppTest.from_file(APP_PATH).run(timeout=30)

    assert not at.exception
    assert at.text_input  # the question box rendered, i.e. the dataset loaded fine


def test_app_shows_friendly_message_if_dataset_missing(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key-not-real")
    monkeypatch.setattr("askmycity.data.REAL_DATA_FILE", Path("does/not/exist.csv.gz"))
    at = st_testing.AppTest.from_file(APP_PATH).run()

    assert not at.exception
    assert any("Dataset not ready" in i.value for i in at.info)


def test_example_chip_click_fills_input_and_autosubmits(monkeypatch):
    # Matches the first entry of EXAMPLE_QUESTIONS in app/streamlit_app.py.
    example_question = "How many 311 requests were filed in total?"

    from askmycity.agent import AgentAnswer

    monkeypatch.setenv("GROQ_API_KEY", "test-key-not-real")
    monkeypatch.setattr(
        "askmycity.agent.ask",
        lambda question, df: AgentAnswer(text=f"Answer to: {question}"),
    )

    at = st_testing.AppTest.from_file(APP_PATH).run(timeout=30)
    assert not at.exception

    # Clicking a chip should fill the input AND run the query immediately —
    # no separate click on "Ask" required.
    at.button(key="example_Count").click().run(timeout=30)

    assert not at.exception
    assert at.session_state["question"] == example_question
    assert any(f"Answer to: {example_question}" in md.value for md in at.markdown)
