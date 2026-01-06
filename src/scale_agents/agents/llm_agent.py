"""LLM-powered agent base class.

Extends BaseScaleAgent with BeeAI Framework's RequirementAgent
for enhanced reasoning, tool selection, and multi-step operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from scale_agents.agents.base import BaseScaleAgent
from scale_agents.core.logging import get_logger

if TYPE_CHECKING:
    from a2a.types import Message

    from scale_agents.config.tool_mappings import AgentType

logger = get_logger(__name__)

# Optional BeeAI imports
_HAS_BEEAI = False
try:
    from beeai_framework.agents.requirement.agent import RequirementAgent
    from beeai_framework.backend import ChatModel
    from beeai_framework.memory import UnconstrainedMemory
    from beeai_framework.tools.mcp import McpToolset, StreamableHTTPConnectionParams

    _HAS_BEEAI = True
except ImportError:
    pass


class LLMPoweredAgent(BaseScaleAgent):
    """Agent with LLM-powered reasoning capabilities.

    Extends BaseScaleAgent to use BeeAI Framework's RequirementAgent
    for semantic understanding and intelligent tool selection.

    When LLM is unavailable, falls back to the parent class behavior.
    """

    def __init__(
        self,
        name: str,
        description: str,
        allowed_tools: frozenset[str],
        agent_type: AgentType,
        read_only: bool = True,
        system_prompt: str | None = None,
    ) -> None:
        """Initialize the LLM-powered agent.

        Args:
            name: Agent name.
            description: Agent description.
            allowed_tools: Set of allowed MCP tool names.
            agent_type: The agent type for tool filtering.
            read_only: If True, block destructive operations.
            system_prompt: Optional custom system prompt for the LLM.
        """
        super().__init__(name, description, allowed_tools, read_only)

        self.agent_type = agent_type
        self.system_prompt = system_prompt or self._default_system_prompt()

        self._llm_agent: Any = None
        self._mcp_tools: list[Any] = []
        self._llm_enabled = False

        self._setup_llm()

    def _default_system_prompt(self) -> str:
        """Generate default system prompt for this agent."""
        return f"""You are an IBM Storage Scale {self.name} agent.

Your role: {self.description}

You have access to the following tools:
{chr(10).join(f'- {t}' for t in sorted(self.allowed_tools))}

Guidelines:
1. Use tools to gather information before making conclusions
2. Be concise and precise in your responses
3. If an operation requires confirmation, explain what will happen
4. Report errors clearly with context

When responding:
- Format output for readability
- Include relevant metrics and status indicators
- Suggest next steps when appropriate
"""

    def _setup_llm(self) -> None:
        """Setup the LLM agent with MCP tools."""
        if not _HAS_BEEAI:
            self.logger.debug("beeai_not_available")
            return

        from scale_agents.config.settings import settings

        if not settings.llm_provider or not settings.llm_model:
            self.logger.debug("llm_not_configured")
            return

        try:
            # Initialize chat model
            if settings.llm_provider == "ollama":
                model = ChatModel.from_name(
                    f"ollama:{settings.llm_model}",
                    options={"base_url": settings.llm_base_url or "http://localhost:11434"},
                )
            elif settings.llm_provider == "openai":
                model = ChatModel.from_name(
                    f"openai:{settings.llm_model}",
                    options={"api_key": settings.llm_api_key},
                )
            elif settings.llm_provider == "anthropic":
                model = ChatModel.from_name(
                    f"anthropic:{settings.llm_model}",
                    options={"api_key": settings.llm_api_key},
                )
            else:
                self.logger.warning("unknown_llm_provider", provider=settings.llm_provider)
                return

            # Create RequirementAgent (tools will be added lazily)
            self._llm_agent = RequirementAgent(
                llm=model,
                memory=UnconstrainedMemory(),
            )

            self._llm_enabled = True
            self.logger.info("llm_agent_initialized", provider=settings.llm_provider)

        except Exception as e:
            self.logger.error("llm_setup_failed", error=str(e))

    async def _get_mcp_tools(self) -> list[Any]:
        """Get filtered MCP tools for this agent.

        Returns:
            List of MCP tools filtered to this agent's whitelist.
        """
        if self._mcp_tools:
            return self._mcp_tools

        if not _HAS_BEEAI:
            return []

        from scale_agents.config.settings import settings

        try:
            toolset = McpToolset(
                StreamableHTTPConnectionParams(url=settings.mcp_server_url)
            )

            # Get all tools and filter
            all_tools = await toolset.get_tools()
            self._mcp_tools = [
                tool for tool in all_tools
                if tool.name in self.allowed_tools
            ]

            self.logger.debug(
                "mcp_tools_loaded",
                total=len(all_tools),
                filtered=len(self._mcp_tools),
            )

            return self._mcp_tools

        except Exception as e:
            self.logger.error("mcp_tools_load_failed", error=str(e))
            return []

    async def process_with_llm(
        self,
        query: str,
        context_id: str | None = None,
    ) -> str:
        """Process a query using LLM reasoning.

        Args:
            query: The user's query.
            context_id: Optional conversation context.

        Returns:
            The agent's response.
        """
        if not self._llm_enabled or self._llm_agent is None:
            raise RuntimeError("LLM agent not available")

        # Get filtered MCP tools
        tools = await self._get_mcp_tools()

        # Update agent with tools
        self._llm_agent.tools = tools

        # Build prompt with system context
        full_prompt = f"""{self.system_prompt}

User Query: {query}

Analyze the query and use the appropriate tools to respond.
If tools return errors, explain them clearly.
Format your response for easy reading."""

        try:
            response = await self._llm_agent.run(prompt=full_prompt)
            return response.result.text

        except Exception as e:
            self.logger.error("llm_processing_failed", error=str(e))
            raise

    async def process(
        self,
        message: Message,
        context_id: str | None = None,
    ) -> str:
        """Process an incoming message.

        Uses LLM reasoning if available, otherwise falls back
        to the parent class implementation.

        Args:
            message: The incoming message.
            context_id: Optional conversation context.

        Returns:
            The agent's response.
        """
        if self._llm_enabled:
            try:
                user_text = self.get_user_text(message)
                return await self.process_with_llm(user_text, context_id)
            except Exception as e:
                self.logger.warning(
                    "llm_fallback",
                    error=str(e),
                    reason="Falling back to pattern-based processing",
                )

        # Must be implemented by subclass if LLM is not used
        raise NotImplementedError(
            "Subclass must implement process() for non-LLM mode"
        )

    @property
    def llm_enabled(self) -> bool:
        """Check if LLM reasoning is enabled."""
        return self._llm_enabled
