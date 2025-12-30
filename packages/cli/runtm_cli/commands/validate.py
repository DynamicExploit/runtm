"""Validate command - local project validation."""

from __future__ import annotations

import ast
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import typer
from rich.console import Console

from runtm_shared import Limits, Manifest, create_validation_result

console = Console()


def validate_project(path: Path) -> tuple[bool, list[str], list[str]]:
    """Validate a project before deployment.

    Args:
        path: Path to project directory

    Returns:
        Tuple of (is_valid, errors, warnings)
    """
    result = create_validation_result()
    manifest = None

    # Check runtm.yaml exists
    manifest_path = path / "runtm.yaml"
    if not manifest_path.exists():
        result.add_error("Missing runtm.yaml - run `runtm init backend-service`, `runtm init static-site`, or `runtm init web-app`")
    else:
        # Validate manifest
        try:
            manifest = Manifest.from_file(manifest_path)
            
            # Validate health configuration
            health_errors, health_warnings = validate_health_config(manifest)
            for error in health_errors:
                result.add_error(error)
            for warning in health_warnings:
                result.add_warning(warning)
        except Exception as e:
            result.add_error(f"Invalid runtm.yaml: {e}")

    # Check Dockerfile exists
    dockerfile_path = path / "Dockerfile"
    if not dockerfile_path.exists():
        result.add_error("Missing Dockerfile")

    # Check artifact size
    total_size = 0
    file_count = 0
    exclude_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv", ".next", "out"}

    for item in path.rglob("*"):
        # Skip excluded directories
        if any(excluded in item.parts for excluded in exclude_dirs):
            continue
        if item.is_file():
            total_size += item.stat().st_size
            file_count += 1

    if total_size > Limits.MAX_ARTIFACT_SIZE_BYTES:
        size_mb = total_size / (1024 * 1024)
        limit_mb = Limits.MAX_ARTIFACT_SIZE_BYTES / (1024 * 1024)
        result.add_error(
            f"Project too large: {size_mb:.1f} MB > {limit_mb:.0f} MB limit. "
            "Remove large files or add them to .gitignore"
        )

    # Check for common issues
    if (path / ".env").exists():
        result.add_warning(".env file found - it will be excluded from deployment")

    # Check for discovery metadata
    discovery_path = path / "runtm.discovery.yaml"
    if not discovery_path.exists():
        result.add_warning(
            "No runtm.discovery.yaml found. "
            "Add app metadata for better discoverability in the dashboard."
        )
    else:
        # Check if discovery file has unfilled TODO placeholders
        try:
            discovery_content = discovery_path.read_text()
            if "# TODO:" in discovery_content or "TODO:" in discovery_content:
                result.add_warning(
                    "runtm.discovery.yaml has unfilled TODO placeholders. "
                    "Fill them in before deploying for better app discoverability."
                )
        except Exception:
            pass  # Don't block on read errors

    # Detect project type based on manifest or file structure
    is_node_project = (path / "package.json").exists()
    is_python_project = (path / "pyproject.toml").exists() or (path / "requirements.txt").exists()

    # Python-specific validation (backend-service template)
    if is_python_project and not is_node_project:
        if (path / "requirements.txt").exists() and not (path / "pyproject.toml").exists():
            result.add_warning("Using requirements.txt without pyproject.toml")

        # Validate Python syntax for all .py files
        python_errors = validate_python_syntax(path, exclude_dirs)
        for error in python_errors:
            result.add_error(error)

        # Validate Python imports with production dependencies
        import_errors, import_warnings = validate_python_imports(path)
        for error in import_errors:
            result.add_error(error)
        for warning in import_warnings:
            result.add_warning(warning)

    # Node.js-specific validation
    if is_node_project:
        node_errors, node_warnings = validate_node_project(path, manifest)
        for error in node_errors:
            result.add_error(error)
        for warning in node_warnings:
            result.add_warning(warning)

    # Fullstack (web-app) validation - check backend Python imports
    if manifest and manifest.runtime == "fullstack":
        backend_path = path / "backend"
        if backend_path.exists():
            # Validate Python syntax in backend
            python_errors = validate_python_syntax(backend_path, exclude_dirs)
            for error in python_errors:
                result.add_error(error)

            # Validate Python imports in backend
            import_errors, import_warnings = validate_python_imports(path, backend_path)
            for error in import_errors:
                result.add_error(error)
            for warning in import_warnings:
                result.add_warning(warning)

    return result.is_valid, result.errors, result.warnings


def validate_node_project(path: Path, manifest: Manifest | None) -> tuple[list[str], list[str]]:
    """Validate Node.js project structure.

    Args:
        path: Path to project directory
        manifest: Parsed manifest (if available)

    Returns:
        Tuple of (errors, warnings)
    """
    import json

    errors = []
    warnings = []

    package_json_path = path / "package.json"
    if not package_json_path.exists():
        errors.append("Missing package.json for Node.js project")
        return errors, warnings

    try:
        package_json = json.loads(package_json_path.read_text())
    except json.JSONDecodeError as e:
        errors.append(f"Invalid package.json: {e}")
        return errors, warnings

    # Check for required scripts
    scripts = package_json.get("scripts", {})
    if "build" not in scripts:
        warnings.append("No 'build' script in package.json")

    # Check for TypeScript config if using TypeScript
    if (path / "tsconfig.json").exists():
        try:
            json.loads((path / "tsconfig.json").read_text())
        except json.JSONDecodeError as e:
            errors.append(f"Invalid tsconfig.json: {e}")

    # Static-site template specific checks
    if manifest and manifest.template == "static-site":
        # Check for Next.js config
        if not (path / "next.config.js").exists() and not (path / "next.config.mjs").exists():
            warnings.append("Missing next.config.js for Next.js project")

        # Check that it's configured for static export
        next_config_path = path / "next.config.js"
        if next_config_path.exists():
            config_content = next_config_path.read_text()
            if "output" not in config_content or "'export'" not in config_content:
                warnings.append(
                    "next.config.js should have output: 'export' for static deployment"
                )

    return errors, warnings


def validate_python_syntax(path: Path, exclude_dirs: set) -> list[str]:
    """Validate Python syntax for all .py files in the project.

    Args:
        path: Path to project directory
        exclude_dirs: Set of directory names to exclude

    Returns:
        List of syntax error messages
    """
    errors = []

    for py_file in path.rglob("*.py"):
        # Skip excluded directories
        if any(excluded in py_file.parts for excluded in exclude_dirs):
            continue

        try:
            source = py_file.read_text()
            ast.parse(source, filename=str(py_file))
        except SyntaxError as e:
            relative_path = py_file.relative_to(path)
            errors.append(
                f"Syntax error in {relative_path}:{e.lineno}: {e.msg}"
            )

    return errors


def _parse_pyproject_dependencies(pyproject_path: Path) -> tuple[list[str], list[str]]:
    """Parse production and dev dependencies from pyproject.toml.
    
    Uses regex parsing to avoid external TOML dependencies.
    
    Args:
        pyproject_path: Path to pyproject.toml file
        
    Returns:
        Tuple of (production_dependencies, dev_dependencies) as lists of package names
    """
    if not pyproject_path.exists():
        return [], []
    
    try:
        content = pyproject_path.read_text()
    except Exception:
        return [], []
    
    prod_deps = []
    dev_deps = []
    
    # Parse [project] dependencies section
    # Find the [project] section, then look for dependencies = [...]
    project_section_match = re.search(r'\[project\](.*?)(?=\n\[|\Z)', content, re.DOTALL)
    if project_section_match:
        project_section = project_section_match.group(1)
        # Find dependencies = [...] using bracket counting to handle nested brackets
        deps_start = project_section.find('dependencies = [')
        if deps_start != -1:
            bracket_count = 0
            start_idx = deps_start + len('dependencies = [')
            i = start_idx
            while i < len(project_section):
                if project_section[i] == '[':
                    bracket_count += 1
                elif project_section[i] == ']':
                    if bracket_count == 0:
                        deps_content = project_section[start_idx:i]
                        # Extract individual dependencies (handle multi-line, quotes, etc.)
                        dep_pattern = r'["\']([^"\']+)["\']'
                        for dep_match in re.finditer(dep_pattern, deps_content):
                            dep = dep_match.group(1)
                            # Extract package name (remove version constraints)
                            # Handle formats like "fastapi>=0.100.0,<1.0" or "uvicorn[standard]>=0.20.0"
                            pkg_match = re.match(r"^([a-zA-Z0-9_-]+(?:\[[^\]]+\])?)", dep.strip())
                            if pkg_match:
                                prod_deps.append(pkg_match.group(1).lower())
                        break
                    bracket_count -= 1
                i += 1
    
    # Parse [project.optional-dependencies] dev section
    optional_section_match = re.search(
        r'\[project\.optional-dependencies\](.*?)(?=\n\[|\Z)', content, re.DOTALL
    )
    if optional_section_match:
        optional_section = optional_section_match.group(1)
        # Find dev = [...] using bracket counting
        dev_start = optional_section.find('dev = [')
        if dev_start == -1:
            dev_start = optional_section.find('dev=[')
        if dev_start != -1:
            bracket_count = 0
            start_idx = dev_start + len('dev = [') if 'dev = [' in optional_section[dev_start:dev_start+10] else dev_start + len('dev=[')
            i = start_idx
            while i < len(optional_section):
                if optional_section[i] == '[':
                    bracket_count += 1
                elif optional_section[i] == ']':
                    if bracket_count == 0:
                        dev_deps_content = optional_section[start_idx:i]
                        dep_pattern = r'["\']([^"\']+)["\']'
                        for dep_match in re.finditer(dep_pattern, dev_deps_content):
                            dep = dep_match.group(1)
                            pkg_match = re.match(r"^([a-zA-Z0-9_-]+(?:\[[^\]]+\])?)", dep.strip())
                            if pkg_match:
                                dev_deps.append(pkg_match.group(1).lower())
                        break
                    bracket_count -= 1
                i += 1
    
    return prod_deps, dev_deps


def _normalize_package_name(module_name: str) -> str:
    """Normalize module name to package name.
    
    Maps common import names to their package names (e.g., 'yaml' -> 'pyyaml').
    """
    # Common mappings
    mappings = {
        "yaml": "pyyaml",
        "dotenv": "python-dotenv",
        "pkg_resources": "setuptools",
    }
    
    # Check if it's a direct mapping
    if module_name.lower() in mappings:
        return mappings[module_name.lower()]
    
    # Return as-is (most packages have the same import and package name)
    return module_name.lower()


def validate_python_imports(
    project_path: Path,
    backend_path: Path | None = None,
) -> tuple[list[str], list[str]]:
    """Validate Python imports by testing in a clean venv with production deps only.

    This is deterministic - it exactly mirrors what happens in production.
    Creates a temporary venv, installs only production dependencies (not dev),
    and tries to import the main module.

    Args:
        project_path: Path to project root
        backend_path: Path to backend directory (for fullstack apps)

    Returns:
        Tuple of (errors, warnings)
    """
    errors = []
    warnings = []

    # Determine the Python package path
    if backend_path and backend_path.exists():
        package_path = backend_path
        pyproject = backend_path / "pyproject.toml"
    elif (project_path / "backend").exists():
        package_path = project_path / "backend"
        pyproject = package_path / "pyproject.toml"
    elif (project_path / "pyproject.toml").exists():
        package_path = project_path
        pyproject = project_path / "pyproject.toml"
    else:
        # No Python project to validate
        return errors, warnings

    if not pyproject.exists():
        return errors, warnings

    # Find the main module to import
    app_dir = package_path / "app"
    if not app_dir.exists():
        warnings.append("No 'app' directory found - skipping import validation")
        return errors, warnings

    main_module = "app.main"
    if not (app_dir / "main.py").exists():
        warnings.append("No 'app/main.py' found - skipping import validation")
        return errors, warnings

    console.print("  Checking Python imports with production dependencies...")

    # Create temporary venv and test imports
    with tempfile.TemporaryDirectory() as temp_dir:
        venv_path = Path(temp_dir) / "venv"

        try:
            # Create venv
            result = subprocess.run(
                [sys.executable, "-m", "venv", str(venv_path)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                warnings.append("Could not create venv for import validation")
                return errors, warnings

            # Get venv python path
            if sys.platform == "win32":
                venv_python = venv_path / "Scripts" / "python.exe"
            else:
                venv_python = venv_path / "bin" / "python"

            # Install production dependencies only (not dev)
            # Use "." as the path since we're running from package_path
            result = subprocess.run(
                [
                    str(venv_python), "-m", "pip", "install",
                    "--no-cache-dir",
                    ".",
                ],
                capture_output=True,
                text=True,
                timeout=180,  # Increase timeout for slow networks
                cwd=str(package_path),
            )
            if result.returncode != 0:
                # Parse the error to give a helpful message
                stderr = result.stderr
                if "No module named" in stderr:
                    errors.append(f"Failed to install package: {stderr.strip()}")
                else:
                    errors.append(
                        f"Failed to install Python package. Check pyproject.toml.\n"
                        f"  Error: {stderr.strip()[:200]}"
                    )
                return errors, warnings
            
            # Verify that dependencies were actually installed
            check_result = subprocess.run(
                [str(venv_python), "-m", "pip", "list"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            installed_packages = check_result.stdout.lower() if check_result.returncode == 0 else ""

            # Try to import the main module
            # The package is installed in the venv, so its dependencies are available.
            # We need to run from the package directory so Python can find the local
            # app/ module, but use the venv's Python which has the dependencies installed.
            #
            # The key insight: `pip install .` installs the package AND its dependencies
            # into the venv. When we run `venv_python -c "import app.main"` from the
            # package directory, Python will:
            # 1. Find app/ in the current directory (local module)
            # 2. When app/main.py does `from fastapi import FastAPI`, Python looks in
            #    the venv's site-packages (because we're using venv_python)
            #
            # If this fails with ModuleNotFoundError, it means the dependency wasn't
            # installed properly.
            result = subprocess.run(
                [
                    str(venv_python),
                    "-c",
                    f"import sys; sys.path.insert(0, '.'); import {main_module}; print('OK')",
                ],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(package_path),
            )

            if result.returncode != 0:
                stderr = result.stderr
                # Parse common import errors
                if "ModuleNotFoundError: No module named" in stderr:
                    # Extract the missing module name
                    match = re.search(r"No module named '([^']+)'", stderr)
                    if match:
                        missing_module = match.group(1)
                        # Parse pyproject.toml to check if dependency is actually missing
                        prod_deps, dev_deps = _parse_pyproject_dependencies(pyproject)
                        normalized_module = _normalize_package_name(missing_module)
                        
                        # Normalize dependencies: extract base package name (before [extras] or version)
                        def normalize_dep(dep: str) -> str:
                            # Remove extras like "uvicorn[standard]" -> "uvicorn"
                            base = dep.split("[")[0]
                            return _normalize_package_name(base)
                        
                        prod_deps_normalized = [normalize_dep(dep) for dep in prod_deps]
                        dev_deps_normalized = [normalize_dep(dep) for dep in dev_deps]
                        
                        # Check if the module name matches any dependency
                        # Handle cases where package name differs from import name
                        is_in_prod = normalized_module in prod_deps_normalized
                        is_in_dev = normalized_module in dev_deps_normalized
                        
                        # Also check reverse mapping (e.g., if dependency is "pyyaml" but import is "yaml")
                        reverse_mappings = {
                            "pyyaml": "yaml",
                            "python-dotenv": "dotenv",
                            "setuptools": "pkg_resources",
                        }
                        for pkg_name, import_name in reverse_mappings.items():
                            if normalized_module == import_name and pkg_name in prod_deps_normalized:
                                is_in_prod = True
                            if normalized_module == import_name and pkg_name in dev_deps_normalized:
                                is_in_dev = True
                        
                        if is_in_prod:
                            # Dependency is listed in pyproject.toml but not importable
                            # Check if it was actually installed in the venv
                            pkg_installed = normalized_module in installed_packages
                            if pkg_installed:
                                # Package is installed but still can't import - likely a path issue
                                errors.append(
                                    f"Dependency '{missing_module}' is installed but cannot be imported.\n"
                                    f"  This may be a Python path issue. Verify your project structure.\n"
                                    f"  Error: {stderr.strip()[:300]}"
                                )
                            else:
                                # Package was supposed to be installed but wasn't
                                errors.append(
                                    f"Dependency '{missing_module}' is listed in pyproject.toml but pip failed to install it.\n"
                                    f"  Found in dependencies: {', '.join(prod_deps[:5])}{'...' if len(prod_deps) > 5 else ''}\n"
                                    f"  Try running: pip install {missing_module}\n"
                                    f"  Error: {stderr.strip()[:300]}"
                                )
                        elif is_in_dev:
                            # Dependency is in dev deps but not production
                            errors.append(
                                f"Missing dependency: '{missing_module}' is imported but only listed in "
                                f"[project.optional-dependencies] dev.\n"
                                f"  Add it to [project] dependencies (not dev) for production use."
                            )
                        else:
                            # Actually missing - show what dependencies were found
                            deps_preview = ', '.join(prod_deps[:5]) + ('...' if len(prod_deps) > 5 else '')
                            if not prod_deps:
                                deps_preview = "(none found)"
                            errors.append(
                                f"Missing dependency: '{missing_module}' is imported but not in "
                                f"pyproject.toml dependencies.\n"
                                f"  Found dependencies: {deps_preview}\n"
                                f"  Add '{missing_module}' to [project] dependencies (not [project.optional-dependencies] dev)"
                            )
                    else:
                        errors.append(f"Import error: {stderr.strip()[:300]}")
                elif "ImportError" in stderr:
                    errors.append(f"Import error in {main_module}: {stderr.strip()[:300]}")
                else:
                    errors.append(f"Failed to import {main_module}: {stderr.strip()[:300]}")
            else:
                console.print("  [green]✓[/green] Python imports validated")

        except subprocess.TimeoutExpired:
            warnings.append("Import validation timed out")
        except Exception as e:
            warnings.append(f"Import validation failed: {e}")

    return errors, warnings


def validate_health_config(manifest: Manifest) -> tuple[list[str], list[str]]:
    """Validate health endpoint configuration in manifest.
    
    Checks that health_path is properly configured. The actual health
    endpoint behavior is checked at runtime, not statically.
    
    Args:
        manifest: Parsed manifest
        
    Returns:
        Tuple of (errors, warnings)
    """
    errors = []
    warnings = []
    
    # Check health_path exists and is valid
    if not manifest.health_path:
        errors.append(
            "Manifest missing health_path. "
            "Add 'health_path: /health' to runtm.yaml"
        )
    elif not manifest.health_path.startswith("/"):
        errors.append(
            f"health_path must start with /. Got: {manifest.health_path}"
        )
    
    # Warn if non-standard health path
    if manifest.health_path and manifest.health_path != "/health":
        warnings.append(
            f"Non-standard health_path: {manifest.health_path}. "
            "Consider using /health for consistency."
        )

    return errors, warnings


def validate_command(
    path: Path = typer.Argument(
        Path("."),
        help="Path to project directory",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
) -> None:
    """Validate project before deployment.

    Checks:
    - runtm.yaml exists and is valid
    - Dockerfile exists
    - Artifact size is within limits
    - No env/secrets in manifest (not supported in V0)
    """
    console.print(f"Validating project: {path.absolute()}")
    console.print()

    is_valid, errors, warnings = validate_project(path)

    # Show warnings
    for warning in warnings:
        console.print(f"[yellow]⚠[/yellow] {warning}")

    # Show errors
    for error in errors:
        console.print(f"[red]✗[/red] {error}")

    console.print()

    if is_valid:
        console.print("[green]✓[/green] Project is valid and ready to deploy")
    else:
        console.print("[red]✗[/red] Validation failed. Fix the errors above and try again.")
        raise typer.Exit(1)

