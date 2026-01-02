"""Canonical types for Runtm: deployment state machine, enums, and API types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set


class MachineTier(str, Enum):
    """Machine size tiers for deployments.

    Tiers:
        STARTER: Cheapest option, good for simple tools and APIs (~$2/month)
                 shared-cpu-1x, 256MB RAM
        STANDARD: Medium option for most workloads (~$5/month)
                  shared-cpu-1x, 512MB RAM
        PERFORMANCE: For full-stack apps and heavier workloads (~$10/month)
                     shared-cpu-2x, 1024MB RAM

    All tiers use auto-stop to minimize costs when idle.
    """

    STARTER = "starter"
    STANDARD = "standard"
    PERFORMANCE = "performance"


@dataclass
class MachineTierSpec:
    """Specification for a machine tier."""

    tier: MachineTier
    memory_mb: int
    cpus: int
    cpu_kind: str
    description: str
    estimated_cost: str  # Monthly estimate when running 24/7


# Tier specifications - all use auto-stop
MACHINE_TIER_SPECS: Dict[MachineTier, MachineTierSpec] = {
    MachineTier.STARTER: MachineTierSpec(
        tier=MachineTier.STARTER,
        memory_mb=256,
        cpus=1,
        cpu_kind="shared",
        description="Starter: 1 shared CPU, 256MB RAM",
        estimated_cost="~$2/month (with auto-stop, much less)",
    ),
    MachineTier.STANDARD: MachineTierSpec(
        tier=MachineTier.STANDARD,
        memory_mb=512,
        cpus=1,
        cpu_kind="shared",
        description="Standard: 1 shared CPU, 512MB RAM",
        estimated_cost="~$5/month (with auto-stop, much less)",
    ),
    MachineTier.PERFORMANCE: MachineTierSpec(
        tier=MachineTier.PERFORMANCE,
        memory_mb=1024,
        cpus=2,
        cpu_kind="shared",
        description="Performance: 2 shared CPUs, 1GB RAM",
        estimated_cost="~$10/month (with auto-stop, much less)",
    ),
}


def get_tier_spec(tier: MachineTier) -> MachineTierSpec:
    """Get the specification for a machine tier.

    Args:
        tier: Machine tier

    Returns:
        MachineTierSpec with CPU/memory configuration
    """
    return MACHINE_TIER_SPECS[tier]


class DeploymentState(str, Enum):
    """Deployment lifecycle states.

    State machine:
        [*] --> queued: POST /deployments
        queued --> building: Worker picks up
        queued --> failed: Validation error
        building --> deploying: Image pushed
        building --> failed: Build error
        deploying --> ready: Health check passed
        deploying --> failed: Deploy/health error
        ready --> queued: Redeployment (new version)
        ready --> destroyed: DELETE /deployments/:id
        failed --> destroyed: DELETE /deployments/:id
        ready --> [*]
        failed --> [*]
        destroyed --> [*]
    """

    QUEUED = "queued"
    BUILDING = "building"
    DEPLOYING = "deploying"
    READY = "ready"
    FAILED = "failed"
    DESTROYED = "destroyed"


# Allowed state transitions
ALLOWED_TRANSITIONS: Dict[DeploymentState, Set[DeploymentState]] = {
    # DEPLOYING allowed from QUEUED for config-only deploys (skip build)
    DeploymentState.QUEUED: {
        DeploymentState.BUILDING,
        DeploymentState.DEPLOYING,
        DeploymentState.FAILED,
        DeploymentState.DESTROYED,
    },
    DeploymentState.BUILDING: {DeploymentState.DEPLOYING, DeploymentState.FAILED},
    DeploymentState.DEPLOYING: {DeploymentState.READY, DeploymentState.FAILED},
    DeploymentState.READY: {
        DeploymentState.QUEUED,
        DeploymentState.DESTROYED,
    },  # QUEUED for redeploy
    DeploymentState.FAILED: {DeploymentState.QUEUED, DeploymentState.DESTROYED},  # QUEUED to retry
    DeploymentState.DESTROYED: set(),  # Terminal state
}


def can_transition(from_state: DeploymentState, to_state: DeploymentState) -> bool:
    """Check if a state transition is allowed.

    Args:
        from_state: Current deployment state
        to_state: Target deployment state

    Returns:
        True if the transition is allowed, False otherwise
    """
    return to_state in ALLOWED_TRANSITIONS.get(from_state, set())


def is_terminal_state(state: DeploymentState) -> bool:
    """Check if a state is terminal (no further transitions allowed).

    Args:
        state: Deployment state to check

    Returns:
        True if the state is terminal, False otherwise
    """
    return len(ALLOWED_TRANSITIONS.get(state, set())) == 0


class LogType(str, Enum):
    """Types of deployment logs."""

    BUILD = "build"
    DEPLOY = "deploy"
    RUNTIME = "runtime"


class AuthMode(str, Enum):
    """Authentication modes."""

    SINGLE_TENANT = "single_tenant"
    MULTI_TENANT = "multi_tenant"


class ApiKeyScope(str, Enum):
    """API key permission scopes.

    Scopes control what operations an API key can perform:
    - READ: List deployments, view logs, check status
    - DEPLOY: Create and update deployments (implies READ)
    - DELETE: Destroy deployments (implies READ)
    - ADMIN: Full access including token management
    """

    READ = "read"
    DEPLOY = "deploy"
    DELETE = "delete"
    ADMIN = "admin"


# Scope hierarchy: higher scopes include lower ones
SCOPE_HIERARCHY: Dict[ApiKeyScope, Set[ApiKeyScope]] = {
    ApiKeyScope.ADMIN: {ApiKeyScope.READ, ApiKeyScope.DEPLOY, ApiKeyScope.DELETE},
    ApiKeyScope.DEPLOY: {ApiKeyScope.READ},
    ApiKeyScope.DELETE: {ApiKeyScope.READ},
    ApiKeyScope.READ: set(),
}

# Valid scope values for validation
VALID_SCOPES = frozenset(s.value for s in ApiKeyScope)


def validate_scopes(scopes: List[str]) -> List[str]:
    """Validate and normalize scopes on write.

    Args:
        scopes: List of scope strings to validate

    Returns:
        Canonical sorted list of valid scopes

    Raises:
        ValueError: If any scope is invalid
    """
    scope_set = set(scopes)
    invalid = scope_set - VALID_SCOPES
    if invalid:
        raise ValueError(f"Invalid scopes: {invalid}. Valid scopes: {sorted(VALID_SCOPES)}")
    return sorted(scope_set)  # Dedupe and sort for consistency


def has_scope(granted_scopes: Set[str], required_scope: ApiKeyScope) -> bool:
    """Check if granted scopes include the required scope.

    Respects scope hierarchy (e.g., ADMIN includes all scopes).

    Args:
        granted_scopes: Set of scope strings the key has
        required_scope: The scope required for the operation

    Returns:
        True if the required scope is granted (directly or via hierarchy)
    """
    # Check direct grant
    if required_scope.value in granted_scopes:
        return True

    # Check if ADMIN is granted (includes everything)
    if ApiKeyScope.ADMIN.value in granted_scopes:
        return True

    # Check hierarchy - if a higher scope is granted that includes this one
    for scope_str in granted_scopes:
        try:
            scope = ApiKeyScope(scope_str)
            if required_scope in SCOPE_HIERARCHY.get(scope, set()):
                return True
        except ValueError:
            continue

    return False


@dataclass
class AuthContext:
    """Authentication context for API requests.

    In single-tenant mode, only token and tenant_id are populated.
    In multi-tenant mode, all fields are populated from the API key.

    Attributes:
        token: The raw bearer token
        tenant_id: Tenant/org identifier for isolation
        principal_id: User or service account identifier
        api_key_id: The API key ID used for this request
        scopes: Set of granted scope strings
    """

    token: str
    tenant_id: str = "default"
    principal_id: str = "default"
    api_key_id: Optional[str] = None
    scopes: Set[str] = field(
        default_factory=lambda: {
            ApiKeyScope.READ.value,
            ApiKeyScope.DEPLOY.value,
            ApiKeyScope.DELETE.value,
        }
    )


@dataclass
class VolumeConfig:
    """Configuration for a persistent volume mount.

    Volumes persist data across deploys and machine restarts.
    Used for SQLite databases and other persistent storage.
    """

    name: str
    path: str
    size_gb: int = 1


@dataclass
class MachineConfig:
    """Configuration for deploying a machine to a provider.

    This is passed to the DeployProvider to create a machine.
    All deployments use auto-stop to minimize costs.
    """

    image: str
    memory_mb: int = 256
    cpus: int = 1
    cpu_kind: str = "shared"
    region: str = "iad"
    env: Dict[str, str] = field(default_factory=dict)
    health_check_path: str = "/health"
    internal_port: int = 8080
    auto_stop: bool = True  # Always enabled for cost savings
    auto_stop_timeout: str = "5m"  # Stop after 5 minutes of no traffic
    volumes: List[VolumeConfig] = field(default_factory=list)  # Persistent volumes

    @classmethod
    def from_tier(
        cls,
        tier: MachineTier,
        image: str,
        health_check_path: str = "/health",
        internal_port: int = 8080,
        region: str = "iad",
        env: Optional[Dict[str, str]] = None,
        volumes: Optional[List[VolumeConfig]] = None,
    ) -> MachineConfig:
        """Create a MachineConfig from a tier specification.

        Args:
            tier: Machine tier (starter, standard, performance)
            image: Docker image to deploy
            health_check_path: Health check endpoint
            internal_port: Internal container port
            region: Deployment region
            env: Environment variables
            volumes: Persistent volume configurations

        Returns:
            MachineConfig with tier-appropriate resources
        """
        spec = get_tier_spec(tier)
        return cls(
            image=image,
            memory_mb=spec.memory_mb,
            cpus=spec.cpus,
            cpu_kind=spec.cpu_kind,
            health_check_path=health_check_path,
            internal_port=internal_port,
            region=region,
            env=env or {},
            auto_stop=True,
            auto_stop_timeout="5m",
            volumes=volumes or [],
        )


@dataclass
class ProviderResource:
    """Resource identifiers returned by a provider after deployment.

    Stored in provider_resources table to map deployment_id to provider-specific IDs.
    """

    app_name: str
    machine_id: str
    region: str
    image_ref: str
    url: str


@dataclass
class DeploymentInfo:
    """Deployment information returned by API.

    Used for GET /v0/deployments/:id response.
    """

    deployment_id: str
    name: str
    state: DeploymentState
    url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class BuildLogEntry:
    """A single build log entry."""

    log_type: LogType
    content: str
    created_at: datetime


# Guardrails - tuned for V0
class Limits:
    """Hard limits for V0 guardrails."""

    # Artifact limits
    MAX_ARTIFACT_SIZE_BYTES: int = 20 * 1024 * 1024  # 20 MB

    # Timeout limits
    BUILD_TIMEOUT_SECONDS: int = 10 * 60  # 10 minutes
    DEPLOY_TIMEOUT_SECONDS: int = 5 * 60  # 5 minutes

    # Resource limits (defaults for starter tier)
    DEFAULT_MEMORY_MB: int = 256
    DEFAULT_CPUS: int = 1
    DEFAULT_TIER: MachineTier = MachineTier.STARTER

    # Rate limits
    MAX_DEPLOYMENTS_PER_HOUR: int = 10

    # Idempotency key TTL
    IDEMPOTENCY_KEY_TTL_HOURS: int = 24


@dataclass
class ValidationResult:
    """Result of manifest/project validation."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        """Add an error message."""
        self.errors.append(message)
        self.is_valid = False

    def add_warning(self, message: str) -> None:
        """Add a warning message."""
        self.warnings.append(message)


def create_validation_result() -> ValidationResult:
    """Create a new validation result (initially valid)."""
    return ValidationResult(is_valid=True)


@dataclass
class DnsRecord:
    """A DNS record required for custom domain setup."""

    record_type: str  # A, AAAA, CNAME
    name: str  # e.g., "@" or "www"
    value: str  # IP address or hostname


@dataclass
class CustomDomainInfo:
    """Custom domain configuration and status.

    Returned by providers when adding or checking custom domain status.
    """

    hostname: str
    configured: bool = False
    certificate_status: str = "pending"  # pending, issued, error
    dns_records: list[DnsRecord] = field(default_factory=list)
    error: Optional[str] = None
    check_url: Optional[str] = None  # URL to check certificate status
