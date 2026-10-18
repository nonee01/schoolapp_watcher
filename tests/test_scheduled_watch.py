"""`s5 watch --scheduled`: one check per systemd timer tick, with the watch
loop's failure alerts, back-off and night pace carried in a state file."""

import json

import pytest
import requests
from typer.testing import CliRunner

from schoolapp import cli, watcher
from schoolapp.semesters import _factory

FAILING = "⚠️ SchoolApp watcher is failing"
RECOVERED = "✅ SchoolApp watcher recovered"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.setattr(watcher, "_scheduled_interval", lambda fast: float(fast))
    sent = []
    monkeypatch.setattr(watcher, "_try_notify",
                        lambda config, enabled, subject, text, notify_telegram=False: sent.append((subject, text)) or True)
    return tmp_path / "schoolapp", sent


def run(now, **kw):
    args = dict(email="e", password="p", timeout=5, semester="S5", state_file=None,
                interval=120, notify_email=True, config=None, notify_telegram=True)
    args.update(kw)
    return watcher.scheduled_check(now=now, **args)


def next_due(state_dir):
    return int((state_dir / "s5_next_due").read_text())


def test_success_sets_next_due_and_exits_zero_even_when_marks_changed(env, monkeypatch):
    state_dir, sent = env
    monkeypatch.setattr(watcher, "check_once", lambda **kw: 1)
    assert run(1000) == 0
    assert next_due(state_dir) == 1120
    assert json.loads((state_dir / "s5_watch.json").read_text())["failures"] == 0
    assert sent == []


def test_alerts_once_after_an_hour_of_failures(env, monkeypatch):
    state_dir, sent = env

    def boom(**kw):
        raise RuntimeError("portal down")

    monkeypatch.setattr(watcher, "check_once", boom)
    assert run(0) == 0
    assert next_due(state_dir) == 240  # back-off: 120 * 2**1
    run(3599)
    assert sent == []
    run(3600)
    assert [s for s, _ in sent] == [FAILING]
    assert "(3 attempts)" in sent[0][1] and "portal down" in sent[0][1]
    run(4000)
    assert len(sent) == 1


def test_network_errors_count_as_failures(env, monkeypatch):
    state_dir, _ = env

    def offline(**kw):
        raise requests.ConnectionError("no route")

    monkeypatch.setattr(watcher, "check_once", offline)
    run(0)
    run(10)
    state = json.loads((state_dir / "s5_watch.json").read_text())
    assert state["failures"] == 2 and state["last_error"] == "no route"


def test_back_off_is_capped_at_30_minutes(env, monkeypatch):
    state_dir, _ = env
    (state_dir).mkdir(parents=True, exist_ok=True)
    (state_dir / "s5_watch.json").write_text(json.dumps(
        {"failures": 6, "first_failure": 0, "alerted": True, "last_error": "x"}))

    def boom(**kw):
        raise RuntimeError("still down")

    monkeypatch.setattr(watcher, "check_once", boom)
    run(5000)
    assert next_due(state_dir) == 5000 + 1800


def test_recovery_after_an_alert_is_announced_and_state_cleared(env, monkeypatch):
    state_dir, sent = env
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "s5_watch.json").write_text(json.dumps(
        {"failures": 4, "first_failure": 0, "alerted": True, "last_error": "x"}))
    monkeypatch.setattr(watcher, "check_once", lambda **kw: 0)
    run(9000)
    assert [s for s, _ in sent] == [RECOVERED]
    state = json.loads((state_dir / "s5_watch.json").read_text())
    assert state == {"failures": 0, "first_failure": None, "alerted": False, "last_error": "x"}


def test_corrupt_state_file_starts_fresh(env, monkeypatch):
    state_dir, _ = env
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "s5_watch.json").write_text("{not json")
    monkeypatch.setattr(watcher, "check_once", lambda **kw: 0)
    assert run(100) == 0
    assert next_due(state_dir) == 220


def test_cli_scheduled_flag_calls_scheduled_check(monkeypatch):
    calls = []
    monkeypatch.setattr(_factory, "scheduled_check", lambda **kw: calls.append(kw) or 0)
    result = CliRunner().invoke(cli.app, ["s5", "watch", "--scheduled", "--interval", "120",
                                          "--notify-email", "--notify-telegram",
                                          "--email", "e", "--password", "p"])
    assert result.exit_code == 0, result.output
    assert calls and calls[0]["interval"] == 120
    assert calls[0]["notify_email"] and calls[0]["notify_telegram"] and calls[0]["semester"] == "S5"
