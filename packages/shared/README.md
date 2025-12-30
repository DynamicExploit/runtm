# runtm-shared

Canonical contracts for Runtm: manifest schema, types, errors, and ID generation.

## Contents

- `types.py` - Deployment state machine, enums, API types
- `manifest.py` - Pydantic models for `runtm.yaml` validation
- `errors.py` - Typed error hierarchy with recovery hints
- `ids.py` - Deterministic deployment ID generation
- `storage/base.py` - Abstract storage interface

## Usage

```python
from runtm_shared.types import DeploymentState, can_transition
from runtm_shared.manifest import Manifest
from runtm_shared.errors import RuntmError, ManifestValidationError
from runtm_shared.ids import generate_deployment_id
from runtm_shared.storage.base import ArtifactStore
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

