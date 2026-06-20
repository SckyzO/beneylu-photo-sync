import threading
from dataclasses import dataclass
from beneylu_photo_sync.web.jobs import SyncRunner


@dataclass
class FakeReport:
    downloaded: int = 3
    skipped: int = 1
    errors: int = 0
    pruned: int = 0


def test_run_records_report_and_returns_to_idle():
    done = threading.Event()
    runner = SyncRunner(lambda on_progress=None: (done.wait(1), FakeReport())[1])
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
    runner = SyncRunner(lambda on_progress=None: (gate.wait(1), FakeReport())[1])
    assert runner.trigger() is True
    assert runner.trigger() is False  # already running
    gate.set()
    runner._thread.join(2)


def test_live_progress_and_pruned_surface_in_status():
    seen, release = threading.Event(), threading.Event()

    def job(on_progress):
        on_progress(FakeReport(downloaded=2, skipped=0, errors=0, pruned=1))
        seen.set()
        release.wait(1)
        return FakeReport(downloaded=5, skipped=2, errors=0, pruned=1)

    runner = SyncRunner(job)
    runner.trigger()
    assert seen.wait(1)
    assert runner.status.downloaded == 2  # live, mid-run
    assert runner.status.pruned == 1
    release.set()
    runner._thread.join(2)
    assert runner.status.state == "idle"
    assert runner.status.downloaded == 5 and runner.status.skipped == 2
    assert runner.status.pruned == 1


def test_exception_surfaces_in_status():
    def boom(on_progress=None):
        raise RuntimeError("identifiants ENT manquants")
    runner = SyncRunner(boom)
    runner.trigger()
    runner._thread.join(2)
    assert runner.status.state == "error"
    assert "identifiants" in runner.status.last_error
