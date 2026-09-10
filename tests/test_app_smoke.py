"""Smoke tests for the Streamlit app: it must import and run without
crashing, in whichever state the environment happens to be in (no API key,
API key but no dataset yet, etc). This does NOT exercise the LLM.
"""

from __future__ import annotations

from pathlib import Path

import pytest

st_testing = pytest.importorskip("streamlit.testing.v1")

APP_PATH = str(Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py")


def test_app_runs_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    at = st_testing.AppTest.from_file(APP_PATH).run()

    assert not at.exception
    assert any("ANTHROPIC_API_KEY" in w.value for w in at.warning)


def test_app_runs_with_api_key_but_no_dataset(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    at = st_testing.AppTest.from_file(APP_PATH).run()

    assert not at.exception
    assert any("Dataset not ready" in i.value for i in at.info)
