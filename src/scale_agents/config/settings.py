"""Configuration management for Scale Agents.

Supports configuration from:
1. YAML configuration file (config.yaml)
2. Environment variables (override YAML)
3. Default values

Priority: Environment Variables > YAML Config > Defaults
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Try to import YAML support
try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False


def load_yaml_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load configuration from YAML file.

    Args:
        config_path: Path to config file. If None, searches for config.yaml
                    in current directory and parent directories.

    Returns:
        Dictionary of configuration values.
    """
    if not _HAS_YAML:
        return {}

    # Search paths for config file
    search_paths = []
    if config_path:
        search_paths.append(Path(config_path))
    else:
        cwd = Path.cwd()
        search_paths.extend([
            cwd / "config.yaml",
            cwd / "config.yml",
            cwd / ".scale-agents.yaml",
            cwd / ".scale-agents.yml",
            Path.home() / ".config" / "scale-agents" / "config.yaml",
        ])

    for path in search_paths:
        if path.exists():
            with open(path) as f:
                config = yaml.safe_load(f) or {}
                return config

    return {}


class MCPSettings(BaseSettings):
    """MCP Server connection settings."""

    model_config = SettingsConfigDict(
        env_prefix="SCALE_AGENTS_MCP_",
        extra="ignore",
    )

    server_url: str = Field(
        default="http://127.0.0.1:8000/mcp",
        description="URL of the scale-mcp-server endpoint",
    )
    timeout: float = Field(
        default=60.0,
        ge=1.0,
        le=300.0,
        description="Request timeout in seconds",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retry attempts for failed requests",
    )
    retry_delay: float = Field(
        default=1.0,
        ge=0.1,
        le=30.0,
        description="Base delay between retries in seconds",
    )
    domain: str = Field(
        default="StorageScaleDomain",
        description="Storage Scale domain for authorization",
    )


class LLMSettings(BaseSettings):
    """LLM provider settings for reasoning."""

    model_config = SettingsConfigDict(
        env_prefix="SCALE_AGENTS_LLM_",
        extra="ignore",
    )

    enabled: bool = Field(
        default=False,
        description="Enable LLM-powered reasoning",
    )
    provider: str | None = Field(
        default=None,
        description="LLM provider: ollama, openai, anthropic",
    )
    model: str | None = Field(
        default=None,
        description="Model name/identifier",
    )
    base_url: str | None = Field(
        default=None,
        description="Base URL for API (required for ollama)",
    )
    api_key: str | None = Field(
        default=None,
        description="API key for provider",
    )
    temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=2.0,
        description="Sampling temperature",
    )
    max_tokens: int = Field(
        default=4096,
        ge=100,
        le=128000,
        description="Maximum tokens in response",
    )


class ServerSettings(BaseSettings):
    """Agent server settings."""

    model_config = SettingsConfigDict(
        env_prefix="SCALE_AGENTS_",
        extra="ignore",
    )

    host: str = Field(
        default="0.0.0.0",
        description="Host to bind the server",
    )
    port: int = Field(
        default=10000,
        ge=1,
        le=65535,
        description="Port to bind the server (AgentStack default: 10000)",
    )


class SecuritySettings(BaseSettings):
    """Security and confirmation settings."""

    model_config = SettingsConfigDict(
        env_prefix="SCALE_AGENTS_",
        extra="ignore",
    )

    require_confirmation: bool = Field(
        default=True,
        description="Require confirmation for destructive operations",
    )
    confirmation_timeout: int = Field(
        default=300,
        ge=30,
        le=3600,
        description="Confirmation timeout in seconds",
    )
    allowed_domains: list[str] = Field(
        default_factory=list,
        description="Allowed Storage Scale domains (empty = all)",
    )


class LoggingSettings(BaseSettings):
    """Logging configuration."""

    model_config = SettingsConfigDict(
        env_prefix="SCALE_AGENTS_LOG_",
        extra="ignore",
    )

    level: str = Field(
        default="INFO",
        description="Log level: DEBUG, INFO, WARNING, ERROR",
    )
    format: str = Field(
        default="json",
        description="Log format: json, console",
    )
    file: str | None = Field(
        default=None,
        description="Log file path (optional)",
    )


class AgentConfig(BaseSettings):
    """Configuration for individual agents."""

    model_config = SettingsConfigDict(extra="ignore")

    enabled: bool = Field(default=True, description="Enable this agent")
    description: str | None = Field(default=None, description="Custom description")
    max_results: int = Field(default=100, description="Max results to return")
    timeout: float | None = Field(default=None, description="Agent-specific timeout")


class AgentsSettings(BaseSettings):
    """Settings for all agents."""

    model_config = SettingsConfigDict(extra="ignore")

    orchestrator: AgentConfig = Field(default_factory=AgentConfig)
    health: AgentConfig = Field(default_factory=AgentConfig)
    storage: AgentConfig = Field(default_factory=AgentConfig)
    quota: AgentConfig = Field(default_factory=AgentConfig)
    performance: AgentConfig = Field(default_factory=AgentConfig)
    admin: AgentConfig = Field(default_factory=AgentConfig)


class Settings(BaseSettings):
    """Main settings container for Scale Agents.

    Loads configuration from:
    1. config.yaml (if present)
    2. Environment variables (override YAML)
    3. Default values

    Environment variable format: SCALE_AGENTS_<SECTION>_<KEY>
    Example: SCALE_AGENTS_MCP_SERVER_URL, SCALE_AGENTS_LLM_PROVIDER
    """

    model_config = SettingsConfigDict(
        env_prefix="SCALE_AGENTS_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # Nested settings
    mcp: MCPSettings = Field(default_factory=MCPSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    agents: AgentsSettings = Field(default_factory=AgentsSettings)

    # Legacy flat access (for backwards compatibility)
    @property
    def mcp_server_url(self) -> str:
        return self.mcp.server_url

    @property
    def mcp_timeout(self) -> float:
        return self.mcp.timeout

    @property
    def mcp_max_retries(self) -> int:
        return self.mcp.max_retries

    @property
    def host(self) -> str:
        return self.server.host

    @property
    def port(self) -> int:
        return self.server.port

    @property
    def require_confirmation(self) -> bool:
        return self.security.require_confirmation

    @property
    def log_level(self) -> str:
        return self.logging.level

    @property
    def log_format(self) -> str:
        return self.logging.format

    @property
    def llm_enabled(self) -> bool:
        return self.llm.enabled

    @property
    def llm_provider(self) -> str | None:
        return self.llm.provider

    @property
    def llm_model(self) -> str | None:
        return self.llm.model

    @property
    def llm_base_url(self) -> str | None:
        return self.llm.base_url

    @property
    def llm_api_key(self) -> str | None:
        return self.llm.api_key

    @model_validator(mode="before")
    @classmethod
    def load_from_yaml(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Load configuration from YAML file and merge with env vars."""
        # Get config file path from env or use default search
        config_path = os.environ.get("SCALE_AGENTS_CONFIG")
        yaml_config = load_yaml_config(Path(config_path) if config_path else None)

        # Merge: YAML first, then data (env vars) override
        def deep_merge(base: dict, override: dict) -> dict:
            result = base.copy()
            for key, value in override.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = deep_merge(result[key], value)
                else:
                    result[key] = value
            return result

        return deep_merge(yaml_config, data)


def load_settings(config_path: str | None = None) -> Settings:
    """Load settings from config file and environment.

    Args:
        config_path: Optional path to config file.

    Returns:
        Configured Settings instance.
    """
    if config_path:
        os.environ["SCALE_AGENTS_CONFIG"] = config_path

    return Settings()


# Global settings instance (lazy loaded)
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


def reload_settings(config_path: str | None = None) -> Settings:
    """Reload settings from config file.

    Args:
        config_path: Optional path to config file.

    Returns:
        New Settings instance.
    """
    global _settings
    _settings = load_settings(config_path)
    return _settings


# Backwards compatibility
settings = get_settings()
