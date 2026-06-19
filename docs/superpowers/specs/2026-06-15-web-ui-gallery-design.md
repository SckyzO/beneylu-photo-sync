# Design — UI web galerie (Phase 2.A)

**Date** : 2026-06-15
**Statut** : validé (brainstorming)
**Dépend de** : Phase 1 (`core` : client, sources, storage, state, naming, sync, config)
**Parent** : `docs/superpowers/specs/2026-06-15-beneylu-photo-exporter-design.md` (§ Phase 2)

## Problème

La Phase 1 livre un `core` + une CLI : on synchronise les photos en ligne de commande,
elles atterrissent dans `data/<board>/<AAAA-MM>/<label>`. Pour l'utilisateur final
non-technique, ça reste une CLI. Ce sous-projet ajoute une **interface web** au-dessus
du `core`, sans le modifier, livrée dans le runtime Docker : `docker compose up` →
galerie navigable + déclenchement de sync + configuration + cron interne.

Périmètre strict : **seulement l'UI web Docker**. Google Drive (lot B), sources
additionnelles (lot C), optimisation curseur `updatedAt` (lot D) restent hors-scope.

## Principes

- **Le `core` ne change pas.** `web/` le consomme via ses interfaces publiques
  (`BeneyluClient`, `CardboardSource`, `FilesystemStorage`, `StateStore`, `Synchronizer`).
  Aucune régression possible sur la CLI / le runtime Docker existant.
- **Rendu serveur, pas de SPA.** FastAPI + Jinja2 + un peu de JS vanilla. Zéro build front,
  cohérent avec « doc utilisateur simple ».
- **Dépendances isolées.** `fastapi`, `jinja2`, `python-multipart`, `uvicorn` sous un extra
  `web` ; la CLI reste légère (`pip install ent-exporter` n'embarque pas le serveur).

## Composants (`src/ent_exporter/web/`)

| Fichier | Responsabilité |
|---|---|
| `settings_store.py` | Lit/écrit la config persistée (`chmod 600`) ; **env > fichier** (l'env garde la priorité, non-régression). Fournit la config effective (identifiants ENT, intervalle de sync, dossiers). |
| `jobs.py` | `SyncRunner` : exécute `Synchronizer` dans un **thread de fond**, un seul run concurrent (lock), expose un statut (`idle` / `running` / dernier `SyncReport` + horodatage + erreur). |
| `scheduler.py` | `IntervalScheduler` : **thread interne** qui relance le job toutes les N heures (0 = désactivé). Remplace APScheduler (voir Décisions). |
| `gallery.py` | Parcourt le `Storage` filesystem en lecture seule → structure `board → AAAA-MM → [photos]`. Ne lit pas la base d'état (le filesystem fait foi pour l'affichage). |
| `thumbnails.py` | Génère une miniature (Pillow) à la demande, **cache disque** (`<data>/.thumbnails/`). |
| `auth.py` | Dépendance d'auth optionnelle : si `ENT_WEB_PASSWORD` défini → cookie de session signé ; sinon accès libre. |
| `app.py` | Application FastAPI : routes, montage `StaticFiles`, `Jinja2Templates`, câblage des composants. |
| `templates/` | `base.html`, `gallery.html`, `config.html`, `login.html` (Jinja2). |
| `static/` | `style.css` minimal, `app.js` (polling du statut de sync). |
| `__main__.py` | Point d'entrée `uvicorn` (lancé par le conteneur). |

## Routes

| Méthode | Chemin | Rôle |
|---|---|---|
| `GET` | `/` | Galerie : grille des photos groupées par board puis mois. |
| `GET` | `/thumb/{key:path}` | Miniature d'une photo (cache disque). |
| `GET` | `/photo/{key:path}` | Image pleine résolution (depuis le filesystem). |
| `POST` | `/sync` | Déclenche un run en tâche de fond (no-op si déjà en cours). |
| `GET` | `/api/status` | JSON `{state, last_report, last_run_at, last_error}` pour le polling. |
| `GET` | `/config` | Formulaire de configuration. |
| `POST` | `/config` | Persiste la config (`chmod 600`) ; mot de passe ENT **write-only**. |
| `GET` / `POST` | `/login`, `/logout` | Présents seulement si `ENT_WEB_PASSWORD` défini. |

`/thumb` et `/photo` valident la clé contre le `Storage` (pas de traversée de répertoire :
clé refusée si elle contient `..` ou sort de la racine).

## Flux

```
GET /            → gallery.scan(storage_root) → rend gallery.html
POST /sync       → SyncRunner.trigger()       → thread: Synchronizer(...).run()
                                                 (lock : un seul run à la fois)
app.js (1×/s)    → GET /api/status            → met à jour la bannière de statut
IntervalScheduler (thread) → SyncRunner.trigger() toutes les N h
```

La galerie lit le filesystem en lecture seule ; un run écrit via le `core` ; la galerie
reflète les nouveautés au prochain rafraîchissement de page. Idempotence et isolation
par item héritées du `core`.

## Décisions

- **Cron : thread interne, pas APScheduler.** APScheduler v4 impose un datastore +
  event broker (SQLAlchemy/asyncpg) — disproportionné pour un unique job périodique
  self-hosted. Un `threading.Thread` avec une attente interruptible (intervalle en heures,
  `0` = désactivé) couvre le besoin sans dépendance ni job store. YAGNI assumé ;
  réévaluable si un vrai planning multi-jobs apparaît.
- **Auth UI : libre par défaut, bind `127.0.0.1`.** L'UI expose des photos et stocke les
  identifiants ENT. Défaut conservateur self-hosted : pas d'auth, écoute sur `127.0.0.1`.
  **Warning au démarrage si l'hôte écoute sur `0.0.0.0`.** Durcissement optionnel :
  `ENT_WEB_PASSWORD` → page de login + cookie de session signé. Conforme à la philosophie
  OSS (ne pas changer le défaut, alerter en mode exposé, durcissement documenté & optionnel).
- **Identifiants ENT via l'UI.** La page `/config` écrit dans le fichier `chmod 600` ;
  **les variables d'env restent prioritaires** (fallback). Le mot de passe ENT n'est
  **jamais ré-affiché** (champ write-only), jamais loggé, jamais renvoyé par une route.
- **Statut live : polling.** `app.js` interroge `GET /api/status` 1×/s pendant un run.
  Trivial et robuste ; SSE/WebSocket = sur-ingénierie ici.
- **Miniatures : cache disque.** Générées à la demande (Pillow `thumbnail()`), stockées
  sous `<data>/.thumbnails/<clé>.jpg`. Le dossier `.thumbnails/` est exclu de la galerie.

## Configuration (nouvelles variables, préfixe `ENT_`)

| Variable | Rôle | Défaut |
|---|---|---|
| `ENT_WEB_HOST` | interface d'écoute | `127.0.0.1` |
| `ENT_WEB_PORT` | port | `8000` |
| `ENT_WEB_PASSWORD` | mot de passe d'accès à l'UI (optionnel) | — (auth désactivée) |
| `ENT_SYNC_INTERVAL_HOURS` | fréquence du cron interne (`0` = désactivé) | `0` |
| `ENT_CONFIG_FILE` | fichier de config persistée (`chmod 600`) | `<data>/config.json` |

Les variables Phase 1 (`ENT_LOGIN`, `ENT_PASSWORD`, `ENT_DATA_DIR`, `ENT_STATE_DB`)
restent valides et **prioritaires** sur le fichier de config.

## Gestion d'erreurs

- Échec d'un run : capturé par `SyncRunner`, exposé dans `last_error` (statut), **jamais**
  avalé silencieusement ; le thread se termine proprement, l'UI reste vivante.
- Identifiants absents/invalides au déclenchement : statut `error` avec message clair
  (« identifiants ENT manquants — voir Configuration »), pas de stacktrace nue à l'écran.
- Captcha (`CaptchaLockedError`) : message explicite « compte temporairement verrouillé ».
- Aucun `except` silencieux retournant une valeur par défaut.

## Tests (TDD, `tests/web/`)

- **`settings_store`** : écrit en `chmod 600`, relit, masque le secret, l'env est prioritaire.
- **`jobs`** : `SyncRunner` lance un faux `Synchronizer`, le lock empêche le run concurrent,
  le statut reflète `running` puis `idle` + rapport, une exception part dans `last_error`.
- **`scheduler`** : `IntervalScheduler` appelle le callback ; `0` heure = jamais lancé.
- **`gallery`** : un faux arbre de fichiers est groupé correctement ; `.thumbnails/` ignoré ;
  clé hors racine refusée.
- **`thumbnails`** : génère + met en cache (2ᵉ appel ne régénère pas).
- **`auth`** : sans `ENT_WEB_PASSWORD` accès libre ; avec, redirection `/login` puis cookie OK.
- **`app`** (`TestClient`) : `/` rend la galerie, `/sync` déclenche le runner (mocké),
  `/api/status` renvoie le JSON, `POST /config` écrit le fichier et ne renvoie pas le secret,
  traversée de répertoire refusée sur `/photo`.
- Zéro appel réseau live ; le `core` est mocké au niveau `Synchronizer`/client.

## Documentation

Une fois l'UI debout : captures d'écran dans `docs/screenshots/` (galerie, config),
remplacement des placeholders du `README.md`, sections **Utilisation (UI web)** complétées.

## Hors-scope (YAGNI)

Google Drive / runtime Actions (lot B) ; sources famille/chat/newspaper (lot C) ;
curseur `updatedAt` (lot D) ; multi-utilisateur ; édition/suppression de photos depuis l'UI ;
téléversement vers l'ENT ; notifications.
