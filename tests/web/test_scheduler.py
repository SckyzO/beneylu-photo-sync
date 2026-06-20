import threading
import time
from beneylu_photo_sync.web.scheduler import IntervalScheduler


def test_disabled_when_interval_zero():
    calls = []
    sched = IntervalScheduler(0, lambda: calls.append(1))
    sched.start()
    time.sleep(0.2)
    assert sched._thread is None
    assert calls == []


def test_fires_callback_on_interval():
    fired = threading.Event()
    sched = IntervalScheduler(1, fired.set)   # 1 hour nominally
    sched.interval_seconds = 0.05             # shrink for the test
    sched.start()
    assert fired.wait(1.0) is True
    sched.stop()
