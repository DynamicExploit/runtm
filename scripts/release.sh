#!/bin/bash
# Release helper script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

VERSION=${1:-}

if [ -z "$VERSION" ]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 0.1.0"
    exit 1
fi

echo "Releasing version $VERSION..."

cd "$PROJECT_ROOT"

# Ensure we're on main branch
BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$BRANCH" != "main" ]; then
    echo "Error: Must be on main branch to release"
    exit 1
fi

# Ensure working directory is clean
if [ -n "$(git status --porcelain)" ]; then
    echo "Error: Working directory is not clean"
    exit 1
fi

# Run tests
echo "Running tests..."
pytest

# Run linter
echo "Running linter..."
ruff check .

# Update version in pyproject.toml files
echo "Updating versions..."
for pkg in shared api worker cli; do
    sed -i '' "s/version = \".*\"/version = \"$VERSION\"/" "packages/$pkg/pyproject.toml"
done

# Build packages
echo "Building packages..."
for pkg in shared api worker cli; do
    cd "packages/$pkg"
    python -m build
    cd "$PROJECT_ROOT"
done

# Create git tag
echo "Creating git tag..."
git add -A
git commit -m "chore: release v$VERSION"
git tag -a "v$VERSION" -m "Release v$VERSION"

echo ""
echo "Release v$VERSION prepared!"
echo ""
echo "Next steps:"
echo "  1. Review the commit: git show HEAD"
echo "  2. Push to origin: git push origin main --tags"
echo "  3. Publish to PyPI: twine upload packages/*/dist/*"

