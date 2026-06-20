import threading
from dataclasses import dataclass
from beneylu_photo_sync.web.jobs import SyncRunner


@dataclass
class FakeReport:
    downloaded: int = 3
    skipped: int = 1
    errors: int = 0


def test_run_records_report_and_returns_to_idle():
    done = threading.Event()
    runner = SyncRunner(lambda: (done.wait(1), FakeReport())[1])
    assert runner.trigger() is True
    assert runner.status.state == "running"
    done.set()
    runner._thread.join(2)
    assert runner.status.state == "idle"
    assert runner.status.downloaded == 3
    assert runner.status.skipped == 1
    assert runner.status.last_run_at is not None


def test_single_concurrent_run():
    gate = threading.Event()
    runner = SyncRunner(lambda: (gate.wait(1), FakeReport())[1])
    assert runner.trigger() is True
    assert runner.trigger() is False  # already running
    gate.set()
    runner._thread.join(2)


def test_exception_surfaces_in_status():
    def boom():
        raise RuntimeError("identifiants ENT manquants")
    runner = SyncRunner(boom)
    runner.trigger()
    runner._thread.join(2)
    assert runner.status.state == "error"
    assert "identifiants" in runner.status.last_error
