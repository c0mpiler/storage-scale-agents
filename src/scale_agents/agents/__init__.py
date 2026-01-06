"""Agent implementations for Scale Agents."""

from scale_agents.agents.admin import AdminAgent
from scale_agents.agents.base import BaseScaleAgent
from scale_agents.agents.health import HealthAgent
from scale_agents.agents.orchestrator import Orchestrator
from scale_agents.agents.performance import PerformanceAgent
from scale_agents.agents.quota import QuotaAgent
from scale_agents.agents.storage import StorageAgent

__all__ = [
    "AdminAgent",
    "BaseScaleAgent",
    "HealthAgent",
    "Orchestrator",
    "PerformanceAgent",
    "QuotaAgent",
    "StorageAgent",
]

# Optional LLM-powered agent
try:
    from scale_agents.agents.llm_agent import LLMPoweredAgent  # noqa: F401
    __all__.append("LLMPoweredAgent")
except ImportError:
    pass

