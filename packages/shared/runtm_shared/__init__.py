"""Runtm shared contracts: types, manifest schema, errors, and ID generation."""

# Telemetry module is available as runtm_shared.telemetry
# Import specific items with: from runtm_shared.telemetry import TelemetryService

from runtm_shared.discovery import (
    ApiDiscovery,
    AppDiscovery,
    GeneratedInfo,
)
from runtm_shared.env import ensure_env_loaded, find_project_root, load_env_file
from runtm_shared.errors import (
    ArtifactError,
    ArtifactNotFoundError,
    ArtifactTooLargeError,
    AuthError,
    BuildError,
    BuildTimeoutError,
    DeploymentError,
    DeploymentNotFoundError,
    DeploymentStateError,
    DeployTimeoutError,
    DockerfileNotFoundError,
    FlyError,
    HealthCheckError,
    InvalidTokenError,
    ManifestError,
    ManifestNotFoundError,
    ManifestValidationError,
    ProviderError,
    ProviderNotConfiguredError,
    RateLimitError,
    RuntmError,
    SecretsNotSupportedError,
    StorageError,
    StorageReadError,
    StorageWriteError,
)
from runtm_shared.ids import (
    generate_artifact_key,
    generate_build_context_key,
    generate_deployment_id,
    generate_idempotency_key,
    is_valid_deployment_id,
    parse_deployment_id,
)
from runtm_shared.lockfiles import (
    LockfileStatus,
    check_all_lockfiles,
    check_lockfile,
    check_node_lockfile,
    check_python_lockfile,
    fix_lockfile,
)
from runtm_shared.manifest import (
    Connection,
    EnvVar,
    EnvVarType,
    Manifest,
    Policy,
    PolicyMode,
)
from runtm_shared.requests import (
    RequestedChanges,
    RequestedConnection,
    RequestedEnvVar,
    RequestsFile,
)
from runtm_shared.storage.base import ArtifactStore

# NOTE: We intentionally do NOT auto-load .env when runtm_shared is imported.
# The CLI runs in user projects and shouldn't load the monorepo's .env.
# API and Worker should call ensure_env_loaded() explicitly at startup.
from runtm_shared.types import (
    ALLOWED_TRANSITIONS,
    MACHINE_TIER_SPECS,
    AuthContext,
    AuthMode,
    BuildLogEntry,
    CustomDomainInfo,
    DeploymentInfo,
    DeploymentState,
    DnsRecord,
    Limits,
    LogType,
    MachineConfig,
    MachineTier,
    MachineTierSpec,
    ProviderResource,
    ValidationResult,
    can_transition,
    create_validation_result,
    get_tier_spec,
    is_terminal_state,
)
from runtm_shared.urls import (
    construct_deployment_url,
    get_base_domain,
    get_subdomain_for_app,
)

__all__ = [
    # Types
    "DeploymentState",
    "ALLOWED_TRANSITIONS",
    "can_transition",
    "is_terminal_state",
    "LogType",
    "AuthMode",
    "AuthContext",
    "MachineConfig",
    "MachineTier",
    "MachineTierSpec",
    "MACHINE_TIER_SPECS",
    "get_tier_spec",
    "ProviderResource",
    "DeploymentInfo",
    "BuildLogEntry",
    "Limits",
    "ValidationResult",
    "create_validation_result",
    "DnsRecord",
    "CustomDomainInfo",
    # Manifest
    "Manifest",
    "EnvVar",
    "EnvVarType",
    "Connection",
    "Policy",
    "PolicyMode",
    # Errors
    "RuntmError",
    "ManifestError",
    "ManifestNotFoundError",
    "ManifestValidationError",
    "SecretsNotSupportedError",
    "ArtifactError",
    "ArtifactTooLargeError",
    "ArtifactNotFoundError",
    "DockerfileNotFoundError",
    "DeploymentError",
    "DeploymentNotFoundError",
    "DeploymentStateError",
    "BuildError",
    "BuildTimeoutError",
    "DeployTimeoutError",
    "HealthCheckError",
    "AuthError",
    "InvalidTokenError",
    "RateLimitError",
    "ProviderError",
    "FlyError",
    "ProviderNotConfiguredError",
    "StorageError",
    "StorageWriteError",
    "StorageReadError",
    # IDs
    "generate_deployment_id",
    "generate_idempotency_key",
    "is_valid_deployment_id",
    "parse_deployment_id",
    "generate_artifact_key",
    "generate_build_context_key",
    # Storage
    "ArtifactStore",
    # Environment
    "ensure_env_loaded",
    "load_env_file",
    "find_project_root",
    # URLs
    "construct_deployment_url",
    "get_base_domain",
    "get_subdomain_for_app",
    # Lockfiles
    "LockfileStatus",
    "check_lockfile",
    "check_all_lockfiles",
    "check_node_lockfile",
    "check_python_lockfile",
    "fix_lockfile",
    # Discovery
    "ApiDiscovery",
    "AppDiscovery",
    "GeneratedInfo",
    # Requests
    "RequestsFile",
    "RequestedChanges",
    "RequestedEnvVar",
    "RequestedConnection",
]
