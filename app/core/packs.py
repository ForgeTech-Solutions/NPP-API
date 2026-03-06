"""Pack definitions, feature gates and rate limits."""
from typing import Optional


# ── Rate limits per pack ───────────────────────────────────────────────────
# None = unlimited
PACK_LIMITS: dict[str, dict] = {
    "FREE": {
        "requests_per_day": 100,
        "requests_per_month": 1000,
    },
    "PRO": {
        "requests_per_day": None,
        "requests_per_month": None,
    },
    "INSTITUTIONNEL": {
        "requests_per_day": None,
        "requests_per_month": None,
    },
    "DEVELOPPEUR": {
        "requests_per_day": None,
        "requests_per_month": None,
    },
}

# ── Feature gates per pack ─────────────────────────────────────────────────
# Maps feature_key → list of packs that have access
PACK_FEATURES: dict[str, list[str]] = {
    "search_basic":            ["FREE", "PRO", "INSTITUTIONNEL", "DEVELOPPEUR"],
    "medicament_detail":       ["FREE", "PRO", "INSTITUTIONNEL", "DEVELOPPEUR"],
    "filters_advanced":        ["PRO", "INSTITUTIONNEL", "DEVELOPPEUR"],
    "group_by_dci":            ["PRO", "INSTITUTIONNEL", "DEVELOPPEUR"],
    "status_enregistrement":   ["PRO", "INSTITUTIONNEL", "DEVELOPPEUR"],
    "retraits_non_renouveles": ["PRO", "INSTITUTIONNEL", "DEVELOPPEUR"],
    "statistiques":            ["INSTITUTIONNEL", "DEVELOPPEUR"],
    "dashboard":               ["INSTITUTIONNEL", "DEVELOPPEUR"],
    "export_csv":              ["PRO", "INSTITUTIONNEL", "DEVELOPPEUR"],
}

# ── Human-readable catalog ────────────────────────────────────────────────
PACK_CATALOG: dict[str, dict] = {
    "FREE": {
        "name": "Gratuit",
        "slug": "FREE",
        "target": "Accès public",
        "description": "Accès limité pour découvrir la nomenclature.",
        "features": [
            "Recherche basique (DCI, nom, code)",
            "Fiche médicament",
            "100 requêtes/jour · 1 000 requêtes/mois",
        ],
        "limitations": [
            "Sans filtres avancés",
            "Sans export CSV",
            "Sans statistiques ni dashboard",
        ],
        "rate_limit_day": 100,
        "rate_limit_month": 1000,
        "requires_approval": True,
    },
    "PRO": {
        "name": "Pro",
        "slug": "PRO",
        "target": "Pharmacies & Grossistes",
        "description": "Officines et grossistes répartiteurs.",
        "features": [
            "Recherche par DCI, marque ou code AMM",
            "Historique des retraits et non-renouvellements",
            "Export CSV pour la gestion de stock",
            "Intégration logiciel de gestion",
            "Requêtes illimitées",
        ],
        "limitations": [],
        "rate_limit_day": None,
        "rate_limit_month": None,
        "requires_approval": True,
    },
    "INSTITUTIONNEL": {
        "name": "Institutionnel",
        "slug": "INSTITUTIONNEL",
        "target": "Établissements de santé",
        "description": "Hôpitaux publics, cliniques privées et structures sanitaires.",
        "features": [
            "Accès illimité à la nomenclature nationale",
            "Consultation en temps réel des disponibilités",
            "Vérification des statuts d'enregistrement",
            "Statistiques et dashboard enrichi",
            "Données certifiées MSPRH",
            "Requêtes illimitées",
        ],
        "limitations": [],
        "rate_limit_day": None,
        "rate_limit_month": None,
        "requires_approval": True,
    },
    "DEVELOPPEUR": {
        "name": "Développeur",
        "slug": "DEVELOPPEUR",
        "target": "Éditeurs logiciels",
        "description": "Applications santé, systèmes HIS et plateformes de prescription.",
        "features": [
            "API RESTful JSON complète",
            "Documentation Swagger / ReDoc",
            "Support de tous les filtres et exports",
            "Statistiques et dashboard enrichi",
            "SLA & support technique dédié",
            "Mises à jour automatiques des données",
            "Requêtes illimitées",
        ],
        "limitations": [],
        "rate_limit_day": None,
        "rate_limit_month": None,
        "requires_approval": True,
    },
}


def get_pack_info(pack: str) -> dict:
    """Return catalog info for a given pack slug."""
    return PACK_CATALOG.get(pack, PACK_CATALOG["FREE"])


def has_feature(pack: str, feature_key: str) -> bool:
    """Return True if the pack has access to the given feature."""
    return pack in PACK_FEATURES.get(feature_key, [])


def get_rate_limit(pack: str) -> dict:
    """Return rate limit config for a pack."""
    return PACK_LIMITS.get(pack, PACK_LIMITS["FREE"])


# ── API key limits per pack ────────────────────────────────────────────────
API_KEY_LIMITS: dict[str, int] = {
    "FREE": 1,
    "PRO": 3,
    "INSTITUTIONNEL": 5,
    "DEVELOPPEUR": 10,
}
