# tests/test_client_refresh.py
import httpx
import respx
import pytest
from beneylu_photo_sync.core.client import BeneyluClient

BASE = "https://www.ent-ecole.fr"


def _client():
    return BeneyluClient(base_url=BASE, login="x", password="y")


@respx.mock
def test_boards_refreshes_jwt_on_401_then_succeeds(fixture):
    boards_route = respx.get(f"{BASE}/api/cardboard/boards").mock(
        side_effect=[
            httpx.Response(401, json={}),
            httpx.Response(200, json=fixture("boards.json")),
        ]
    )
    refresh_route = respx.post(f"{BASE}/api/auth/token/refresh").mock(
        return_value=httpx.Response(200, json={"refresh_token": "new-refresh"})
    )
    c = _client()
    c.refresh_token = "old-refresh"

    boards = c.boards()

    assert [b.name for b in boards] == ["DANS LA CLASSE DES PS", "APEIT"]
    assert refresh_route.call_count == 1
    assert boards_route.call_count == 2
    assert c.refresh_token == "new-refresh"


@respx.mock
def test_401_without_refresh_token_does_not_loop():
    respx.get(f"{BASE}/api/cardboard/boards").mock(return_value=httpx.Response(401, json={}))
    c = _client()
    assert c.refresh_token is None
    with pytest.raises(httpx.HTTPStatusError):
        c.boards()


@respx.mock
def test_download_refreshes_jwt_on_401_then_streams():
    respx.get("https://s3.example.test/x.jpg").mock(
        side_effect=[
            httpx.Response(401, content=b""),
            httpx.Response(200, content=b"\xff\xd8\xffDATA"),
        ]
    )
    refresh_route = respx.post(f"{BASE}/api/auth/token/refresh").mock(
        return_value=httpx.Response(200, json={"refresh_token": "new-refresh"})
    )
    c = _client()
    c.refresh_token = "old-refresh"

    data = b"".join(c.download("https://s3.example.test/x.jpg"))

    assert data == b"\xff\xd8\xffDATA"
    assert refresh_route.call_count == 1


@respx.mock
def test_download_401_without_refresh_token_raises():
    respx.get("https://s3.example.test/x.jpg").mock(return_value=httpx.Response(401, content=b""))
    c = _client()
    with pytest.raises(httpx.HTTPStatusError):
        b"".join(c.download("https://s3.example.test/x.jpg"))


def test_concurrent_401s_trigger_a_single_refresh():
    # Under a parallel sync, many in-flight requests can see a 401 at once.
    # They must collapse to ONE token refresh, not one per thread.
    import threading
    c = _client()
    c.refresh_token = "old"
    refresh_calls = []
    c.refresh = lambda: refresh_calls.append(1)  # count, don't hit network
    gen = c._refresh_gen                          # generation observed at 401 time
    ready = threading.Barrier(2)

    def worker():
        ready.wait()           # line both threads up to contend on the lock
        c._refresh_once(gen)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(refresh_calls) == 1
    assert c._refresh_gen == gen + 1
