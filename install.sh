#!/usr/bin/env bash

# LogView Installation Script
# This script installs LogView TUI log viewer with automatic platform detection
# Usage: curl -fsSL https://raw.githubusercontent.com/agileguy/logview/main/install.sh | bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
MIN_PYTHON_VERSION="3.11"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/logview"
INSTALL_METHOD=""
WITH_GCP=false
UNINSTALL=false

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

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --with-gcp)
                WITH_GCP=true
                shift
                ;;
            --method)
                if [[ -z "$2" || "$2" == --* ]]; then
                    error "--method requires an argument (pip or pipx)"
                    show_help
                    exit 1
                fi
                INSTALL_METHOD="$2"
                shift 2
                ;;
            --uninstall)
                UNINSTALL=true
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

show_help() {
    cat << EOF
LogView Installation Script

Usage:
    curl -fsSL https://raw.githubusercontent.com/agileguy/logview/main/install.sh | bash
    ./install.sh [OPTIONS]

Options:
    --with-gcp        Install with GCP/GKE support
    --method METHOD   Force installation method (pip or pipx)
    --uninstall       Uninstall LogView
    --help            Show this help message

Examples:
    # Quick install
    curl -fsSL https://raw.githubusercontent.com/agileguy/logview/main/install.sh | bash

    # Install with GCP support
    curl -fsSL https://raw.githubusercontent.com/agileguy/logview/main/install.sh | bash -s -- --with-gcp

    # Force pipx installation
    ./install.sh --method pipx

    # Uninstall
    ./install.sh --uninstall
EOF
}

# Detect operating system
detect_os() {
    case "$(uname -s)" in
        Linux*)
            OS="linux"
            ;;
        Darwin*)
            OS="macos"
            ;;
        *)
            error "Unsupported operating system: $(uname -s)"
            info "LogView supports Linux and macOS"
            exit 1
            ;;
    esac
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Get Python version
get_python_version() {
    if command_exists python3; then
        python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))'
    else
        echo "0.0"
    fi
}

# Compare version numbers (portable - works on macOS and Linux)
# Returns 0 if $1 >= $2, 1 otherwise
version_ge() {
    local actual="$1"
    local required="$2"

    # Split versions into arrays
    IFS='.' read -ra act_parts <<< "$actual"
    IFS='.' read -ra req_parts <<< "$required"

    # Compare each component
    for i in "${!req_parts[@]}"; do
        local act_part="${act_parts[$i]:-0}"  # Default to 0 if not present
        local req_part="${req_parts[$i]}"

        if (( act_part > req_part )); then
            return 0
        elif (( act_part < req_part )); then
            return 1
        fi
    done

    return 0  # Equal versions
}

# Check Python installation
check_python() {
    info "Checking Python installation..."

    if ! command_exists python3; then
        error "Python 3 is not installed"
        info "Please install Python 3.11 or higher:"
        if [[ "$OS" == "macos" ]]; then
            info "  brew install python@3.11"
        else
            info "  sudo apt-get install python3.11  # Debian/Ubuntu"
            info "  sudo dnf install python3.11      # Fedora"
        fi
        exit 1
    fi

    local python_version
    python_version=$(get_python_version)

    if ! version_ge "$python_version" "$MIN_PYTHON_VERSION"; then
        error "Python $python_version is installed, but LogView requires Python $MIN_PYTHON_VERSION or higher"
        exit 1
    fi

    success "Found Python $python_version"
}

# Determine installation method
determine_install_method() {
    if [[ -n "$INSTALL_METHOD" ]]; then
        case "$INSTALL_METHOD" in
            pip)
                if ! command_exists pip3 && ! command_exists pip; then
                    error "pip is not installed"
                    info "Install pip first or use --method pipx"
                    exit 1
                fi
                info "Using forced installation method: $INSTALL_METHOD"
                return
                ;;
            pipx)
                if ! command_exists pipx; then
                    error "pipx is not installed"
                    info "Install pipx first or use --method pip"
                    exit 1
                fi
                info "Using forced installation method: $INSTALL_METHOD"
                return
                ;;
            *)
                error "Invalid installation method: $INSTALL_METHOD"
                info "Valid methods: pip, pipx"
                exit 1
                ;;
        esac
    fi

    # Prefer pipx if available
    if command_exists pipx; then
        INSTALL_METHOD="pipx"
        info "Found pipx - using isolated environment installation"
    elif command_exists pip3 || command_exists pip; then
        INSTALL_METHOD="pip"
        warning "pipx not found - using pip installation"
        info "For isolated installation, install pipx:"
        info "  python3 -m pip install --user pipx"
        info "  python3 -m pipx ensurepath"
    else
        error "Neither pip nor pipx found"
        exit 1
    fi
}

# Install LogView
install_logview() {
    info "Installing LogView..."

    # Check for existing installations
    local existing_method=""
    if command_exists pipx && pipx list --short 2>/dev/null | grep -q "^logview$"; then
        existing_method="pipx"
    elif command_exists pip3 && pip3 show logview >/dev/null 2>&1; then
        existing_method="pip"
    elif command_exists pip && pip show logview >/dev/null 2>&1; then
        existing_method="pip"
    fi

    if [[ -n "$existing_method" ]]; then
        warning "LogView is already installed via $existing_method"
        if [[ "$existing_method" != "$INSTALL_METHOD" ]]; then
            error "Cannot install via $INSTALL_METHOD when already installed via $existing_method"
            info "To switch installation methods, first uninstall:"
            info "  $0 --uninstall"
            info "Then install again with your preferred method"
            exit 1
        else
            info "Reinstalling LogView via $INSTALL_METHOD..."
        fi
    fi

    case "$INSTALL_METHOD" in
        pipx)
            if [[ "$WITH_GCP" == true ]]; then
                info "Installing with GCP/GKE support"
                if pipx install "logview[all]"; then
                    success "LogView installed via pipx"
                else
                    error "Installation failed"
                    exit 1
                fi
            else
                if pipx install logview; then
                    success "LogView installed via pipx"
                else
                    error "Installation failed"
                    exit 1
                fi
            fi
            ;;
        pip)
            if command_exists pip3; then
                PIP_CMD="pip3"
            else
                PIP_CMD="pip"
            fi

            if [[ "$WITH_GCP" == true ]]; then
                info "Installing with GCP/GKE support"
                if $PIP_CMD install --user "logview[all]"; then
                    success "LogView installed via pip"
                else
                    error "Installation failed"
                    exit 1
                fi
            else
                if $PIP_CMD install --user logview; then
                    success "LogView installed via pip"
                else
                    error "Installation failed"
                    exit 1
                fi
            fi
            ;;
    esac
}

# Create configuration directory
create_config_dir() {
    if [[ ! -d "$CONFIG_DIR" ]]; then
        info "Creating configuration directory: $CONFIG_DIR"
        mkdir -p "$CONFIG_DIR"
        success "Configuration directory created"
    else
        info "Configuration directory already exists: $CONFIG_DIR"
    fi
}

# Detect shell config file
detect_shell_config() {
    if [[ -n "$ZSH_VERSION" ]] && [[ -f "$HOME/.zshrc" ]]; then
        echo "$HOME/.zshrc"
    elif [[ -n "$BASH_VERSION" ]] && [[ -f "$HOME/.bashrc" ]]; then
        echo "$HOME/.bashrc"
    elif [[ -f "$HOME/.profile" ]]; then
        echo "$HOME/.profile"
    else
        echo ""
    fi
}

# Offer to update PATH
offer_path_update() {
    local path_to_add="$1"
    local shell_config
    shell_config=$(detect_shell_config)

    if [[ -z "$shell_config" ]]; then
        return
    fi

    # Validate path contains only safe characters (security check)
    if ! [[ "$path_to_add" =~ ^[a-zA-Z0-9/_.-]+$ ]]; then
        warning "Path contains unsafe characters, skipping automatic PATH update"
        info "Manually add: export PATH=\"\$PATH:$path_to_add\""
        return
    fi

    # Check if running in interactive terminal (not piped from curl)
    if [[ ! -t 0 ]]; then
        info "Non-interactive session detected, skipping PATH prompt"
        info "To add to PATH manually, add this to your $shell_config:"
        info "  export PATH=\"\$PATH:$path_to_add\""
        return
    fi

    echo ""
    read -r -p "Would you like to automatically add this to your PATH in $shell_config? (y/n) " response
    case "$response" in
        [yY][eE][sS]|[yY])
            echo "" >> "$shell_config"
            echo "# LogView PATH (added by install.sh)" >> "$shell_config"
            echo "export PATH=\"\$PATH:$path_to_add\"" >> "$shell_config"
            success "PATH updated in $shell_config"
            info "Restart your shell or run: source $shell_config"
            ;;
        *)
            info "Skipping automatic PATH update"
            ;;
    esac
}

# Verify installation
verify_installation() {
    info "Verifying installation..."

    if command_exists logview; then
        success "LogView installed successfully!"
        info "Run 'logview' to start the application"
    else
        warning "LogView command not found in PATH"
        info "You may need to add the installation directory to your PATH"

        if [[ "$INSTALL_METHOD" == "pip" ]]; then
            local user_base
            user_base=$(python3 -m site --user-base)
            info "Add this to your ~/.bashrc or ~/.zshrc:"
            info "  export PATH=\"\$PATH:$user_base/bin\""
            offer_path_update "$user_base/bin"
        elif [[ "$INSTALL_METHOD" == "pipx" ]]; then
            info "Run: pipx ensurepath"
            info "Or let pipx handle PATH setup automatically"
        fi

        if [[ "$INSTALL_METHOD" != "pipx" ]]; then
            warning "You may need to restart your shell or run: source ~/.bashrc"
        fi
    fi
}

# Uninstall LogView
uninstall_logview() {
    info "Uninstalling LogView..."

    local uninstalled=false

    # Try pipx first
    if command_exists pipx; then
        if pipx list --short 2>/dev/null | grep -q "^logview$"; then
            pipx uninstall logview
            success "LogView removed via pipx"
            uninstalled=true
        fi
    fi

    # Try pip (always check, even if pipx succeeded)
    if command_exists pip3; then
        PIP_CMD="pip3"
    elif command_exists pip; then
        PIP_CMD="pip"
    fi

    if [[ -n "$PIP_CMD" ]]; then
        if $PIP_CMD show logview >/dev/null 2>&1; then
            $PIP_CMD uninstall -y logview
            success "LogView removed via pip"
            uninstalled=true
        fi
    fi

    if [[ "$uninstalled" == false ]]; then
        warning "LogView installation not found"
    fi

    # Ask about config directory
    if [[ -d "$CONFIG_DIR" ]]; then
        warning "Configuration directory still exists: $CONFIG_DIR"
        info "Remove it manually if you want to delete all configuration:"
        info "  rm -rf $CONFIG_DIR"
    fi

    success "Uninstallation complete"
}

# Main installation flow
main() {
    echo ""
    info "LogView Installation Script"
    echo ""

    parse_args "$@"

    if [[ "$UNINSTALL" == true ]]; then
        uninstall_logview
        exit 0
    fi

    detect_os
    check_python
    determine_install_method
    install_logview
    create_config_dir
    verify_installation

    echo ""
    success "Installation complete!"
    echo ""
    info "Next steps:"
    info "  1. Run 'logview' to start the application"
    info "  2. Press '?' for help and keyboard shortcuts"
    info "  3. Configure contexts in $CONFIG_DIR/config.json"
    echo ""
    info "Documentation: https://github.com/agileguy/logview"
    echo ""
}

# Only run main if script is executed directly (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
