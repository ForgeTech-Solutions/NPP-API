# API Nomenclature Produits Pharmaceutiques

API REST pour la gestion de la **nomenclature nationale des produits pharmaceutiques à usage humain** (Algérie).

## Fonctionnalités

- **Système de packs** — FREE, PRO, INSTITUTIONNEL, DÉVELOPPEUR (permissions & quotas)
- **Rate limiting** — 100 req/jour, 1 000 req/mois pour le pack FREE (minuit GMT+1)
- **Inscription publique** — avec validation admin obligatoire
- **Authentification JWT** — rôles Admin / Lecteur + pack
- **Clés API** — authentification machine-to-machine (`X-API-Key`), limites par pack
- **Emails transactionnels** — Microsoft 365 Graph API (inscription, approbation, reset password…)
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
| Auth | JWT (HS256, 30 min) + API Keys (SHA-256) |
| Email | Microsoft 365 Graph API (MSAL) |
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

# Microsoft 365 Email (optionnel — désactivé par défaut)
MICROSOFT_TENANT_ID=
MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=
MAIL_FROM=noreply@votredomaine.com
MAIL_FROM_NAME=NPP — Nomenclature Pharmaceutique
MAIL_ENABLED=false
ADMIN_NOTIFICATION_EMAIL=admin@votredomaine.com
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
| PATCH | `/auth/me` | Modifier profil (nom, tel, organisation) | Auth |
| POST | `/auth/me/password` | Changer mot de passe | Auth |
| GET | `/auth/me/stats` | Statistiques d'utilisation | Auth |
| GET | `/auth/me/pack` | Détail de mon pack | Auth |
| POST | `/auth/me/delete` | Supprimer mon compte | Auth |
| POST | `/auth/signup` | Demander un accès (pending approval) | Public |
| GET | `/auth/me/api-keys` | Lister mes clés API | Auth |
| POST | `/auth/me/api-keys` | Créer une clé API | Auth |
| DELETE | `/auth/me/api-keys/{id}` | Révoquer une clé API | Auth |

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
| POST | `/admin/users/{id}/reset-password` | Réinitialiser mot de passe + envoi email |
| GET | `/admin/stats` | Statistiques admin (users par pack, statut) |
| GET | `/admin/api-keys` | Lister toutes les clés API |
| GET | `/admin/api-keys/{id}` | Détail d'une clé API |
| PATCH | `/admin/api-keys/{id}` | Activer/désactiver une clé API |
| DELETE | `/admin/api-keys/{id}` | Supprimer une clé API |
| GET | `/admin/users/{id}/api-keys` | Clés API d'un utilisateur |
| GET | `/admin/email/status` | Statut de la configuration email M365 |
| POST | `/admin/email/test` | Envoyer un email de test |
| POST | `/admin/email/send` | Envoyer un email personnalisé |

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
│   ├── security.py         # JWT + API Key auth, pack guards, rate limiter
│   ├── email.py            # Service email Microsoft 365 Graph API (MSAL)
│   ├── cache.py            # Cache TTL en mémoire
│   └── packs.py            # Définitions packs, features, limites, API key limits
├── templates/
│   └── email/              # Templates HTML emails transactionnels (9 templates)
├── auth/
│   ├── models.py           # Modèle User (rôle, pack, quotas)
│   ├── schemas.py          # Schemas auth, PackDetail, QuotaInfo
│   ├── routes.py           # /auth/login, /auth/me, /auth/signup, /auth/me/api-keys
│   └── jwt.py              # Création de tokens
├── admin/
│   └── routes.py           # Gestion users, packs, approbations, stats, email, API keys
├── medicaments/
│   ├── models.py           # Modèle Medicament (+ catégorie, retrait)
│   ├── schemas.py          # Schemas CRUD, pagination, dashboard, DCI
│   ├── routes.py           # 9 endpoints médicaments
│   └── crud.py             # Logique métier, recherche, export, stats
├── importer/
│   ├── excel_parser.py     # Parsing Excel multi-feuilles + normalisation
│   └── routes.py           # Import, preview, doublons
├── models/
│   ├── import_log.py       # Modèle ImportLog
│   ├── api_key.py          # Modèle ApiKey (SHA-256, usage tracking)
│   └── service_meta.py     # Métadonnées service (first_deployed_at)
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
| `DOCS_USERNAME` | `admin` | HTTP Basic Auth pour /docs, /redoc |
| `DOCS_PASSWORD` | `docs2025!` | Mot de passe protège la doc |
| `ROOT_PATH` | `/v1` | Préfixe reverse proxy (nginx) |
| `MICROSOFT_TENANT_ID` | _(vide)_ | Tenant ID Azure Entra ID |
| `MICROSOFT_CLIENT_ID` | _(vide)_ | Client ID de l'App Registration |
| `MICROSOFT_CLIENT_SECRET` | _(vide)_ | Client Secret |
| `MAIL_FROM` | _(vide)_ | Adresse d'envoi (`noreply@domaine.com`) |
| `MAIL_FROM_NAME` | `NPP — Nomenclature Pharmaceutique` | Nom affiché comme expéditeur |
| `MAIL_ENABLED` | `false` | Activer l'envoi d'emails |
| `ADMIN_NOTIFICATION_EMAIL` | _(vide)_ | Email recevant les notifications admin |

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

## Emails transactionnels (Microsoft 365)

L'API envoie des emails automatiques via **Microsoft Graph API** pour les événements suivants :

| Événement | Destinataire | Template |
|---|---|---|
| Inscription publique | Utilisateur | `signup_confirmation` |
| Nouvelle inscription | Admin | `admin_new_signup` |
| Compte approuvé (avec mot de passe) | Utilisateur | `account_approved` |
| Compte désactivé/rejeté | Utilisateur | `account_rejected` |
| Changement de mot de passe | Utilisateur | `password_changed` |
| Réinitialisation mot de passe (admin) | Utilisateur | `password_reset` |
| Création de clé API | Utilisateur | `api_key_created` |
| Changement de pack | Utilisateur | `pack_changed` |

### Configuration Microsoft Entra ID

1. Aller sur [portal.azure.com](https://portal.azure.com) → **Microsoft Entra ID** → **App Registrations**
2. **New Registration** → nom : `NPP-API-Email` → type : `Accounts in this organizational directory only`
3. **API Permissions** → **Add** → **Microsoft Graph** → **Application** → `Mail.Send` → **Grant admin consent**
4. **Certificates & secrets** → **New client secret** → copier la valeur
5. Copier `Tenant ID`, `Application (Client) ID` et `Client Secret Value`
6. Configurer dans `.env` :

```env
MICROSOFT_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
MICROSOFT_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
MICROSOFT_CLIENT_SECRET=votre-secret
MAIL_FROM=noreply@votredomaine.com
MAIL_ENABLED=true
ADMIN_NOTIFICATION_EMAIL=admin@votredomaine.com
```

> **Important** : `MAIL_FROM` doit être une boîte aux lettres existante dans votre tenant Microsoft 365.

### Tester la configuration

```bash
# Vérifier le statut
curl -H "Authorization: Bearer <ADMIN_TOKEN>" \
  https://votre-api.com/v1/admin/email/status

# Envoyer un email de test
curl -X POST -H "Authorization: Bearer <ADMIN_TOKEN>" \
  "https://votre-api.com/v1/admin/email/test?to_email=votre@email.com"
```

---

## Clés API (Machine-to-Machine)

En plus du JWT, l'API supporte l'authentification par clé API via l'en-tête `X-API-Key`.

| Pack | Nombre max de clés |
|---|---|
| FREE | 1 |
| PRO | 3 |
| INSTITUTIONNEL | 5 |
| DÉVELOPPEUR | 10 |

```bash
# Créer une clé API (authentifié JWT)
curl -X POST -H "Authorization: Bearer <TOKEN>" \
  "https://votre-api.com/v1/auth/me/api-keys?name=Mon+App"

# Utiliser la clé API
curl -H "X-API-Key: npp_xxxxxxxxxxxxxxxx" \
  https://votre-api.com/v1/medicaments
```

---

## Licence

Projet interne — Nomenclature nationale des produits pharmaceutiques.
