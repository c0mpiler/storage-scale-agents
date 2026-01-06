"""AgentStack Server entry point for Scale Agents.

This module initializes and runs the AgentStack server with a single
orchestrator agent that routes to specialized Scale agents internally.

AgentStack SDK constraint: Only ONE @server.agent() decorator per server.
The orchestrator handles routing to health, storage, quota, performance,
and admin agents based on intent classification.

Configuration is loaded from:
1. config.yaml (if present in current directory)
2. Environment variables (override YAML)
3. Default values
"""

# from __future__ import annotations  # Disabled for AgentStack SDK compatibility

import os
import signal
import sys
from typing import TYPE_CHECKING, NoReturn

from a2a.types import Message, TextPart
from a2a.utils.message import get_message_text
from agentstack_sdk.a2a.types import AgentMessage
from agentstack_sdk.server import Server
from agentstack_sdk.server.context import RunContext

from scale_agents.agents.admin import AdminAgent
from scale_agents.agents.health import HealthAgent
from scale_agents.agents.orchestrator import Orchestrator
from scale_agents.agents.performance import PerformanceAgent
from scale_agents.agents.quota import QuotaAgent
from scale_agents.agents.storage import StorageAgent
from scale_agents.config.settings import get_settings, reload_settings
from scale_agents.core.logging import get_logger, setup_logging

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

# Create the server instance
server = Server()


def _create_agents() -> dict[str, object]:
    """Create agent instances based on configuration.

    Returns:
        Dictionary mapping agent names to their instances.
    """
    settings = get_settings()
    use_llm = settings.llm.enabled
    agents_config = settings.agents

    instances = {
        "orchestrator": Orchestrator(use_llm=use_llm),
    }

    if agents_config.health.enabled:
        instances["health"] = HealthAgent()
    if agents_config.storage.enabled:
        instances["storage"] = StorageAgent()
    if agents_config.quota.enabled:
        instances["quota"] = QuotaAgent()
    if agents_config.performance.enabled:
        instances["performance"] = PerformanceAgent()
    if agents_config.admin.enabled:
        instances["admin"] = AdminAgent()

    return instances


# Lazy initialization of agents
_agents: dict[str, object] | None = None


def _get_agents() -> dict[str, object]:
    """Get or create agent instances."""
    global _agents
    if _agents is None:
        _agents = _create_agents()
    return _agents


def _classify_intent(text: str) -> str:
    """Classify user intent to route to appropriate agent.

    Args:
        text: User message text.

    Returns:
        Agent name to route to.
    """
    text_lower = text.lower()

    # Health related keywords
    health_keywords = [
        "health", "status", "node", "event", "diagnostic",
        "monitoring", "alert", "state", "version", "cluster info",
    ]
    if any(kw in text_lower for kw in health_keywords):
        return "health"

    # Storage related keywords
    storage_keywords = [
        "filesystem", "fileset", "mount", "unmount", "pool",
        "storage pool", "create fs", "delete fs", "link", "unlink",
        "nsd", "disk",
    ]
    if any(kw in text_lower for kw in storage_keywords):
        return "storage"

    # Quota related keywords
    quota_keywords = [
        "quota", "usage", "capacity", "limit", "space",
        "disk usage", "fileset usage",
    ]
    if any(kw in text_lower for kw in quota_keywords):
        return "quota"

    # Performance related keywords
    performance_keywords = [
        "performance", "metric", "throughput", "latency",
        "iops", "bandwidth", "bottleneck", "slow",
    ]
    if any(kw in text_lower for kw in performance_keywords):
        return "performance"

    # Admin related keywords
    admin_keywords = [
        "snapshot", "backup", "config", "admin", "remote cluster",
        "policy", "add node", "remove node", "shutdown", "start node",
        "stop node",
    ]
    if any(kw in text_lower for kw in admin_keywords):
        return "admin"

    # Default to orchestrator for complex or unclear requests
    return "orchestrator"


@server.agent()
async def scale_agent(input: Message, context: RunContext):
    """IBM Storage Scale Agent for cluster management and monitoring.

    This is the single entry point for all Storage Scale operations.
    Routes requests to specialized internal agents based on intent:
    
    - **Health**: Cluster health, node status, events, diagnostics
    - **Storage**: Filesystems, filesets, storage pools, NSDs
    - **Quota**: Quota management, capacity monitoring, usage reports
    - **Performance**: Metrics analysis, bottleneck detection, throughput
    - **Admin**: Snapshots, policies, node management, cluster admin
    
    Examples:
        "Show cluster health" -> Health agent
        "List all filesystems" -> Storage agent
        "What's the quota for fileset data01?" -> Quota agent
        "Analyze performance bottlenecks" -> Performance agent
        "Create a snapshot of fs01" -> Admin agent
    """
    agents = _get_agents()
    context_id = getattr(context, "context_id", None)

    # Get message text
    user_text = get_message_text(input) or ""
    
    # Classify intent and route to appropriate agent
    intent = _classify_intent(user_text)
    
    # Get the target agent
    if intent in agents:
        agent = agents[intent]
    else:
        agent = agents["orchestrator"]
    
    logger.debug(
        "routing_request",
        intent=intent,
        agent=type(agent).__name__,
        message_preview=user_text[:100] if user_text else "",
    )
    
    # Process with the selected agent
    try:
        result = await agent.process(input, context_id)
        
        # Yield as AgentMessage for proper AgentStack integration
        if isinstance(result, str):
            yield AgentMessage(parts=[TextPart(text=result)])
        else:
            yield result
            
    except Exception as e:
        logger.exception("agent_error", agent=intent, error=str(e))
        error_msg = f"Error processing request: {e}"
        yield AgentMessage(parts=[TextPart(text=error_msg)])


def handle_shutdown(signum: int, frame: object) -> NoReturn:
    """Handle shutdown signals gracefully."""
    logger.info("shutdown_signal_received", signal=signum)
    sys.exit(0)


def run(config_path: str | None = None) -> None:
    """Main entry point for the server.

    Args:
        config_path: Optional path to configuration file.
    """
    # Load settings (will load config.yaml if present)
    if config_path:
        reload_settings(config_path)

    settings = get_settings()

    # Setup logging
    setup_logging()

    # Setup signal handlers
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Get host and port from environment (AgentStack standard) or settings
    host = os.getenv("HOST", settings.server.host)
    port = int(os.getenv("PORT", settings.server.port))

    # Log configuration summary
    logger.info(
        "scale_agents_starting",
        version="1.0.0",
        config={
            "mcp_server": settings.mcp.server_url,
            "host": host,
            "port": port,
            "llm_enabled": settings.llm.enabled,
            "llm_provider": settings.llm.provider,
            "llm_model": settings.llm.model,
            "require_confirmation": settings.security.require_confirmation,
            "log_level": settings.logging.level,
        },
    )

    # Initialize agents
    global _agents
    _agents = _create_agents()

    registered = list(_agents.keys())
    logger.info(
        "agents_initialized",
        internal_agents=registered,
        llm_enabled=settings.llm.enabled,
        note="Single scale_agent routes to internal agents",
    )

    # Check LLM availability if enabled
    if settings.llm.enabled:
        try:
            import beeai_framework  # noqa: F401

            logger.info(
                "llm_available",
                provider=settings.llm.provider,
                model=settings.llm.model,
            )
        except ImportError:
            logger.warning(
                "beeai_not_installed",
                message="Install with: uv pip install -e '.[llm]'",
            )

    # Run server
    try:
        server.run(host=host, port=port)
    except KeyboardInterrupt:
        logger.info("server_stopped_by_user")
    except Exception as e:
        logger.exception("fatal_error", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    run()
