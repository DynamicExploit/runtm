"""Tenant-scoped data access layer.

This module enforces tenant isolation on ALL database operations (reads AND writes).
It prevents common multi-tenancy security issues:
- Filter bypass attacks (where attacker passes tenant_id as filter)
- Cross-tenant data access (where attacker guesses deployment_id)
- Tenant switching attacks (where attacker changes tenant_id on update)

Security Invariants:
1. All reads are scoped to tenant_id from auth context
2. All creates set tenant_id server-side (never from user input)
3. All updates/deletes fetch via scoped query first (verify ownership)
4. list() does NOT accept tenant_id as a filter (prevents bypass)
5. Returns 404 (not 403) to prevent resource enumeration
"""

from __future__ import annotations

from typing import Generic, Optional, TypeVar

from sqlalchemy.orm import Query, Session

from runtm_api.db.models import ApiKey, Base, Deployment

T = TypeVar("T", bound=Base)

# Fields that cannot be passed as filters (security)
# Prevents filter bypass attacks like: list(tenant_id="other_tenant")
FORBIDDEN_FILTERS = frozenset({"tenant_id", "owner_id"})


class TenantRepository(Generic[T]):
    """Base repository with automatic tenant scoping on ALL operations.

    Usage:
        repo = DeploymentRepository(db, auth.tenant_id)
        deployments = repo.list()  # Always scoped to tenant
        deployment = repo.create(name="foo")  # tenant_id set server-side
    """

    def __init__(self, db: Session, tenant_id: str, model: type[T]):
        """Initialize tenant-scoped repository.

        Args:
            db: SQLAlchemy session
            tenant_id: Tenant ID from auth context (NOT from user input!)
            model: SQLAlchemy model class
        """
        self.db = db
        self.tenant_id = tenant_id
        self.model = model

    def _scoped_query(self) -> Query[T]:
        """Base query always filtered by tenant.

        This is the security boundary - all queries go through here.
        """
        return self.db.query(self.model).filter(
            self.model.tenant_id == self.tenant_id  # type: ignore
        )

    def get_by_id(self, id: str) -> Optional[T]:
        """Get by ID within tenant scope.

        Returns None if not found OR wrong tenant (prevents enumeration).
        """
        return self._scoped_query().filter(self.model.id == id).first()

    def list(self, **filters) -> list[T]:
        """List with automatic tenant scoping.

        Security: Raises ValueError if forbidden filters are passed.
        This prevents filter bypass attacks.

        Args:
            **filters: Attribute filters (cannot include tenant_id)

        Returns:
            List of entities matching filters within tenant

        Raises:
            ValueError: If forbidden filters (tenant_id, owner_id) are passed
        """
        # SECURITY: Prevent filter bypass attacks
        forbidden = set(filters.keys()) & FORBIDDEN_FILTERS
        if forbidden:
            raise ValueError(f"Cannot filter by: {forbidden}")

        query = self._scoped_query()
        for key, value in filters.items():
            if hasattr(self.model, key):
                query = query.filter(getattr(self.model, key) == value)
        return query.all()

    def create(self, **kwargs) -> T:
        """Create with tenant_id set server-side.

        SECURITY: tenant_id is ALWAYS set from auth context, never from input.
        Even if the caller passes tenant_id, it's ignored.

        Args:
            **kwargs: Entity attributes (tenant_id will be overwritten)

        Returns:
            Created entity
        """
        # Remove tenant_id if passed (we set it ourselves)
        kwargs.pop("tenant_id", None)

        entity = self.model(tenant_id=self.tenant_id, **kwargs)
        self.db.add(entity)
        self.db.flush()
        return entity

    def update(self, id: str, **kwargs) -> Optional[T]:
        """Update within tenant scope.

        Fetches via scoped query first to ensure tenant ownership.
        Returns None if not found (404 to caller, not 403).

        SECURITY: Cannot change tenant_id via update.

        Args:
            id: Entity ID
            **kwargs: Attributes to update (cannot include tenant_id)

        Returns:
            Updated entity or None if not found
        """
        entity = self.get_by_id(id)
        if not entity:
            return None

        # SECURITY: Cannot change tenant_id
        kwargs.pop("tenant_id", None)

        for key, value in kwargs.items():
            if hasattr(entity, key):
                setattr(entity, key, value)
        self.db.flush()
        return entity

    def delete(self, id: str) -> bool:
        """Delete within tenant scope.

        Fetches via scoped query first to ensure tenant ownership.
        Returns False if not found.

        Args:
            id: Entity ID

        Returns:
            True if deleted, False if not found
        """
        entity = self.get_by_id(id)
        if not entity:
            return False
        self.db.delete(entity)
        self.db.flush()
        return True


class DeploymentRepository(TenantRepository[Deployment]):
    """Deployment-specific queries with tenant isolation."""

    def __init__(self, db: Session, tenant_id: str):
        super().__init__(db, tenant_id, Deployment)

    def get_by_deployment_id(self, deployment_id: str) -> Optional[Deployment]:
        """Get deployment by human-friendly ID.

        Args:
            deployment_id: Deployment ID like "dep_abc123"

        Returns:
            Deployment or None if not found within tenant
        """
        return self._scoped_query().filter(Deployment.deployment_id == deployment_id).first()

    def get_latest_by_name(self, name: str) -> Optional[Deployment]:
        """Get latest active deployment by name.

        Args:
            name: Deployment name

        Returns:
            Latest deployment with this name or None
        """
        return (
            self._scoped_query()
            .filter(
                Deployment.name == name,
                Deployment.is_latest == True,  # noqa: E712
            )
            .first()
        )

    def list_active(self, limit: int = 100, offset: int = 0) -> list[Deployment]:
        """List active (latest version, not destroyed/failed) deployments.

        Args:
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of active deployments
        """
        return (
            self._scoped_query()
            .filter(
                Deployment.is_latest == True,  # noqa: E712
                Deployment.state.notin_(["DESTROYED", "FAILED"]),
            )
            .order_by(Deployment.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )


class ApiKeyRepository(TenantRepository[ApiKey]):
    """API key queries with tenant isolation.

    Note: This is for tenant admins managing their own keys.
    The auth lookup (by prefix/hash) is in the auth module.
    """

    def __init__(self, db: Session, tenant_id: str):
        super().__init__(db, tenant_id, ApiKey)

    def get_by_prefix_active(self, prefix: str) -> list[ApiKey]:
        """Get active (non-revoked) keys by prefix.

        Used for key lookup during authentication.

        Args:
            prefix: Key prefix (first 16 chars)

        Returns:
            List of matching non-revoked keys
        """
        return (
            self._scoped_query()
            .filter(
                ApiKey.key_prefix == prefix,
                ApiKey.is_revoked == False,  # noqa: E712
            )
            .all()
        )

    def list_for_principal(self, principal_id: str) -> list[ApiKey]:
        """List keys for a specific principal.

        Args:
            principal_id: User or service account ID

        Returns:
            List of API keys for the principal
        """
        return (
            self._scoped_query()
            .filter(ApiKey.principal_id == principal_id)
            .order_by(ApiKey.created_at.desc())
            .all()
        )

    def revoke(self, key_id: str) -> Optional[ApiKey]:
        """Revoke an API key (soft delete).

        Args:
            key_id: API key UUID

        Returns:
            Revoked key or None if not found
        """
        key = self.get_by_id(key_id)
        if not key:
            return None
        key.is_revoked = True
        self.db.flush()
        return key
