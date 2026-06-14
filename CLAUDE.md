# CLAUDE.md — ent_exporter

Exporteur automatique des photos publiées par l'école sur **Beneylu School**
(instance `ent-ecole.fr`). Gros sync initial + sync incrémentale. Self-hostable,
réutilisable par d'autres familles. Stack **Python**.

> Design complet : `docs/superpowers/specs/2026-06-15-beneylu-photo-exporter-design.md`

## Pipeline API Beneylu (critique, non-trivial)

`ent-ecole.fr` = SPA React + **API REST JSON privée**, auth par **cookie `BEARER`**
(JWT, rôle PARENT, **exp ~15 min**) + `refresh_token`. **Aucun navigateur requis** —
tout est faisable en HTTP pur (vérifié). Base : `https://www.ent-ecole.fr`.

1. `POST /api/auth/login_check` body `{login, password, remember_me, first_name:"", last_name:"", otp:"", captcha:""}`
   → cookie `BEARER` + `{auth_url, refresh_token}`. **Champ `login`, PAS `username`.**
2. `POST /api/auth/token/refresh` body `{refresh_token}`.
3. `GET /api/auth/users/me` → `children[]`.
4. `GET /api/cardboard/boards` → tableaux.
5. `GET /api/cardboard/boards/{boardId}/cards` → cartes ; `cardAttachments:[{mediaId, entityId, entityType:"Card", timestamp, signature}]` (**signature éphémère**).
6. `GET /api/media-library/media/{mediaId}?mediaId=&entityId=&entityType=Card&timestamp=&signature=`
   → `{label, mime_type, url}` ; `url` = **S3 OVH pré-signé** (expire 1h).
7. `GET <url S3>` → octets JPEG (EXIF d'origine conservé).

Pièges : auth par **cookie** (pas header Bearer) ; `signature`/`timestamp` à résoudre
**au moment du download** ; en-tête `X-Bns-Captcha` = compte verrouillé après échecs.

## Architecture

`core/` runtime-agnostique : `client.py` (BeneyluClient), `sources/` (interface `Source`,
`cardboard.py` en v1), `storage/` (interface `Storage`, `filesystem.py` défaut),
`state.py` (SQLite, idempotence par `media_id`), `naming.py`, `sync.py`, `config.py`.
Par-dessus : `web/` (FastAPI, runtime Docker), `runtimes/` (docker, github-actions), `cli.py`.

**Extensibilité par interface, pas par liste hardcodée** : une nouvelle source/un nouveau
backend storage s'ajoute sans toucher au cœur.

## Commandes

```bash
ent-exporter login-test      # valide les identifiants
ent-exporter list-boards     # liste les tableaux du compte
ent-exporter sync            # synchronise (incrémental)
pytest                       # tests (mocks httpx, AUCUN appel live)
```

## Conventions

- **Sources d'abord (context7)** pour toute lib/CLI/API versionnée (httpx, FastAPI, pydantic…).
- **TDD** : tout bug → test rouge avant le fix ; toute feature active couverte. **CI verte avant de déclarer terminé.**
- **Pas d'`except` silencieux** : échec *par item* loggé + retry borné (n'abat pas le run) ;
  échec global → remonter la vraie cause.
- **Secrets** : credentials via env/`.env` (Docker) ou GitHub Secrets (Actions) ; **jamais loggés,
  jamais dans le state**. UI persistant → fichier `chmod 600`.
- **Refactoring à risque = 2 phases** : nouveau mécanisme en parallèle + fallback, puis dépréciation.
- Éditions chirurgicales, validables indépendamment.

## Phases

- **Phase 1** : cardboard + filesystem + state + CLI + Docker, sync incrémental testé.
- **Phase 2** : UI web galerie, runtime Actions + Google Drive, sources famille/chat/newspaper.

## Hors-scope

Multi-tenant, upload vers l'ENT, sources non-photo.
