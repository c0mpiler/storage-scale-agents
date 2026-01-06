"""IBM Storage Scale AI Agents for BeeAI AgentStack."""

__version__ = "1.0.0"


def run(config_path: str | None = None) -> None:
    """Main entry point for the server.
    
    Args:
        config_path: Optional path to configuration file.
    """
    from scale_agents.server import run as _run
    _run(config_path)


__all__ = ["run", "__version__"]
