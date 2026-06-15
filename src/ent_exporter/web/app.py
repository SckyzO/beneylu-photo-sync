from __future__ import annotations
import dataclasses
import os
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..client import BeneyluClient
from ..sources.cardboard import CardboardSource
from ..state import StateStore
from ..storage.filesystem import FilesystemStorage
from ..sync import Synchronizer
from . import auth, gallery, thumbnails
from .jobs import SyncRunner
from .settings_store import SettingsStore

WEB_DIR = Path(__file__).parent


def _default_job(store: SettingsStore):
    def job():
        cfg = store.effective()
        if not cfg.login or not cfg.password:
            raise RuntimeError("identifiants ENT manquants — voir Configuration")
        storage = FilesystemStorage(cfg.data_dir)
        client = BeneyluClient(base_url=cfg.base_url, login=cfg.login,
                               password=cfg.password, timeout=30.0)
        client.login()
        with StateStore(cfg.state_db) as state, client as c:
            return Synchronizer(c, [CardboardSource()], storage, state).run()
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
    app = FastAPI()
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

    @app.get("/thumb/{key:path}")
    def thumb(key: str, _=Depends(guard)):
        cfg = store.effective()
        src = gallery.safe_resolve(cfg.data_dir, key)
        if not src:
            raise HTTPException(status_code=404)
        return FileResponse(thumbnails.get_or_create(cfg.data_dir, src, key))

    @app.get("/photo/{key:path}")
    def photo(key: str, _=Depends(guard)):
        cfg = store.effective()
        src = gallery.safe_resolve(cfg.data_dir, key)
        if not src:
            raise HTTPException(status_code=404)
        return FileResponse(src)

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
                     "sync_interval_hours": cfg.sync_interval_hours})

    @app.post("/config")
    def config_post(login: str = Form(""), password: str = Form(""),
                    sync_interval_hours: int = Form(0), _=Depends(guard)):
        store.save(login=login or None, password=password or None,
                   sync_interval_hours=sync_interval_hours)
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
