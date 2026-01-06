"""Orchestrator Agent for intent classification and routing.

This agent serves as the primary entry point, classifying user intent
and routing requests to the appropriate specialized agent.

Supports two modes:
1. Pattern-based: Fast, deterministic regex matching (default)
2. LLM-powered: Semantic understanding via BeeAI Framework (optional)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from a2a.types import Message
from agentstack_sdk.server import Server
from agentstack_sdk.server.context import RunContext
from agentstack_sdk.a2a.types import AgentMessage

from scale_agents.agents.base import BaseScaleAgent
from scale_agents.agents.health import HealthAgent
from scale_agents.agents.storage import StorageAgent
from scale_agents.agents.quota import QuotaAgent
from scale_agents.agents.performance import PerformanceAgent
from scale_agents.agents.admin import AdminAgent
from scale_agents.config.tool_mappings import AgentType
from scale_agents.core.exceptions import AgentRoutingError
from scale_agents.core.logging import get_logger

logger = get_logger(__name__)


class Intent(str, Enum):
    """Classified user intents."""

    HEALTH = "health"
    STORAGE = "storage"
    QUOTA = "quota"
    PERFORMANCE = "performance"
    ADMIN = "admin"
    HELP = "help"
    UNKNOWN = "unknown"


@dataclass
class IntentClassification:
    """Result of intent classification."""

    intent: Intent
    confidence: float
    keywords_matched: list[str]
    target_agent: AgentType | None
    extracted_params: dict[str, Any] | None = None
    reasoning: str | None = None


# Intent classification patterns
INTENT_PATTERNS: dict[Intent, list[re.Pattern[str]]] = {
    Intent.HEALTH: [
        re.compile(r"\b(health|healthy|unhealthy|status|state|alert|event|events)\b", re.I),
        re.compile(r"\b(monitor|monitoring|diagnostic|diagnostics)\b", re.I),
        re.compile(r"\b(node.*(status|health|state)|cluster.*health)\b", re.I),
        re.compile(r"\b(what.*(wrong|issue|problem)|any.*issue|any.*problem)\b", re.I),
    ],
    Intent.STORAGE: [
        re.compile(r"\b(filesystem|fileset|filesets|mount|unmount)\b", re.I),
        re.compile(r"\b(create|delete|link|unlink).*(fileset|filesystem)\b", re.I),
        re.compile(r"\b(storage.pool|pool)\b", re.I),
        re.compile(r"\b(list|show).*(filesystem|fileset)\b", re.I),
    ],
    Intent.QUOTA: [
        re.compile(r"\b(quota|quotas)\b", re.I),
        re.compile(r"\b(usage|capacity|space|limit)\b", re.I),
        re.compile(r"\b(set|delete|remove).*(quota|limit)\b", re.I),
        re.compile(r"\b(how.much.*(used|space|available))\b", re.I),
    ],
    Intent.PERFORMANCE: [
        re.compile(r"\b(performance|bottleneck|slow|latency|throughput)\b", re.I),
        re.compile(r"\b(iops|bandwidth|io)\b", re.I),
        re.compile(r"\b(analyze|analysis|investigate).*(performance|slow)\b", re.I),
        re.compile(r"\b(why.*(slow|taking|long))\b", re.I),
    ],
    Intent.ADMIN: [
        re.compile(r"\b(snapshot|snapshots)\b", re.I),
        re.compile(r"\b(cluster|remote.cluster|nsd)\b", re.I),
        re.compile(r"\b(start|stop|restart).*(node|nodes|cluster)\b", re.I),
        re.compile(r"\b(add|remove).*(node|cluster)\b", re.I),
        re.compile(r"\b(config|configuration|setting)\b", re.I),
        re.compile(r"\b(authorize|unauthorize|trust)\b", re.I),
    ],
    Intent.HELP: [
        re.compile(r"\b(help|assist|how.do.i|what.can)\b", re.I),
        re.compile(r"\b(capabilities|features|commands)\b", re.I),
    ],
}

# Intent to agent mapping
INTENT_AGENT_MAP: dict[Intent, AgentType] = {
    Intent.HEALTH: AgentType.HEALTH,
    Intent.STORAGE: AgentType.STORAGE,
    Intent.QUOTA: AgentType.QUOTA,
    Intent.PERFORMANCE: AgentType.PERFORMANCE,
    Intent.ADMIN: AgentType.ADMIN,
}


class Orchestrator:
    """Orchestrator for routing requests to specialized agents.

    Handles intent classification and delegates to the appropriate
    domain-specific agent based on the user's request.

    Supports two classification modes:
    - Pattern-based (default): Fast regex matching
    - LLM-powered (optional): Semantic understanding via BeeAI Framework
    """

    def __init__(self, use_llm: bool = False) -> None:
        """Initialize the orchestrator.

        Args:
            use_llm: If True, use LLM-powered reasoning when available.
        """
        self.name = "orchestrator"
        self.description = (
            "Routes requests to appropriate specialized agents based on intent. "
            "Entry point for all Storage Scale operations."
        )
        self.logger = get_logger(f"agent.{self.name}")
        self.use_llm = use_llm

        # Initialize specialized agents
        self.agents: dict[AgentType, BaseScaleAgent] = {
            AgentType.HEALTH: HealthAgent(),
            AgentType.STORAGE: StorageAgent(),
            AgentType.QUOTA: QuotaAgent(),
            AgentType.PERFORMANCE: PerformanceAgent(),
            AgentType.ADMIN: AdminAgent(),
        }

        # Initialize LLM reasoner if requested
        self._reasoner = None
        if use_llm:
            try:
                from scale_agents.core.reasoning import get_reasoner
                self._reasoner = get_reasoner()
                if self._reasoner.enabled:
                    self.logger.info("llm_reasoning_enabled")
                else:
                    self.logger.info("llm_reasoning_not_available")
            except ImportError:
                self.logger.info("llm_reasoning_import_failed")

    async def process(
        self,
        message: Message,
        context_id: str | None = None,
    ) -> str:
        """Process an incoming message by routing to the appropriate agent.

        Args:
            message: The incoming A2A message.
            context_id: Optional conversation context ID.

        Returns:
            Response from the specialized agent.
        """
        from a2a.utils.message import get_message_text

        user_text = get_message_text(message)

        # Classify intent (LLM or pattern-based)
        classification = await self._classify_intent_async(user_text)

        self.logger.info(
            "intent_classified",
            intent=classification.intent.value,
            confidence=classification.confidence,
            keywords=classification.keywords_matched,
            llm_used=self._reasoner is not None and self._reasoner.enabled,
        )

        # Handle special cases
        if classification.intent == Intent.HELP:
            return self._get_help_response()

        if classification.intent == Intent.UNKNOWN:
            if classification.confidence < 0.3:
                return self._get_clarification_prompt(user_text)
            # Fall back to health agent for general queries
            classification = IntentClassification(
                intent=Intent.HEALTH,
                confidence=0.5,
                keywords_matched=["default"],
                target_agent=AgentType.HEALTH,
            )

        # Get target agent
        target_agent_type = INTENT_AGENT_MAP.get(classification.intent)
        if not target_agent_type:
            return self._get_clarification_prompt(user_text)

        agent = self.agents.get(target_agent_type)
        if not agent:
            raise AgentRoutingError(
                f"Agent not available: {target_agent_type}",
                intent=classification.intent.value,
                available_agents=list(self.agents.keys()),
            )

        self.logger.info(
            "routing_to_agent",
            agent=agent.name,
            intent=classification.intent.value,
        )

        # Delegate to specialized agent
        return await agent.process(message, context_id)

    async def _classify_intent_async(self, text: str) -> IntentClassification:
        """Classify intent, optionally using LLM reasoning.

        Args:
            text: User's input text.

        Returns:
            IntentClassification result.
        """
        # Try LLM reasoning if enabled
        if self._reasoner is not None and self._reasoner.enabled:
            try:
                from scale_agents.core.reasoning import ReasoningResult

                result = await self._reasoner.classify_intent(text)

                # Convert ReasoningResult to IntentClassification
                intent_map = {
                    "health": Intent.HEALTH,
                    "storage": Intent.STORAGE,
                    "quota": Intent.QUOTA,
                    "performance": Intent.PERFORMANCE,
                    "admin": Intent.ADMIN,
                    "help": Intent.HELP,
                }
                intent = intent_map.get(result.intent, Intent.UNKNOWN)

                return IntentClassification(
                    intent=intent,
                    confidence=result.confidence,
                    keywords_matched=[],
                    target_agent=result.target_agent,
                    extracted_params=result.extracted_params,
                    reasoning=result.reasoning,
                )
            except Exception as e:
                self.logger.warning("llm_classification_error", error=str(e))

        # Fall back to pattern-based classification
        return self._classify_intent(text)

    def _classify_intent(self, text: str) -> IntentClassification:
        """Classify the intent of user text using pattern matching.

        Args:
            text: User's input text.

        Returns:
            IntentClassification with detected intent and confidence.
        """
        intent_scores: dict[Intent, tuple[float, list[str]]] = {}

        for intent, patterns in INTENT_PATTERNS.items():
            matched_keywords = []
            for pattern in patterns:
                matches = pattern.findall(text)
                if matches:
                    if isinstance(matches[0], tuple):
                        matched_keywords.extend(m for match in matches for m in match if m)
                    else:
                        matched_keywords.extend(matches)

            if matched_keywords:
                # Score based on number and quality of matches
                score = min(1.0, len(matched_keywords) * 0.3)
                intent_scores[intent] = (score, matched_keywords)

        if not intent_scores:
            return IntentClassification(
                intent=Intent.UNKNOWN,
                confidence=0.0,
                keywords_matched=[],
                target_agent=None,
            )

        # Find best match
        best_intent = max(intent_scores, key=lambda i: intent_scores[i][0])
        best_score, best_keywords = intent_scores[best_intent]

        return IntentClassification(
            intent=best_intent,
            confidence=best_score,
            keywords_matched=best_keywords,
            target_agent=INTENT_AGENT_MAP.get(best_intent),
        )

    def _get_help_response(self) -> str:
        """Generate help response listing available capabilities."""
        lines = [
            "**IBM Storage Scale Agent System**",
            "",
            "I can help you with the following:",
            "",
            "**Health Monitoring** (SREs, NOC)",
            "• Check cluster and node health status",
            "• View health events and alerts",
            "• Monitor filesystem health",
            "",
            "**Storage Management** (Storage Admins)",
            "• List and manage filesystems",
            "• Create, delete, link filesets",
            "• Mount/unmount filesystems",
            "• View storage pools",
            "",
            "**Quota Management** (Storage Admins, Project Leads)",
            "• View and set quotas",
            "• Monitor capacity usage",
            "• Delete quotas",
            "",
            "**Performance Analysis** (Performance Engineers)",
            "• Analyze performance bottlenecks",
            "• Review node and filesystem metrics",
            "• Investigate latency issues",
            "",
            "**Administration** (Cluster Admins)",
            "• Manage snapshots",
            "• Start/stop nodes",
            "• Configure cluster settings",
            "• Manage remote clusters and NSDs",
            "",
            "**Example Queries:**",
            "• 'Are there any unhealthy nodes?'",
            "• 'List filesets in filesystem gpfs01'",
            "• 'Set 10TB quota on fileset project-data'",
            "• 'Create snapshot daily-backup in gpfs01'",
            "• 'Analyze performance bottlenecks'",
        ]
        return "\n".join(lines)

    def _get_clarification_prompt(self, text: str) -> str:
        """Generate a clarification prompt when intent is unclear."""
        return (
            "I wasn't sure what you'd like me to help with. "
            "Here are some things I can do:\n\n"
            "• **Health**: Check cluster health, node status, events\n"
            "• **Storage**: Manage filesystems and filesets\n"
            "• **Quota**: Set quotas and check usage\n"
            "• **Performance**: Analyze bottlenecks and metrics\n"
            "• **Admin**: Manage snapshots, nodes, clusters\n\n"
            "Could you please rephrase your request or say 'help' for more details?"
        )


def register_orchestrator(server: Server, use_llm: bool = False) -> None:
    """Register the Orchestrator with an AgentStack server.

    Args:
        server: The AgentStack server instance.
        use_llm: If True, enable LLM-powered reasoning.
    """
    orchestrator = Orchestrator(use_llm=use_llm)

    @server.register(
        name="scale_orchestrator",
        description=orchestrator.description,
    )
    async def orchestrator_handler(context: RunContext, request: AgentMessage) -> str:
        """Handle incoming requests through the orchestrator."""
        message = request.message
        context_id = getattr(context, "context_id", None)
        return await orchestrator.process(message, context_id)
