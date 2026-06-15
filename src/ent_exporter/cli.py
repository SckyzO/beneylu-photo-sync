# src/ent_exporter/cli.py
from __future__ import annotations
import logging
import typer
from .config import Settings
from .client import BeneyluClient
from .sources.cardboard import CardboardSource
from .storage.filesystem import FilesystemStorage
from .state import StateStore
from .sync import Synchronizer

app = typer.Typer(add_completion=False, help="Export school photos from Beneylu School.")

def _client(settings: Settings) -> BeneyluClient:
    c = BeneyluClient(base_url=settings.base_url, login=settings.login,
                      password=settings.password.get_secret_value(),
                      timeout=settings.request_timeout)
    c.login()
    return c

@app.command("login-test")
def login_test():
    """Verify the ENT credentials work."""
    settings = Settings()
    with _client(settings):
        typer.echo("Login OK")

@app.command("list-boards")
def list_boards():
    """List the class boards on the account."""
    settings = Settings()
    with _client(settings) as c:
        for b in c.boards():
            typer.echo(f"{b.id}  {b.name}")

@app.command("sync")
def sync():
    """Download new photos incrementally."""
    logging.basicConfig(level=logging.INFO)
    settings = Settings()
    storage = FilesystemStorage(settings.data_dir)
    state = StateStore(settings.state_db)
    with _client(settings) as c:
        report = Synchronizer(c, [CardboardSource()], storage, state).run()
    typer.echo(f"Sync done: downloaded={report.downloaded} skipped={report.skipped} errors={report.errors}")
    state.close()

if __name__ == "__main__":
    app()
