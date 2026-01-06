"""LLM-powered reasoning layer using BeeAI Framework.

This module provides enhanced reasoning capabilities using RequirementAgent
for intent classification, parameter extraction, and multi-step planning.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scale_agents.config.settings import get_settings
from scale_agents.config.tool_mappings import (
    ADMIN_TOOLS,
    HEALTH_TOOLS,
    PERFORMANCE_TOOLS,
    QUOTA_TOOLS,
    STORAGE_TOOLS,
    AgentType,
)
from scale_agents.core.logging import get_logger

logger = get_logger(__name__)

# Optional imports for LLM reasoning
_HAS_BEEAI = False
try:
    from beeai_framework.agents.requirement.agent import RequirementAgent
    from beeai_framework.backend import ChatModel
    from beeai_framework.memory import UnconstrainedMemory
    from beeai_framework.tools.mcp import McpToolset, StreamableHTTPConnectionParams

    _HAS_BEEAI = True
except ImportError:
    logger.debug("beeai_framework not installed; LLM reasoning disabled")


@dataclass
class ReasoningResult:
    """Result from LLM reasoning."""

    intent: str
    target_agent: AgentType | None
    extracted_params: dict[str, Any]
    reasoning: str
    confidence: float
    suggested_tools: list[str]


# System prompts for different reasoning tasks
INTENT_CLASSIFICATION_PROMPT = """You are an intent classifier for IBM Storage Scale operations.

Given a user query, determine which specialized agent should handle it:

AGENTS:
- health: Monitoring, diagnostics, node/cluster health status, events, alerts
- storage: Filesystem management, fileset operations, mount/unmount, storage pools
- quota: Quota management, capacity usage, space limits
- performance: Performance analysis, bottleneck detection, latency, throughput
- admin: Cluster administration, snapshots, node lifecycle, remote clusters, NSDs

Respond with JSON only, no other text:
{
    "intent": "<agent_name>",
    "confidence": <0.0-1.0>,
    "reasoning": "<brief explanation>",
    "extracted_params": {
        "filesystem": "<if mentioned>",
        "fileset": "<if mentioned>",
        "node": "<if mentioned>",
        "snapshot": "<if mentioned>",
        "quota_value": "<if mentioned>"
    }
}
"""

TOOL_SELECTION_PROMPT = """You are a tool selector for IBM Storage Scale operations.

Given a user query and available tools, determine which tool(s) to call and with what parameters.

Available tools for {agent_type} agent:
{tools_list}

User query: {query}

Respond with JSON only, no other text:
{
    "tools": [
        {
            "name": "<tool_name>",
            "arguments": { ... },
            "reason": "<why this tool>"
        }
    ],
    "execution_order": "sequential" | "parallel",
    "requires_confirmation": true | false
}
"""


class LLMReasoner:
    """LLM-powered reasoning for enhanced agent capabilities.

    Uses BeeAI Framework's RequirementAgent for:
    - Intent classification with semantic understanding
    - Parameter extraction from natural language
    - Multi-step operation planning
    - Tool selection and orchestration
    """

    def __init__(self) -> None:
        """Initialize the LLM reasoner."""
        self._enabled = False
        self._model: Any = None
        self._mcp_toolset: Any = None
        self._settings = get_settings()

        if not _HAS_BEEAI:
            logger.info("llm_reasoning_disabled", reason="beeai_framework not installed")
            return

        if not self._settings.llm.enabled:
            logger.info("llm_reasoning_disabled", reason="LLM disabled in config")
            return

        if not self._settings.llm.provider or not self._settings.llm.model:
            logger.info("llm_reasoning_disabled", reason="LLM provider/model not configured")
            return

        self._setup_model()

    def _setup_model(self) -> None:
        """Setup the LLM model and MCP toolset."""
        try:
            llm_config = self._settings.llm

            # Configure the chat model based on provider
            if llm_config.provider == "ollama":
                base_url = llm_config.base_url or "http://localhost:11434"
                self._model = ChatModel.from_name(
                    f"ollama:{llm_config.model}",
                    options={
                        "base_url": base_url,
                        "temperature": llm_config.temperature,
                        "num_predict": llm_config.max_tokens,
                    },
                )
                logger.info(
                    "ollama_model_configured",
                    model=llm_config.model,
                    base_url=base_url,
                )
            elif llm_config.provider == "openai":
                self._model = ChatModel.from_name(
                    f"openai:{llm_config.model}",
                    options={
                        "api_key": llm_config.api_key,
                        "temperature": llm_config.temperature,
                        "max_tokens": llm_config.max_tokens,
                    },
                )
            elif llm_config.provider == "anthropic":
                self._model = ChatModel.from_name(
                    f"anthropic:{llm_config.model}",
                    options={
                        "api_key": llm_config.api_key,
                        "temperature": llm_config.temperature,
                        "max_tokens": llm_config.max_tokens,
                    },
                )
            else:
                logger.warning("unknown_llm_provider", provider=llm_config.provider)
                return

            # Setup MCP toolset connection
            self._mcp_toolset = McpToolset(
                StreamableHTTPConnectionParams(url=self._settings.mcp.server_url)
            )

            self._enabled = True
            logger.info(
                "llm_reasoning_enabled",
                provider=llm_config.provider,
                model=llm_config.model,
            )

        except Exception as e:
            logger.error("llm_setup_failed", error=str(e))
            self._enabled = False

    @property
    def enabled(self) -> bool:
        """Check if LLM reasoning is enabled."""
        return self._enabled

    async def classify_intent(self, query: str) -> ReasoningResult:
        """Classify user intent using LLM reasoning.

        Args:
            query: The user's natural language query.

        Returns:
            ReasoningResult with classified intent and extracted parameters.
        """
        if not self._enabled:
            return self._fallback_classification(query)

        try:
            agent = RequirementAgent(
                llm=self._model,
                memory=UnconstrainedMemory(),
            )

            response = await agent.run(
                prompt=f"{INTENT_CLASSIFICATION_PROMPT}\n\nUser query: {query}",
            )

            # Parse the JSON response
            import orjson

            result_text = response.result.text
            # Extract JSON from response (handle potential markdown code blocks)
            if "```json" in result_text:
                json_start = result_text.find("```json") + 7
                json_end = result_text.find("```", json_start)
                result_text = result_text[json_start:json_end].strip()
            elif "```" in result_text:
                json_start = result_text.find("```") + 3
                json_end = result_text.find("```", json_start)
                result_text = result_text[json_start:json_end].strip()

            json_start = result_text.find("{")
            json_end = result_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                parsed = orjson.loads(result_text[json_start:json_end])

                intent = parsed.get("intent", "unknown")
                agent_map = {
                    "health": AgentType.HEALTH,
                    "storage": AgentType.STORAGE,
                    "quota": AgentType.QUOTA,
                    "performance": AgentType.PERFORMANCE,
                    "admin": AgentType.ADMIN,
                }

                return ReasoningResult(
                    intent=intent,
                    target_agent=agent_map.get(intent),
                    extracted_params=parsed.get("extracted_params", {}),
                    reasoning=parsed.get("reasoning", ""),
                    confidence=parsed.get("confidence", 0.8),
                    suggested_tools=[],
                )

        except Exception as e:
            logger.warning("llm_classification_failed", error=str(e))

        return self._fallback_classification(query)

    async def select_tools(
        self,
        query: str,
        agent_type: AgentType,
    ) -> list[dict[str, Any]]:
        """Select appropriate tools for a query using LLM reasoning.

        Args:
            query: The user's query.
            agent_type: The target agent type.

        Returns:
            List of tool selections with arguments.
        """
        if not self._enabled:
            return []

        # Get tools for this agent
        tools_map = {
            AgentType.HEALTH: HEALTH_TOOLS,
            AgentType.STORAGE: STORAGE_TOOLS,
            AgentType.QUOTA: QUOTA_TOOLS,
            AgentType.PERFORMANCE: PERFORMANCE_TOOLS,
            AgentType.ADMIN: ADMIN_TOOLS,
        }
        available_tools = tools_map.get(agent_type, frozenset())
        tools_list = "\n".join(f"- {t}" for t in sorted(available_tools))

        try:
            agent = RequirementAgent(
                llm=self._model,
                memory=UnconstrainedMemory(),
            )

            prompt = TOOL_SELECTION_PROMPT.format(
                agent_type=agent_type.value,
                tools_list=tools_list,
                query=query,
            )

            response = await agent.run(prompt=prompt)

            # Parse JSON response
            import orjson

            result_text = response.result.text

            # Handle markdown code blocks
            if "```json" in result_text:
                json_start = result_text.find("```json") + 7
                json_end = result_text.find("```", json_start)
                result_text = result_text[json_start:json_end].strip()
            elif "```" in result_text:
                json_start = result_text.find("```") + 3
                json_end = result_text.find("```", json_start)
                result_text = result_text[json_start:json_end].strip()

            json_start = result_text.find("{")
            json_end = result_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                parsed = orjson.loads(result_text[json_start:json_end])
                return parsed.get("tools", [])

        except Exception as e:
            logger.warning("llm_tool_selection_failed", error=str(e))

        return []

    async def plan_operation(
        self,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Plan a multi-step operation using LLM reasoning.

        Args:
            query: The user's query.
            context: Optional context from previous operations.

        Returns:
            List of operation steps with tool calls.
        """
        if not self._enabled:
            return []

        try:
            # Use RequirementAgent with MCP tools for planning
            tools = await self._mcp_toolset.get_tools()

            agent = RequirementAgent(
                llm=self._model,
                tools=tools,
                memory=UnconstrainedMemory(),
            )

            planning_prompt = f"""Plan the following Storage Scale operation:

Query: {query}

Context: {context or 'None'}

Create a step-by-step plan using the available MCP tools.
For each step, specify:
1. The tool to call
2. The arguments
3. What to do with the result
4. Whether user confirmation is needed

Respond with a JSON array of steps."""

            response = await agent.run(prompt=planning_prompt)

            import orjson

            result_text = response.result.text
            json_start = result_text.find("[")
            json_end = result_text.rfind("]") + 1
            if json_start >= 0 and json_end > json_start:
                return orjson.loads(result_text[json_start:json_end])

        except Exception as e:
            logger.warning("llm_planning_failed", error=str(e))

        return []

    def _fallback_classification(self, query: str) -> ReasoningResult:
        """Fallback to pattern-based classification when LLM is unavailable."""
        from scale_agents.agents.orchestrator import Orchestrator

        orchestrator = Orchestrator()
        classification = orchestrator._classify_intent(query)

        return ReasoningResult(
            intent=classification.intent.value,
            target_agent=classification.target_agent,
            extracted_params={},
            reasoning="Pattern-based classification (LLM unavailable)",
            confidence=classification.confidence,
            suggested_tools=[],
        )


# Global reasoner instance
_reasoner: LLMReasoner | None = None


def get_reasoner() -> LLMReasoner:
    """Get the global LLM reasoner instance."""
    global _reasoner
    if _reasoner is None:
        _reasoner = LLMReasoner()
    return _reasoner


async def classify_with_llm(query: str) -> ReasoningResult:
    """Classify intent using LLM reasoning.

    Convenience function for direct usage.

    Args:
        query: The user's query.

    Returns:
        ReasoningResult with classification.
    """
    reasoner = get_reasoner()
    return await reasoner.classify_intent(query)


async def select_tools_with_llm(
    query: str,
    agent_type: AgentType,
) -> list[dict[str, Any]]:
    """Select tools using LLM reasoning.

    Args:
        query: The user's query.
        agent_type: Target agent type.

    Returns:
        List of tool selections.
    """
    reasoner = get_reasoner()
    return await reasoner.select_tools(query, agent_type)
