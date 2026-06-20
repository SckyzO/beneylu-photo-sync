import logging
from beneylu_photo_sync.web import __main__ as entry


def test_warns_when_bound_to_all_interfaces(monkeypatch, caplog):
    monkeypatch.setenv("ENT_WEB_HOST", "0.0.0.0")
    monkeypatch.delenv("ENT_WEB_PASSWORD", raising=False)
    started = {}
    monkeypatch.setattr(entry.uvicorn, "run",
                        lambda app, host, port: started.update(host=host, port=port))
    monkeypatch.setattr(entry, "create_app", lambda: object())
    with caplog.at_level(logging.WARNING):
        entry.main()
    assert started["host"] == "0.0.0.0"
    assert any("0.0.0.0" in r.message for r in caplog.records)


def test_no_warning_on_localhost(monkeypatch, caplog):
    monkeypatch.setenv("ENT_WEB_HOST", "127.0.0.1")
    monkeypatch.setattr(entry.uvicorn, "run", lambda app, host, port: None)
    monkeypatch.setattr(entry, "create_app", lambda: object())
    with caplog.at_level(logging.WARNING):
        entry.main()
    assert not any("0.0.0.0" in r.message for r in caplog.records)
