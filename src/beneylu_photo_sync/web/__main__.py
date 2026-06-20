from __future__ import annotations
import logging
import os

import uvicorn

from .app import create_app

log = logging.getLogger("beneylu_photo_sync.web")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    host = os.getenv("ENT_WEB_HOST", "127.0.0.1")
    port = int(os.getenv("ENT_WEB_PORT", "8000"))
    if host == "0.0.0.0" and not os.getenv("ENT_WEB_PASSWORD"):  # noqa: S104
        log.warning("L'UI ecoute sur 0.0.0.0 (exposee sur le reseau) sans mot de "
                    "passe. Definis ENT_WEB_PASSWORD pour proteger l'acces.")
    uvicorn.run(create_app(), host=host, port=port)


if __name__ == "__main__":
    main()
