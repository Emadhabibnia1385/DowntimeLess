import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import agent  # noqa: E402


@pytest.fixture(autouse=True)
def no_real_checks(monkeypatch):
    """Collectors never run a real command in tests: every tool looks absent unless a test fakes it."""
    def absent(*args, **kwargs):
        raise FileNotFoundError("not available in tests")
    monkeypatch.setattr(agent, "has", lambda binary: False)
    monkeypatch.setattr(agent, "run_check", absent)
    monkeypatch.setattr(agent, "stream_lines", absent)
