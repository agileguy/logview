"""Tests for configuration loading and validation."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from logview.config.loader import load_config, save_config
from logview.config.schema import (
    Config,
    FilterPreset,
    GCPContext,
    GKEContext,
    MockContext,
    SecuritySettings,
    SyslogContext,
    UISettings,
)


class TestConfigSchema:
    """Tests for configuration schema models."""

    def test_gke_context(self) -> None:
        """Test GKE context model."""
        ctx = GKEContext(
            name="prod",
            type="gke",
            project="my-project",
            cluster="prod-cluster",
            default_namespace="default",
        )
        assert ctx.name == "prod"
        assert ctx.type == "gke"
        assert ctx.cluster == "prod-cluster"

    def test_gcp_context(self) -> None:
        """Test GCP context model."""
        ctx = GCPContext(
            name="audit",
            type="gcp",
            project="my-project",
            log_name="cloudaudit.googleapis.com",
        )
        assert ctx.type == "gcp"
        assert ctx.log_name == "cloudaudit.googleapis.com"

    def test_syslog_context(self) -> None:
        """Test syslog context model."""
        ctx = SyslogContext(name="local", type="syslog")
        assert ctx.type == "syslog"
        assert ctx.path == "/var/log/syslog"  # default

    def test_mock_context(self) -> None:
        """Test mock context model."""
        ctx = MockContext(name="test", type="mock", seed=42)
        assert ctx.type == "mock"
        assert ctx.seed == 42

    def test_filter_preset(self) -> None:
        """Test filter preset model."""
        preset = FilterPreset(
            name="errors",
            severity="ERROR",
            time_range_minutes=60,
            namespace="production",
        )
        assert preset.name == "errors"
        assert preset.time_range_minutes == 60

    def test_ui_settings_defaults(self) -> None:
        """Test UI settings defaults."""
        settings = UISettings()
        assert settings.theme == "dark"
        assert settings.timestamp_format == "%Y-%m-%d %H:%M:%S"
        assert settings.max_message_width == 80
        assert settings.show_metadata is False

    def test_security_settings_defaults(self) -> None:
        """Test security settings defaults."""
        settings = SecuritySettings()
        assert settings.credential_helper == "gcloud"

    def test_full_config(self) -> None:
        """Test full configuration model."""
        config = Config(
            contexts=[
                GKEContext(
                    name="prod",
                    type="gke",
                    project="my-project",
                    cluster="prod-cluster",
                ),
                MockContext(name="test", type="mock"),
            ],
            presets=[FilterPreset(name="errors", severity="ERROR")],
            ui=UISettings(theme="light"),
            security=SecuritySettings(credential_helper="env"),
        )
        assert len(config.contexts) == 2
        assert len(config.presets) == 1
        assert config.ui.theme == "light"
        assert config.security.credential_helper == "env"


class TestConfigLoader:
    """Tests for configuration file loading."""

    def test_load_missing_file(self) -> None:
        """Test loading returns default config when file doesn't exist."""
        config = load_config(Path("/nonexistent/path/config.json"))
        assert config == Config()

    def test_load_valid_config(self) -> None:
        """Test loading a valid configuration file."""
        config_data = {
            "contexts": [
                {
                    "name": "test",
                    "type": "mock",
                    "seed": 123,
                }
            ],
            "ui": {"theme": "light"},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            f.flush()

            config = load_config(Path(f.name))
            assert len(config.contexts) == 1
            assert config.ui.theme == "light"

    def test_save_and_load_config(self) -> None:
        """Test round-trip save and load."""
        config = Config(
            contexts=[MockContext(name="test", type="mock", seed=42)],
            ui=UISettings(theme="dark", max_message_width=100),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.json"
            save_config(config, path)

            loaded = load_config(path)
            assert loaded.ui.theme == "dark"
            assert loaded.ui.max_message_width == 100
            assert len(loaded.contexts) == 1

    def test_save_creates_directory(self) -> None:
        """Test that save creates parent directories."""
        config = Config()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "subdir" / "nested" / "config.json"
            save_config(config, path)
            assert path.exists()


class TestConfigValidation:
    """Tests for configuration validation."""

    def test_custom_theme(self) -> None:
        """Test that custom theme values are accepted."""
        # Any string is valid for theme (including Textual built-in themes)
        settings = UISettings(theme="catppuccin-mocha")
        assert settings.theme == "catppuccin-mocha"

        settings2 = UISettings(theme="dark")
        assert settings2.theme == "dark"

    def test_invalid_credential_helper(self) -> None:
        """Test that invalid credential helper values are rejected."""
        with pytest.raises(ValidationError):
            SecuritySettings(credential_helper="invalid")  # type: ignore[arg-type]

    def test_context_type_discriminator(self) -> None:
        """Test that context type discriminator works."""
        config_data = {
            "contexts": [
                {"name": "gke", "type": "gke", "project": "p", "cluster": "c"},
                {"name": "gcp", "type": "gcp", "project": "p"},
                {"name": "sys", "type": "syslog"},
                {"name": "mock", "type": "mock"},
            ]
        }
        config = Config.model_validate(config_data)
        assert isinstance(config.contexts[0], GKEContext)
        assert isinstance(config.contexts[1], GCPContext)
        assert isinstance(config.contexts[2], SyslogContext)
        assert isinstance(config.contexts[3], MockContext)
