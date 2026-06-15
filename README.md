# 📸 ent_exporter

Récupère **automatiquement les photos** que l'école publie sur l'ENT
[Beneylu School](https://www.ent-ecole.fr) (« le cartable » / les tableaux de la classe),
et les range sur ton ordinateur ou ton cloud — sans avoir à les télécharger une par une.

> 🟢 Premier lancement : récupère **tout l'historique**.
> 🔁 Lancements suivants : récupère **seulement les nouvelles photos**.

## Comment ça marche

```mermaid
flowchart LR
    A["👨‍👩‍👧 Ton compte ENT<br/>ent-ecole.fr"] -->|connexion sécurisée| B["⚙️ ent_exporter"]
    B -->|lit les tableaux<br/>de la classe| C["🖼️ Photos publiées<br/>par l'école"]
    C -->|télécharge<br/>les nouveautés| D["📁 Tes photos<br/>rangées par date"]
```

L'outil se connecte avec **tes identifiants ENT**, parcourt les tableaux de la classe,
et télécharge les photos qu'il ne possède pas encore. Tes identifiants restent **chez
toi** ; rien n'est envoyé ailleurs que vers l'ENT lui-même.

## Installation (Docker)

```bash
git clone <repo> && cd ent_exporter
cp .env.example .env   # puis renseigne ENT_LOGIN / ENT_PASSWORD
docker compose -f runtimes/docker/docker-compose.yml run --rm ent-exporter sync
```

## Configuration

| Variable | Rôle | Défaut |
|---|---|---|
| `ENT_LOGIN` | identifiant ENT | — |
| `ENT_PASSWORD` | mot de passe ENT | — |
| `ENT_DATA_DIR` | dossier des photos | `./data` |

## Utilisation

```bash
ent-exporter login-test   # vérifie la connexion
ent-exporter list-boards  # liste les tableaux
ent-exporter sync         # télécharge les nouvelles photos
```

## Captures d'écran

> ⏳ _À venir avec l'interface web (v1)._
>
> <!-- ![Page de connexion](docs/screenshots/login.png) -->
> <!-- ![Galerie des photos](docs/screenshots/gallery.png) -->

## Vie privée & sécurité

- Tes identifiants ENT ne servent qu'à te connecter à `ent-ecole.fr`, **jamais partagés**.
- Conçu pour un **usage familial / self-hosted** : une installation = ton compte.
- Le code est ouvert et vérifiable.

---

📄 Détails techniques : [`CLAUDE.md`](CLAUDE.md) ·
[design](docs/superpowers/specs/2026-06-15-beneylu-photo-exporter-design.md)
