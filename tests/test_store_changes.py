import json

from schoolapp import store


def _write(tmp_path, entries):
    p = tmp_path / "schoolapp" / "changes.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")


def test_read_changes_newest_first_with_filters(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    _write(tmp_path, [
        {"ts": "2026-07-01T10:00:00", "type": "grades", "semester": "S4", "summary": "a"},
        {"ts": "2026-07-02T10:00:00", "type": "absences", "semester": "S4", "summary": "b"},
        {"ts": "2026-07-03T10:00:00", "type": "grades", "semester": "S4", "summary": "c"},
    ])
    items = store.read_changes()
    assert [i["summary"] for i in items] == ["c", "b", "a"]
    assert [i["summary"] for i in store.read_changes(limit=1)] == ["c"]
    assert [i["summary"] for i in store.read_changes(type="grades")] == ["c", "a"]
    assert [i["summary"] for i in store.read_changes(since="2026-07-01T23:59:59")] == ["c", "b"]


def test_read_changes_absent_or_corrupt(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    assert store.read_changes() == []
    p = tmp_path / "schoolapp" / "changes.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('{"ts": "2026-07-01", "type": "x", "summary": "ok"}\nnot-json\n', encoding="utf-8")
    assert [i["summary"] for i in store.read_changes()] == ["ok"]
