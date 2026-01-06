"""Core module for Scale Agents."""

from scale_agents.core.exceptions import (
    AgentRoutingError,
    ConfirmationRequiredError,
    MCPConnectionError,
    MCPToolError,
    ScaleAgentError,
    ToolNotAllowedError,
    ValidationError,
)
from scale_agents.core.logging import get_logger, setup_logging

__all__ = [
    "AgentRoutingError",
    "ConfirmationRequiredError",
    "MCPConnectionError",
    "MCPToolError",
    "ScaleAgentError",
    "ToolNotAllowedError",
    "ValidationError",
    "get_logger",
    "setup_logging",
]

# Optional LLM reasoning exports
try:
    from scale_agents.core.reasoning import (  # noqa: F401
        LLMReasoner,
        ReasoningResult,
        classify_with_llm,
        get_reasoner,
        select_tools_with_llm,
    )

    __all__.extend([
        "LLMReasoner",
        "ReasoningResult",
        "classify_with_llm",
        "get_reasoner",
        "select_tools_with_llm",
    ])
except ImportError:
    pass
