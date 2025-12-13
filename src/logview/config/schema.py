"""Pydantic models for configuration."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class GKEContext(BaseModel):
    """GKE log source context configuration."""

    name: str
    type: Literal["gke"]
    project: str
    cluster: str
    default_namespace: str | None = None


class GCPContext(BaseModel):
    """GCP Cloud Logging context configuration."""

    name: str
    type: Literal["gcp"]
    project: str
    log_name: str | None = None


class SyslogContext(BaseModel):
    """Local syslog context configuration."""

    name: str
    type: Literal["syslog"]
    path: str = "/var/log/syslog"


class MockContext(BaseModel):
    """Mock log source for testing."""

    name: str
    type: Literal["mock"]
    seed: int | None = None


Context = Annotated[
    GKEContext | GCPContext | SyslogContext | MockContext,
    Field(discriminator="type"),
]


class FilterPreset(BaseModel):
    """A saved filter preset."""

    name: str
    severity: str | None = None
    time_range_minutes: int | None = None
    namespace: str | None = None
    pod: str | None = None
    text_search: str | None = None


class UISettings(BaseModel):
    """UI preference settings."""

    theme: Literal["dark", "light"] = "dark"
    timestamp_format: str = "%Y-%m-%d %H:%M:%S"
    max_message_width: int = 80
    show_metadata: bool = False


class SecuritySettings(BaseModel):
    """Security-related settings."""

    credential_helper: Literal["gcloud", "env", "keyring"] = "gcloud"


class Config(BaseModel):
    """Root configuration model."""

    contexts: list[Context] = Field(default_factory=list)
    presets: list[FilterPreset] = Field(default_factory=list)
    ui: UISettings = Field(default_factory=UISettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
