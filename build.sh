#!/usr/bin/env bash

# LogView Build Script
# Builds distribution wheel and generates checksums for release

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored output
info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

success() {
    echo -e "${GREEN}✓${NC} $1"
}

warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

error() {
    echo -e "${RED}✗${NC} $1" >&2
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
check_prerequisites() {
    info "Checking build prerequisites..."

    if ! command_exists python3; then
        error "Python 3 is required to build"
        exit 1
    fi

    # Check if build module is installed
    if ! python3 -c "import build" 2>/dev/null; then
        info "Installing build module..."
        python3 -m pip install --upgrade build
    fi

    success "Prerequisites OK"
}

# Clean previous builds
clean_build() {
    info "Cleaning previous build artifacts..."
    rm -rf dist/ build/ *.egg-info
    success "Clean complete"
}

# Read version from VERSION file
get_version() {
    if [[ -f VERSION ]]; then
        cat VERSION
    else
        error "VERSION file not found"
        exit 1
    fi
}

# Build wheel
build_wheel() {
    info "Building wheel..."

    python3 -m build --wheel

    if [[ $? -eq 0 ]]; then
        success "Wheel built successfully"
    else
        error "Wheel build failed"
        exit 1
    fi
}

# Build source distribution
build_sdist() {
    info "Building source distribution..."

    python3 -m build --sdist

    if [[ $? -eq 0 ]]; then
        success "Source distribution built successfully"
    else
        error "Source distribution build failed"
        exit 1
    fi
}

# Generate checksums
generate_checksums() {
    info "Generating checksums..."

    if [[ ! -d dist ]]; then
        error "dist/ directory not found"
        exit 1
    fi

    cd dist

    # Generate SHA256 checksums
    if command_exists shasum; then
        shasum -a 256 *.whl *.tar.gz > SHA256SUMS
    elif command_exists sha256sum; then
        sha256sum *.whl *.tar.gz > SHA256SUMS
    else
        warning "shasum/sha256sum not found, skipping checksum generation"
        cd ..
        return
    fi

    cd ..
    success "Checksums generated: dist/SHA256SUMS"
}

# List build artifacts
list_artifacts() {
    echo ""
    info "Build artifacts:"
    echo ""

    if [[ -d dist ]]; then
        ls -lh dist/
    fi

    echo ""
}

# Verify wheel contents
verify_wheel() {
    info "Verifying wheel contents..."

    local wheel_file
    wheel_file=$(find dist -name "*.whl" | head -n 1)

    if [[ -z "$wheel_file" ]]; then
        error "No wheel file found"
        exit 1
    fi

    info "Wheel file: $wheel_file"

    # Check if unzip is available
    if command_exists unzip; then
        info "Wheel contents:"
        unzip -l "$wheel_file" | grep -E "logview/(.*\.py|py\.typed)" | head -20
        if [[ $(unzip -l "$wheel_file" | grep -c "logview/") -gt 20 ]]; then
            info "... ($(unzip -l "$wheel_file" | grep -c "logview/") total files)"
        fi
    else
        warning "unzip not found, skipping wheel content verification"
    fi

    success "Wheel verification complete"
}

# Create release notes template
create_release_notes() {
    local version
    version=$(get_version)

    info "Creating release notes template..."

    cat > RELEASE_NOTES.md << EOF
# LogView v${version}

## What's New

<!-- Describe new features and changes -->

## Bug Fixes

<!-- List bug fixes -->

## Installation

### Quick Install (Recommended)
\`\`\`bash
curl -fsSL https://raw.githubusercontent.com/agileguy/logview/v${version}/install.sh | bash
\`\`\`

### Using pip
\`\`\`bash
pip install logview==${version}
# With GCP/GKE support
pip install logview[all]==${version}
\`\`\`

### Using pipx
\`\`\`bash
pipx install logview==${version}
\`\`\`

## Checksums

\`\`\`
$(cat dist/SHA256SUMS 2>/dev/null || echo "Checksums will be added during release")
\`\`\`

## Full Changelog

See [CHANGELOG.md](https://github.com/agileguy/logview/blob/main/CHANGELOG.md) for detailed changes.
EOF

    success "Release notes template created: RELEASE_NOTES.md"
}

# Main build flow
main() {
    echo ""
    info "LogView Build Script"
    echo ""

    local version
    version=$(get_version)
    info "Building version: $version"
    echo ""

    check_prerequisites
    clean_build
    build_wheel
    build_sdist
    generate_checksums
    verify_wheel
    list_artifacts
    create_release_notes

    echo ""
    success "Build complete!"
    echo ""
    info "Next steps:"
    info "  1. Review dist/ artifacts"
    info "  2. Test installation: pip install dist/logview-${version}-py3-none-any.whl"
    info "  3. Update RELEASE_NOTES.md with changes"
    info "  4. Create git tag: git tag v${version}"
    info "  5. Push tag: git push origin v${version}"
    info "  6. Create GitHub release with dist/ artifacts"
    echo ""
}

main "$@"
