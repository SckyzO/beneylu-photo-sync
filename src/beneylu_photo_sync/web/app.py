from __future__ import annotations
import dataclasses
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.background import BackgroundTask

from ..core.client import BeneyluClient
from ..core.sources.cardboard import CardboardSource
from ..core.state import StateStore
from ..core.storage.filesystem import FilesystemStorage
from ..core.sync import Synchronizer
from . import archive, auth, gallery, thumbnails
from .jobs import SyncRunner
from .scheduler import IntervalScheduler
from .settings_store import SettingsStore

log = logging.getLogger("beneylu_photo_sync.web.app")

WEB_DIR = Path(__file__).parent


def _default_job(store: SettingsStore):
    def job(on_progress=None):
        cfg = store.effective()
        if not cfg.login or not cfg.password:
            raise RuntimeError("identifiants ENT manquants — voir Configuration")
        storage = FilesystemStorage(cfg.data_dir)
        client = BeneyluClient(base_url=cfg.base_url, login=cfg.login,
                               password=cfg.password, timeout=30.0)
        client.login()
        with StateStore(cfg.state_db) as state, client as c:
            return Synchronizer(c, [CardboardSource(excluded_boards=cfg.excluded_boards)],
                                storage, state, workers=cfg.sync_workers).run(on_progress)
    return job


def create_app(store: SettingsStore | None = None,
               runner: SyncRunner | None = None) -> FastAPI:
    if store is None:
        default_cfg = os.getenv("ENT_CONFIG_FILE") or str(
            Path(os.getenv("ENT_DATA_DIR", "./data")) / "config.json")
        store = SettingsStore(default_cfg)
    if runner is None:
        runner = SyncRunner(_default_job(store))

    templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        cfg = store.effective()
        scheduler = IntervalScheduler(cfg.sync_interval_hours, runner.trigger)
        scheduler.start()
        app.state.scheduler = scheduler
        yield
        scheduler.stop()

    app = FastAPI(lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")

    def guard(request: Request):
        if not auth.is_authenticated(request):
            raise HTTPException(status_code=status.HTTP_303_SEE_OTHER,
                                headers={"Location": "/login"})

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request, _=Depends(guard)):
        cfg = store.effective()
        return templates.TemplateResponse(
            request=request, name="gallery.html",
            context={"boards": gallery.scan(cfg.data_dir), "status": runner.status,
                     "configured": bool(cfg.login and cfg.password)})

    def _resolve_image(data_dir, key):
        # Only ever serve image files that live under the data root; reject
        # traversal (safe_resolve) and non-images so /thumb can't 500 on a
        # file Pillow can't open.
        src = gallery.safe_resolve(data_dir, key)
        if not src or src.suffix.lower() not in gallery.IMAGE_EXTS:
            raise HTTPException(status_code=404)
        return src

    def _resolve_dir(data_dir, key):
        # Resolve a gallery sub-tree to a directory under the data root. Reject
        # traversal and the thumbnail cache; empty key means the whole library.
        root = Path(data_dir).resolve()
        candidate = (root / key).resolve() if key else root
        if not candidate.is_dir() or not candidate.is_relative_to(root):
            raise HTTPException(status_code=404)
        rel = candidate.relative_to(root)
        if thumbnails.THUMB_DIR in rel.parts or candidate.name == thumbnails.THUMB_DIR:
            raise HTTPException(status_code=404)
        return root, candidate

    @app.get("/thumb/{key:path}")
    def thumb(key: str, _=Depends(guard)):
        cfg = store.effective()
        src = _resolve_image(cfg.data_dir, key)
        try:
            out = thumbnails.get_or_create(cfg.data_dir, src, key)
        except Exception:
            # Corrupt, truncated or oversized image: degrade to 404 instead of
            # 500. Logged (not swallowed) so bad files remain diagnosable.
            log.warning("Thumbnail generation failed for %s", key, exc_info=True)
            raise HTTPException(status_code=404)
        return FileResponse(out)

    @app.get("/photo/{key:path}")
    def photo(key: str, _=Depends(guard)):
        cfg = store.effective()
        src = _resolve_image(cfg.data_dir, key)
        return FileResponse(src)

    @app.get("/download")
    def download_all(_=Depends(guard)):
        cfg = store.effective()
        root, target = _resolve_dir(cfg.data_dir, "")
        zip_path = archive.build_zip(root, target)
        return FileResponse(zip_path, media_type="application/zip",
                            filename="beneylu-photos.zip",
                            background=BackgroundTask(os.unlink, zip_path))

    @app.get("/download/{key:path}")
    def download_subtree(key: str, _=Depends(guard)):
        cfg = store.effective()
        root, target = _resolve_dir(cfg.data_dir, key)
        zip_path = archive.build_zip(root, target)
        name = (target.name or "beneylu-photos") + ".zip"
        return FileResponse(zip_path, media_type="application/zip",
                            filename=name,
                            background=BackgroundTask(os.unlink, zip_path))

    @app.post("/sync")
    def sync(_=Depends(guard)):
        runner.trigger()
        return RedirectResponse("/", status_code=303)

    @app.get("/api/status")
    def status_api(_=Depends(guard)):
        return JSONResponse(dataclasses.asdict(runner.status))

    @app.get("/config", response_class=HTMLResponse)
    def config_get(request: Request, _=Depends(guard)):
        cfg = store.effective()
        return templates.TemplateResponse(
            request=request, name="config.html",
            context={"login": cfg.login or "", "has_password": cfg.has_password,
                     "sync_interval_hours": cfg.sync_interval_hours,
                     "excluded_boards": ", ".join(cfg.excluded_boards)})

    @app.post("/config")
    def config_post(login: str = Form(""), password: str = Form(""),
                    sync_interval_hours: int = Form(0),
                    excluded_boards: str = Form(""), _=Depends(guard)):
        excl = [s.strip() for s in excluded_boards.split(",") if s.strip()]
        store.save(login=login or None, password=password or None,
                   sync_interval_hours=sync_interval_hours, excluded_boards=excl)
        return RedirectResponse("/config", status_code=303)

    if auth.password_required():
        @app.get("/login", response_class=HTMLResponse)
        def login_get(request: Request):
            return templates.TemplateResponse(
                request=request, name="login.html", context={"error": False})

        @app.post("/login")
        def login_post(request: Request, password: str = Form("")):
            if auth.check_password(password):
                resp = RedirectResponse("/", status_code=303)
                resp.set_cookie(auth.COOKIE, auth.session_cookie_value(),
                                httponly=True, samesite="lax")
                return resp
            return templates.TemplateResponse(
                request=request, name="login.html",
                context={"error": True}, status_code=401)

        @app.get("/logout")
        def logout():
            resp = RedirectResponse("/login", status_code=303)
            resp.delete_cookie(auth.COOKIE)
            return resp

    return app
