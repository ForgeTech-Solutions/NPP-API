# API Nomenclature Produits Pharmaceutiques

API REST pour la gestion de la **nomenclature nationale des produits pharmaceutiques à usage humain** (Algérie).

## Fonctionnalités

- **Système de packs** — FREE, PRO, INSTITUTIONNEL, DÉVELOPPEUR (permissions & quotas)
- **Rate limiting** — 100 req/jour, 1 000 req/mois pour le pack FREE (minuit GMT+1)
- **Inscription publique** — avec validation admin obligatoire
- **Authentification JWT** — rôles Admin / Lecteur + pack
- **Import multi-feuilles** — Nomenclature, Non Renouvelés, Retraits (Excel)
- **Recherche full-text** — DCI, nom de marque, code, laboratoire
- **CRUD complet** — création, modification, suppression logique
- **Pagination & tri** — `sort_by`, `order`, `page`, `page_size`
- **Dashboard & statistiques** — top labos, répartition par type/pays/catégorie
- **Export CSV** — avec filtres
- **Nettoyage doublons** — détection et suppression avec dry-run
- **Cache TTL** — cache en mémoire (5 min) sur les endpoints stats
- **Logging structuré** — middleware de logs HTTP + loggers par module
- **Documentation auto** — Swagger (`/docs`) et ReDoc (`/redoc`)

## Stack technique

| Composant | Technologie |
|---|---|
| Framework | FastAPI 0.115 |
| ORM | SQLAlchemy 2.0 (async) |
| BDD dev | SQLite + aiosqlite |
| BDD prod | PostgreSQL + asyncpg |
| Auth | JWT (HS256, 30 min) |
| Migrations | Alembic |
| Serveur prod | Gunicorn + UvicornWorker |
| Tests | pytest + pytest-asyncio + httpx |
| Conteneurs | Docker + Docker Compose |
| Hébergement | Render.com |

## Installation

```bash
# Cloner et entrer dans le projet
cd "API NPP"

# Créer l'environnement virtuel
python3 -m venv venv
source venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt
```

## Configuration

Copier `.env.example` vers `.env` et adapter :

```env
DATABASE_URL=sqlite+aiosqlite:///./nomenclature.db   # dev
# DATABASE_URL=postgresql+asyncpg://user:pass@host/db  # prod

SECRET_KEY=votre-cle-secrete
ADMIN_EMAIL=admin@nomenclature.dz
ADMIN_PASSWORD=Admin2025!
```

## Démarrage

```bash
# Démarrage rapide
./start.sh

# Ou manuellement
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

L'API est accessible sur `http://localhost:8000` :
- **Swagger** : http://localhost:8000/docs
- **ReDoc** : http://localhost:8000/redoc
- **Health** : http://localhost:8000/health

## Authentification

L'admin par défaut est créé au démarrage : `admin@nomenclature.dz` / `Admin2025!`

```bash
# Se connecter (OAuth2 form)
curl -X POST http://localhost:8000/auth/login \
  -d "username=admin@nomenclature.dz" \
  -d "password=Admin2025!"

# Utiliser le token
curl -H "Authorization: Bearer <TOKEN>" http://localhost:8000/medicaments
```

---

## Endpoints API

### Authentification (`/auth`)

| Méthode | Endpoint | Description | Rôle |
|---|---|---|---|
| POST | `/auth/login` | Connexion (retourne JWT) | Public |
| GET | `/auth/me` | Utilisateur courant | Auth |
| POST | `/auth/signup` | Demander un accès (public, pending approval) | Public |

### Packs & Permissions

| Pack | Cible | Recherche | Filtres avancés | DCI | Retraits | Stats | Dashboard | Export CSV | Limite |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|---|
| **FREE** | Public | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | 100/j · 1 000/mois |
| **PRO** | Pharmacies | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | Illimité |
| **INSTITUTIONNEL** | Hôpitaux | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Illimité |
| **DÉVELOPPEUR** | Éditeurs logiciels | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Illimité |

> `GET /packs` — catalogue public des packs (sans token)

### Médicaments (`/medicaments`)

| Méthode | Endpoint | Description | Pack minimum |
|---|---|---|---|
| GET | `/medicaments` | Lister (pagination, filtres, recherche `?q=`) | FREE |
| GET | `/medicaments/{id}` | Détail d’un médicament | FREE |
| GET | `/medicaments/par-dci/{dci}` | Tous les médicaments d’une DCI | PRO |
| GET | `/medicaments/export` | Export CSV avec filtres | PRO |
| GET | `/medicaments/statistiques` | Stats par labo/pays/type/catégorie | INSTITUTIONNEL |
| GET | `/medicaments/dashboard` | Dashboard enrichi (top 10, versions) | INSTITUTIONNEL |
| POST | `/medicaments` | Créer un médicament | Admin |
| PUT | `/medicaments/{id}` | Modifier un médicament | Admin |
| DELETE | `/medicaments/{id}` | Supprimer (soft delete) | Admin |

#### Filtres disponibles sur `GET /medicaments`

`q`, `dci`, `nom_marque`, `code`, `num_enregistrement`, `laboratoire`, `pays_laboratoire`, `liste`, `type`, `statut`, `categorie`, `date_initial_min`, `date_initial_max`, `version`, `sort_by`, `order`

### Import (`/import`)

| Méthode | Endpoint | Description | Rôle |
|---|---|---|---|
| POST | `/import/sheets/preview` | Prévisualiser les feuilles Excel | Admin |
| POST | `/import/nomenclature` | Importer (multi-feuilles) | Admin |
| GET | `/import/duplicates` | Détecter les doublons | Admin |
| POST | `/import/clean-duplicates` | Nettoyer les doublons (dry-run) | Admin |

### Santé

| Méthode | Endpoint | Description | Rôle |
|---|---|---|---|
| GET | `/health` | Statut API + dernière version importée | Public |
| GET | `/packs` | Catalogue des packs (fonctionnalités, limites) | Public |

### Administration (`/admin`) — Admin uniquement

| Méthode | Endpoint | Description |
|---|---|---|
| GET | `/admin/packs` | Catalogue complet des packs |
| GET | `/admin/packs/{slug}` | Détail d'un pack |
| GET | `/admin/users` | Lister les utilisateurs (filtre par pack, statut) |
| GET | `/admin/users/pending` | Inscriptions en attente de validation |
| GET | `/admin/users/{id}` | Détail d'un utilisateur |
| POST | `/admin/users` | Créer un utilisateur (approuvé immédiatement) |
| PATCH | `/admin/users/{id}` | Modifier un utilisateur (rôle, pack, statut) |
| POST | `/admin/users/{id}/approve` | Approuver une inscription en attente |
| POST | `/admin/users/{id}/pack` | Changer le pack d'un utilisateur |
| DELETE | `/admin/users/{id}` | Désactiver un utilisateur (soft delete) |
| GET | `/admin/stats` | Statistiques admin (users par pack, statut) |

---

## Import Excel multi-feuilles

Le fichier Excel contient 3 feuilles détectées automatiquement :

| Feuille | Catégorie | Description |
|---|---|---|
| Nomenclature JUIN 2025 | `NOMENCLATURE` | Médicaments actifs (5 094 lignes) |
| Non Renouvelés | `NON_RENOUVELE` | Enregistrements non renouvelés (1 905 lignes) |
| RETRAIT | `RETRAIT` | Médicaments retirés (2 296 lignes) |

```bash
# Prévisualiser
curl -X POST http://localhost:8000/import/sheets/preview \
  -H "Authorization: Bearer <TOKEN>" \
  -F "file=@nomenclature.xlsx"

# Importer toutes les feuilles
curl -X POST http://localhost:8000/import/nomenclature \
  -H "Authorization: Bearer <TOKEN>" \
  -F "file=@nomenclature.xlsx" \
  -F "version=2025-06-30"

# Importer une feuille spécifique
curl -X POST http://localhost:8000/import/nomenclature \
  -H "Authorization: Bearer <TOKEN>" \
  -F "file=@nomenclature.xlsx" \
  -F "version=2025-06-30" \
  -F "sheet_names=RETRAIT"
```

---

## Tests

```bash
# Lancer tous les tests (31 tests)
python -m pytest tests/ -v

# Par module
python -m pytest tests/test_auth.py -v          # 7 tests auth
python -m pytest tests/test_cache.py -v         # 5 tests cache
python -m pytest tests/test_import.py -v        # 4 tests import
python -m pytest tests/test_medicaments.py -v   # 15 tests CRUD/search/stats
```

---

## Structure du projet

```
app/
├── main.py                 # App FastAPI, lifespan, middleware logging
├── core/
│   ├── config.py           # Settings (pydantic-settings)
│   ├── security.py         # JWT, hashing, pack guards, rate limiter
│   ├── cache.py            # Cache TTL en mémoire
│   └── packs.py            # Définitions packs, features, limites
├── auth/
│   ├── models.py           # Modèle User (rôle, pack, quotas)
│   ├── schemas.py          # Schemas auth, PackDetail, QuotaInfo
│   ├── routes.py           # /auth/login, /auth/me, /auth/signup
│   └── jwt.py              # Création de tokens
├── admin/
│   └── routes.py           # Gestion users, packs, approbations, stats
├── medicaments/
│   ├── models.py           # Modèle Medicament (+ catégorie, retrait)
│   ├── schemas.py          # Schemas CRUD, pagination, dashboard, DCI
│   ├── routes.py           # 9 endpoints médicaments
│   └── crud.py             # Logique métier, recherche, export, stats
├── importer/
│   ├── excel_parser.py     # Parsing Excel multi-feuilles + normalisation
│   └── routes.py           # Import, preview, doublons
├── models/
│   └── import_log.py       # Modèle ImportLog
└── db/
    ├── base.py             # DeclarativeBase
    └── session.py          # Engine + SessionLocal async
tests/
├── conftest.py             # Fixtures (DB test, auth tokens)
├── test_auth.py            # Tests authentification
├── test_cache.py           # Tests cache TTL
├── test_import.py          # Tests import
└── test_medicaments.py     # Tests CRUD, recherche, stats, export
alembic/
├── env.py                  # Config Alembic async
└── versions/
    ├── 002_add_categories.py  # Migration catégorie + retrait
    └── 003_add_packs.py       # Migration packs, quotas, approbation
```

---

## Déploiement avec Docker

### Prérequis

- [Docker](https://docs.docker.com/get-docker/) ≥ 24.0
- [Docker Compose](https://docs.docker.com/compose/install/) ≥ 2.20 (inclus avec Docker Desktop)

### Démarrage rapide

```bash
# 1. Copier la configuration d'environnement
cp .env.example .env

# 2. Lancer l'API + PostgreSQL
docker compose up -d

# 3. Vérifier que tout est up
docker compose ps
```

L'API est accessible sur **http://localhost:8000** :
- Swagger : http://localhost:8000/docs
- Health : http://localhost:8000/health

### Configuration Docker

Les variables sont définies dans `.env` (ou directement dans l'environnement) :

| Variable | Défaut | Description |
|---|---|---|
| `POSTGRES_USER` | `npp` | Utilisateur PostgreSQL |
| `POSTGRES_PASSWORD` | `npp_secret` | Mot de passe PostgreSQL |
| `POSTGRES_DB` | `nomenclature` | Nom de la base |
| `SECRET_KEY` | `change-me-in-production` | Clé JWT (à changer en prod !) |
| `ADMIN_EMAIL` | `admin@nomenclature.dz` | Email admin initial |
| `ADMIN_PASSWORD` | `Admin2025!` | Mot de passe admin initial |
| `RECREATE_TABLES` | `false` | `true` pour recréer les tables au 1er lancement |
| `API_PORT` | `8000` | Port exposé sur l'hôte |
| `DEBUG` | `false` | Mode debug |

### Commandes utiles

```bash
# Démarrer (avec rebuild)
docker compose up -d --build

# Voir les logs en temps réel
docker compose logs -f api

# Arrêter
docker compose down

# Arrêter et supprimer les données (reset complet)
docker compose down -v

# Lancer les tests dans le conteneur
docker compose exec api python -m pytest tests/ -v

# Importer un fichier Excel
docker compose cp nomenclature.xlsx api:/app/
docker compose exec api python -c "print('File copied, use /import endpoint')"
```

### Architecture Docker

```
┌─────────────────────────────────────────────────┐
│                  docker compose                  │
│                                                  │
│  ┌──────────┐         ┌───────────────────────┐ │
│  │ postgres │ :5432 ← │         api           │ │
│  │ 16-alpine│         │  gunicorn + uvicorn   │ │
│  │          │         │  FastAPI on :8000      │ │
│  └──────────┘         └───────────────────────┘ │
│   volume:              exposed: ${API_PORT}:8000│
│   postgres_data                                  │
└─────────────────────────────────────────────────┘
```

### Build standalone (sans Compose)

```bash
# Build l'image
docker build -t api-nomenclature .

# Lancer avec une base externe
docker run -d --name api-npp \
  -p 8000:8000 \
  -e DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/nomenclature \
  -e SECRET_KEY=ma-cle-secrete \
  -e RECREATE_TABLES=true \
  api-nomenclature
```

---

## Déploiement sur Render

### 1. Préparer le repository

```bash
git init && git add . && git commit -m "Initial commit"
git remote add origin https://github.com/<user>/api-nomenclature.git
git push -u origin main
```

### 2. Créer la base PostgreSQL

**Render Dashboard** > **New+** > **PostgreSQL** > Plan Free > copier l'**Internal Database URL**.

### 3. Créer le Web Service

**New+** > **Web Service** > connecter le repo GitHub.

| Paramètre | Valeur |
|---|---|
| Build Command | `pip install --upgrade pip && pip install -r requirements.txt` |
| Start Command | `gunicorn -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} app.main:app` |
| Plan | Free |

### 4. Variables d'environnement

```env
DATABASE_URL=postgresql+asyncpg://...   # URL interne Render
SECRET_KEY=<clé-secrète-forte>
ADMIN_EMAIL=admin@nomenclature.dz
ADMIN_PASSWORD=<mot-de-passe-fort>
RECREATE_TABLES=true                    # uniquement au 1er déploiement
```

> Retirer `RECREATE_TABLES` après le premier déploiement et utiliser Alembic pour les migrations futures.

---

## Licence

Projet interne — Nomenclature nationale des produits pharmaceutiques.
