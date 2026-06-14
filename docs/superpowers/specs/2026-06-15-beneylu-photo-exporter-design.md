# Design — ent_exporter : exporteur de photos Beneylu School

**Date** : 2026-06-15
**Statut** : validé (brainstorming)

## Problème

`ent-ecole.fr` est une instance white-label de **Beneylu School** (ENT pour le primaire).
L'école y publie des photos que les parents doivent télécharger manuellement, écran par
écran. Objectif : **automatiser la récupération des photos**, avec un gros sync initial
puis une **sync incrémentale récurrente**, dans un outil **self-hostable réutilisable par
d'autres familles**.

## Recon (faits vérifiés le 2026-06-15, compte réel)

Plateforme = Beneylu School : SPA React, **API REST JSON privée** sur la même origine,
auth par **cookie `BEARER`** (JWT, rôle `PARENT`, expiration ~15 min) + `refresh_token`.
**Tout le pipeline fonctionne en pur HTTP — aucun navigateur requis** (validé : JPEG
1920×1440 téléchargé de bout en bout).

Pipeline (base `https://www.ent-ecole.fr`) :

1. `POST /api/auth/login_check` body `{login, password, remember_me, first_name:"", last_name:"", otp:"", captcha:""}`
   → pose cookie `BEARER`, renvoie `{auth_url, refresh_token}`. **Le champ est `login`, pas `username`.**
2. `POST /api/auth/token/refresh` body `{refresh_token}` → renouvelle le cookie.
3. `GET /api/auth/users/me` → profil + `children[]`.
4. `GET /api/auth/groups/classrooms-and-schools` → écoles/classes (ids).
5. `GET /api/cardboard/boards` → tableaux (type Padlet).
6. `GET /api/cardboard/boards/{boardId}/cards` → cartes ; carte `type:"image"` porte
   `cardAttachments:[{mediaId, entityId, entityType:"Card", timestamp, signature}]`.
   **`timestamp`/`signature` sont éphémères** (régénérés à chaque lecture).
7. `GET /api/media-library/media/{mediaId}?mediaId={id}&entityId={eid}&entityType=Card&timestamp={ts}&signature={sig}`
   → JSON `{label (nom de fichier d'origine), mime_type, downloadable, url, display_url}`
   où `url` = **URL S3 OVH pré-signée** (full-res, `Expires=3600`).
8. `GET <url S3>` → les octets de l'image (EXIF d'origine conservé : date de prise de vue).

Sources média non encore explorées (Phase 2) : `family-information/{id}/media`, pièces
jointes du chat, newspaper.

## Décisions produit (validées)

| Axe | Décision |
|---|---|
| Langage / stack | **Python** (httpx, pydantic, FastAPI, Pillow, APScheduler) |
| Sources v1 | **Cardboard uniquement**, architecture extensible par interface `Source` |
| Stockage | **Backend pluggable `Storage`**, implémentation **Filesystem** par défaut |
| Sync | Gros sync initial + **incrémental** (ne re-télécharge pas l'existant) |
| Distribution | **Docker (UI web)** + **GitHub Actions (cron)**, cœur partagé |
| Déploiement | **Mono-famille / self-hosted** (1 compte ENT parent, multi-enfants OK), pas de multi-tenant |

## Architecture

```
ent_exporter/
├─ core/                      # runtime-agnostique
│  ├─ client.py              # BeneyluClient : httpx.Client + cookie jar ; login_check,
│  │                         #   token/refresh, auto-refresh sur 401 ; méthodes typées
│  │                         #   me(), boards(), cards(board_id), resolve_media(attachment)
│  ├─ models.py              # dataclasses/pydantic : Child, Board, Card, CardAttachment,
│  │                         #   ResolvedMedia, MediaItem
│  ├─ sources/
│  │   ├─ base.py            # Source(ABC) : name ; iter_items(client) -> Iterable[MediaItem]
│  │   └─ cardboard.py       # CardboardSource (v1)
│  ├─ storage/
│  │   ├─ base.py            # Storage(ABC) : exists(key)->bool ; write(key, stream, meta)
│  │   └─ filesystem.py      # FilesystemStorage (défaut)
│  ├─ state.py               # StateStore (SQLite) : media déjà récupérés (clé media_id),
│  │                         #   curseur par carte (updatedAt) ; idempotence
│  ├─ naming.py              # clé/chemin : <child|board>/<AAAA-MM>/<label> ; date EXIF→createdAt
│  ├─ sync.py                # Synchronizer : orchestre source→state→resolve→storage→record
│  └─ config.py              # Settings (pydantic-settings) : credentials, storage, sources, planif
├─ web/                       # FastAPI : config, déclenchement sync, statut/logs, galerie (Docker)
├─ runtimes/
│  ├─ docker/                # Dockerfile + compose : APScheduler + UI ; volumes data/ + state.db
│  └─ github-actions/        # workflow cron : python -m ent_exporter sync ; secrets GH ; storage=Drive
├─ cli.py                     # ent-exporter : sync | login-test | list-boards
├─ tests/                     # fixtures recon + mocks httpx (respx) ; zéro appel live
├─ pyproject.toml
└─ docs/
```

## Flux de synchronisation

```
login() → users/me (enfants) → boards()
   pour chaque board : cards(board_id)
       pour chaque card.cardAttachments :
           key = media_id
           si state.has(key) : skip
           sinon :
               media = client.resolve_media(attachment)   # JSON signé
               path  = naming.path_for(media, board, child)
               si not storage.exists(path) :
                   stream = client.download(media.url)     # S3 pré-signé
                   storage.write(path, stream)
               state.record(key, path, card.updatedAt)
```

Idempotent : relançable sans doublon. Le gros sync initial = state vide ; les runs
suivants ne traitent que les nouveaux `media_id`.

## Décisions techniques

- **State** : SQLite (`state.db`), table `media(media_id PK, board_id, card_id, path, downloaded_at, card_updated_at)`.
  Indexé sur `media_id` (stable, unique). Optimisation Phase 2 : sauter une carte entière
  si `card.updatedAt` inchangé depuis le dernier run.
- **Auth/refresh** : login au début de chaque run ; refresh auto si un run dépasse ~15 min ;
  un `BeneyluClient` encapsule le cookie jar et retente une fois après refresh sur 401.
  Détection `X-Bns-Captcha` → exception explicite (compte temporairement verrouillé), jamais avalée.
- **Gestion d'erreurs** : échec *par item* → loggé + retry borné, n'abat pas le run et est
  comptabilisé dans le rapport final ; échec *auth/réseau global* → remonte la vraie cause.
  Aucun `except` silencieux retournant une valeur par défaut.
- **Secrets** : credentials via variables d'env / `.env` (Docker) ou GitHub Secrets (Actions) ;
  jamais loggés, jamais écrits dans le state. L'UI web qui les persiste utilise un fichier
  `chmod 600`. ⚠️ Stocker les identifiants ENT = donnée très sensible → documenté, hors-scope
  multi-tenant.
- **Nommage** : `label` (nom d'origine, ex. `IMG_7363.jpg`) ; date depuis EXIF `DateTimeOriginal`
  sinon `card.createdAt` ; collision de nom → suffixe `media_id`. Arborescence
  `data/<board>/<AAAA-MM>/<label>`.

## Tests (TDD)

- Fixtures JSON figées issues de la recon (login, users/me, boards, cards, resolve_media).
- Mock HTTP (respx/httpx MockTransport) — **aucun appel live en CI**.
- Couverture utile : parsing client, énumération `CardboardSource`, idempotence `Storage`,
  skip via `StateStore`, `naming` (EXIF vs createdAt, collisions), retry/erreurs auth, captcha.
- Chaque bug → test rouge avant fix.

## Documentation utilisateur (livrable de premier plan)

`README.md` **en français, simple, orienté utilisateur final** (pas développeur) :
- schéma **mermaid** « comment ça marche » (connexion → tableaux → photos rangées) ;
- sections **Installation** (Docker / GitHub Actions), **Configuration** (identifiants,
  destination, fréquence), **Utilisation** (UI web + commandes CLI) ;
- **captures d'écran** de l'UI web (`docs/screenshots/`), ajoutées quand l'UI existe ;
- section **Vie privée & sécurité**.

Squelette posé dès maintenant (mermaid + structure) ; les commandes exactes et les
captures sont complétées au fil des features (pas de doc spéculative qui dériverait).

## Découpage en deux phases

**Phase 1 (v1)** : `core` (client, cardboard, filesystem, state, naming, sync), CLI,
Dockerfile/compose, sync incrémental testé. Livrable autonome et utile.

**Phase 2** : UI web (galerie, config, statut), runtime GitHub Actions + backend Google Drive,
sources additionnelles (famille / chat / newspaper) via l'interface `Source`, optimisation
curseur `updatedAt`.

## Hors-scope (YAGNI)

Multi-tenant / inscription multi-familles ; édition/upload vers l'ENT ; notifications push ;
sources non-photo (notes, devoirs, agenda).
