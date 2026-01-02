"""Current user endpoint for CLI token validation.

This endpoint returns information about the authenticated user/principal.
Used by `runtm login` to validate tokens and by `runtm doctor` to check auth status.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from runtm_api.auth.token import get_auth_context
from runtm_api.db.models import ApiKey
from runtm_api.db.session import get_db
from runtm_shared.types import AuthContext

router = APIRouter(prefix="/v1", tags=["auth"])


class MeResponse(BaseModel):
    """Response for GET /v1/me endpoint."""

    # Core identity
    tenant_id: str
    principal_id: str

    # API key info (if using API key auth)
    api_key_id: Optional[str] = None
    api_key_name: Optional[str] = None

    # Permissions
    scopes: list[str]

    # Human-friendly display (for CLI)
    # In multi-tenant mode with Cloud Backend, these come from the Cloud Backend
    # In single-tenant mode, these are derived from tenant/principal IDs
    email: Optional[str] = None
    org_name: Optional[str] = None


@router.get("/me", response_model=MeResponse)
async def get_current_user(
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> MeResponse:
    """Return information about the authenticated user.

    This endpoint is used by:
    - `runtm login` to validate tokens after entry
    - `runtm doctor` to show current auth status

    Returns:
        MeResponse with tenant, principal, and key info
    """
    api_key_name: Optional[str] = None

    # Try to get API key name if we have an api_key_id
    if auth.api_key_id:
        try:
            api_key = db.query(ApiKey).filter(ApiKey.id == auth.api_key_id).first()
            if api_key:
                api_key_name = api_key.name
        except Exception:
            pass  # Ignore lookup errors

    # Derive email/org from principal_id/tenant_id
    # In multi-tenant mode with Cloud Backend integration, these would be
    # enriched with actual user data. For now, use the IDs as placeholders.
    if "@" in auth.principal_id:
        # Looks like an email
        email = auth.principal_id
    elif auth.principal_id == "default" and auth.tenant_id == "default":
        # Single-tenant mode - show friendly message
        email = "Local Developer (single-tenant mode)"
    else:
        # Multi-tenant but no email - show principal_id
        email = auth.principal_id

    org_name = auth.tenant_id if auth.tenant_id != "default" else None

    return MeResponse(
        tenant_id=auth.tenant_id,
        principal_id=auth.principal_id,
        api_key_id=auth.api_key_id,
        api_key_name=api_key_name,
        scopes=list(auth.scopes),
        email=email,
        org_name=org_name,
    )
