"""
Microsoft 365 Email Service — Graph API (Client Credentials Flow).

Sends transactional emails via Microsoft Graph API using MSAL
for OAuth2 client credentials authentication.
"""
import logging
from pathlib import Path
from typing import Optional

import httpx
import msal

from app.core.config import settings

logger = logging.getLogger("nomenclature.email")

# ── MSAL confidential‐client (singleton) ──────────────────────────────────
_msal_app: Optional[msal.ConfidentialClientApplication] = None


def _get_msal_app() -> msal.ConfidentialClientApplication:
    """Lazy‐init MSAL confidential‐client application."""
    global _msal_app
    if _msal_app is None:
        _msal_app = msal.ConfidentialClientApplication(
            client_id=settings.MICROSOFT_CLIENT_ID,
            client_credential=settings.MICROSOFT_CLIENT_SECRET,
            authority=f"https://login.microsoftonline.com/{settings.MICROSOFT_TENANT_ID}",
        )
    return _msal_app


def _acquire_token() -> str:
    """Acquire an access token for Microsoft Graph (Mail.Send scope)."""
    app = _get_msal_app()
    result = app.acquire_token_for_client(
        scopes=["https://graph.microsoft.com/.default"],
    )
    if "access_token" not in result:
        error = result.get("error_description", result.get("error", "unknown"))
        raise RuntimeError(f"Impossible d'obtenir un token Graph API : {error}")
    return result["access_token"]


# ── Template loader ────────────────────────────────────────────────────────

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "email"


def _load_template(template_name: str, **kwargs) -> str:
    """Load an HTML template and substitute {placeholders}."""
    path = TEMPLATES_DIR / f"{template_name}.html"
    if not path.exists():
        logger.error(f"Template introuvable : {path}")
        raise FileNotFoundError(f"Email template '{template_name}' introuvable")
    html = path.read_text(encoding="utf-8")
    for key, value in kwargs.items():
        html = html.replace(f"{{{{{key}}}}}", str(value))
    return html


# ── Core send function ─────────────────────────────────────────────────────

async def send_email(
    to_email: str,
    subject: str,
    html_body: str,
    to_name: str = "",
) -> bool:
    """
    Send an email via Microsoft Graph API.

    Returns True on success, False on failure (never raises — logs errors).
    """
    if not settings.MAIL_ENABLED:
        logger.info(f"[EMAIL DÉSACTIVÉ] → {to_email} | Sujet : {subject}")
        return False

    if not all([
        settings.MICROSOFT_TENANT_ID,
        settings.MICROSOFT_CLIENT_ID,
        settings.MICROSOFT_CLIENT_SECRET,
        settings.MAIL_FROM,
    ]):
        logger.warning("Configuration email Microsoft 365 incomplète — email non envoyé")
        return False

    try:
        token = _acquire_token()
    except RuntimeError as e:
        logger.error(f"Erreur d'authentification Graph API : {e}")
        return False

    url = f"https://graph.microsoft.com/v1.0/users/{settings.MAIL_FROM}/sendMail"

    payload = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": html_body,
            },
            "from": {
                "emailAddress": {
                    "address": settings.MAIL_FROM,
                    "name": settings.MAIL_FROM_NAME,
                }
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "address": to_email,
                        "name": to_name or to_email,
                    }
                }
            ],
        },
        "saveToSentItems": "true",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )
        if resp.status_code == 202:
            logger.info(f"✓ Email envoyé → {to_email} | Sujet : {subject}")
            return True
        else:
            logger.error(
                f"✗ Erreur Graph API ({resp.status_code}) → {to_email} : {resp.text[:500]}"
            )
            return False
    except Exception as e:
        logger.error(f"✗ Erreur réseau envoi email → {to_email} : {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════
#  HIGH-LEVEL SENDERS (one per use case)
# ══════════════════════════════════════════════════════════════════════════

async def send_signup_confirmation(
    to_email: str,
    full_name: str,
    pack: str,
    organisation: str = "",
) -> bool:
    """Email envoyé à l'utilisateur après inscription (en attente d'approbation)."""
    html = _load_template(
        "signup_confirmation",
        full_name=full_name,
        email=to_email,
        pack=pack,
        organisation=organisation or "—",
        app_name=settings.APP_NAME,
    )
    return await send_email(
        to_email=to_email,
        subject=f"{settings.APP_NAME} — Demande d'accès enregistrée",
        html_body=html,
        to_name=full_name,
    )


async def send_admin_new_signup_notification(
    user_email: str,
    full_name: str,
    pack: str,
    organisation: str = "",
    message: str = "",
) -> bool:
    """Notification à l'admin quand un nouvel utilisateur s'inscrit."""
    if not settings.ADMIN_NOTIFICATION_EMAIL:
        return False
    html = _load_template(
        "admin_new_signup",
        full_name=full_name,
        email=user_email,
        pack=pack,
        organisation=organisation or "—",
        message=message or "—",
        app_name=settings.APP_NAME,
    )
    return await send_email(
        to_email=settings.ADMIN_NOTIFICATION_EMAIL,
        subject=f"[NPP Admin] Nouvelle demande d'accès — {full_name}",
        html_body=html,
        to_name="Administrateur NPP",
    )


async def send_account_approved(
    to_email: str,
    full_name: str,
    pack: str,
    password: str,
) -> bool:
    """Email envoyé quand l'admin approuve un compte (inclut le mot de passe)."""
    html = _load_template(
        "account_approved",
        full_name=full_name,
        email=to_email,
        pack=pack,
        password=password,
        app_name=settings.APP_NAME,
    )
    return await send_email(
        to_email=to_email,
        subject=f"{settings.APP_NAME} — Votre accès a été approuvé ✓",
        html_body=html,
        to_name=full_name,
    )


async def send_account_rejected(
    to_email: str,
    full_name: str,
    reason: str = "",
) -> bool:
    """Email envoyé quand l'admin désactive/rejette un compte."""
    html = _load_template(
        "account_rejected",
        full_name=full_name,
        email=to_email,
        reason=reason or "Aucune raison spécifiée.",
        app_name=settings.APP_NAME,
    )
    return await send_email(
        to_email=to_email,
        subject=f"{settings.APP_NAME} — Mise à jour de votre compte",
        html_body=html,
        to_name=full_name,
    )


async def send_password_changed(
    to_email: str,
    full_name: str,
) -> bool:
    """Confirmation de changement de mot de passe."""
    html = _load_template(
        "password_changed",
        full_name=full_name,
        email=to_email,
        app_name=settings.APP_NAME,
    )
    return await send_email(
        to_email=to_email,
        subject=f"{settings.APP_NAME} — Mot de passe modifié",
        html_body=html,
        to_name=full_name,
    )


async def send_password_reset(
    to_email: str,
    full_name: str,
    new_password: str,
) -> bool:
    """Email de réinitialisation de mot de passe (avec nouveau mot de passe)."""
    html = _load_template(
        "password_reset",
        full_name=full_name,
        email=to_email,
        new_password=new_password,
        app_name=settings.APP_NAME,
    )
    return await send_email(
        to_email=to_email,
        subject=f"{settings.APP_NAME} — Réinitialisation de votre mot de passe",
        html_body=html,
        to_name=full_name,
    )


async def send_api_key_created(
    to_email: str,
    full_name: str,
    key_name: str,
    key_prefix: str,
) -> bool:
    """Notification : nouvelle clé API créée."""
    html = _load_template(
        "api_key_created",
        full_name=full_name,
        key_name=key_name,
        key_prefix=key_prefix,
        app_name=settings.APP_NAME,
    )
    return await send_email(
        to_email=to_email,
        subject=f"{settings.APP_NAME} — Nouvelle clé API créée",
        html_body=html,
        to_name=full_name,
    )


async def send_pack_changed(
    to_email: str,
    full_name: str,
    old_pack: str,
    new_pack: str,
) -> bool:
    """Notification de changement de pack."""
    html = _load_template(
        "pack_changed",
        full_name=full_name,
        old_pack=old_pack,
        new_pack=new_pack,
        app_name=settings.APP_NAME,
    )
    return await send_email(
        to_email=to_email,
        subject=f"{settings.APP_NAME} — Pack mis à jour : {new_pack}",
        html_body=html,
        to_name=full_name,
    )


async def send_test_email(to_email: str) -> bool:
    """Email de test pour vérifier la configuration."""
    html = _load_template(
        "test_email",
        app_name=settings.APP_NAME,
        to_email=to_email,
    )
    return await send_email(
        to_email=to_email,
        subject=f"{settings.APP_NAME} — Email de test ✓",
        html_body=html,
    )
