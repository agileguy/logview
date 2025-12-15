#!/usr/bin/env bats
# BATS tests for install.sh
#
# To run these tests:
#   bats tests/bats/install.bats
#
# Install BATS:
#   Ubuntu/Debian: sudo apt-get install bats
#   macOS: brew install bats-core

setup() {
    # Source the install script functions (but don't execute main)
    export INSTALL_SCRIPT="./install.sh"
    export TEST_MODE=true

    # Mock environment
    export HOME="/tmp/logview-test-home"
    mkdir -p "$HOME"
}

teardown() {
    # Cleanup
    rm -rf "/tmp/logview-test-home"
}

# Test: Script exists and is executable
@test "install.sh exists and is executable" {
    [ -f "$INSTALL_SCRIPT" ]
    [ -x "$INSTALL_SCRIPT" ]
}

# Test: Help flag shows usage
@test "install.sh --help shows usage" {
    run bash "$INSTALL_SCRIPT" --help
    [ "$status" -eq 0 ]
    [[ "$output" =~ "Usage:" ]]
    [[ "$output" =~ "--with-gcp" ]]
    [[ "$output" =~ "--method" ]]
    [[ "$output" =~ "--uninstall" ]]
}

# Test: Invalid option shows error
@test "install.sh with invalid option shows error" {
    run bash "$INSTALL_SCRIPT" --invalid-option
    [ "$status" -eq 1 ]
    [[ "$output" =~ "Unknown option" ]]
}

# Test: --method without value shows error
@test "install.sh --method without value shows error" {
    run bash "$INSTALL_SCRIPT" --method
    [ "$status" -eq 1 ]
    [[ "$output" =~ "requires an argument" ]]
}

# Test: --method with another flag shows error
@test "install.sh --method followed by flag shows error" {
    run bash "$INSTALL_SCRIPT" --method --with-gcp
    [ "$status" -eq 1 ]
    [[ "$output" =~ "requires an argument" ]]
}

# Test: version_ge function
@test "version comparison: 3.11 >= 3.11" {
    # Test the version_ge function directly
    source "$INSTALL_SCRIPT" || true

    # Mock the version_ge function test
    run bash -c "source $INSTALL_SCRIPT; version_ge '3.11' '3.11'"
    [ "$status" -eq 0 ]
}

@test "version comparison: 3.12 >= 3.11" {
    run bash -c "source $INSTALL_SCRIPT; version_ge '3.12' '3.11'"
    [ "$status" -eq 0 ]
}

@test "version comparison: 3.10 < 3.11" {
    run bash -c "source $INSTALL_SCRIPT; version_ge '3.10' '3.11'"
    [ "$status" -eq 1 ]
}

@test "version comparison: 3.11.5 >= 3.11" {
    run bash -c "source $INSTALL_SCRIPT; version_ge '3.11.5' '3.11'"
    [ "$status" -eq 0 ]
}

# Test: OS detection
@test "OS detection works on Linux" {
    skip "Requires OS-specific environment"
}

# Test: Config directory creation
@test "Config directory path is correct" {
    run bash -c "source $INSTALL_SCRIPT; echo \$CONFIG_DIR"
    [[ "$output" =~ "/.config/logview" ]]
}

# Note: Full integration tests (actual installation) should be run manually
# or in a separate CI workflow with proper isolation
