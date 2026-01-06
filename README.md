# IBM Storage Scale AI Agents

AI agent for IBM Storage Scale administration built on [BeeAI AgentStack](https://agentstack.beeai.dev).

## Overview

Scale Agents provides an intelligent, conversational interface to IBM Storage Scale cluster management. It uses a single unified agent that routes natural language requests to specialized internal handlers, each with access to specific MCP (Model Context Protocol) tools.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AGENTSTACK PLATFORM LAYER                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     SCALE_AGENT (Single Entry Point)                 │   │
│  │  - Intent classification (pattern or LLM)                           │   │
│  │  - Internal routing to specialized handlers                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│         ┌──────────────┬───────────┼───────────┬──────────────┐            │
│         ▼              ▼           ▼           ▼              ▼            │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────┐ │
│  │   Health   │ │  Storage   │ │   Quota    │ │Performance │ │  Admin   │ │
│  │  Handler   │ │  Handler   │ │  Handler   │ │  Handler   │ │ Handler  │ │
│  │ (internal) │ │ (internal) │ │ (internal) │ │ (internal) │ │(internal)│ │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘ └──────────┘ │
│         │              │           │           │              │            │
│  ┌──────┴──────────────┴───────────┴───────────┴──────────────┴──────┐    │
│  │                     MCP TOOL INTEGRATION LAYER                     │    │
│  │            (Optional: BeeAI Framework RequirementAgent)            │    │
│  └────────────────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        SCALE-MCP-SERVER (FastMCP)                           │
│  HTTP Transport @ :8000/mcp                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    IBM STORAGE SCALE REST API (v2/v3)                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Internal Handlers

The single `scale_agent` automatically routes requests to specialized internal handlers:

| Handler | Purpose | Example Queries |
|---------|---------|-----------------|
| **Health** | Monitoring, diagnostics, alerting | "Show cluster health", "List node events" |
| **Storage** | Filesystem/fileset lifecycle | "List filesystems", "Create fileset data01" |
| **Quota** | Capacity governance | "Check quota for project01", "Set quota limit" |
| **Performance** | Bottleneck analysis | "Analyze performance", "Show throughput metrics" |
| **Admin** | Cluster topology, snapshots | "Create snapshot", "Add remote cluster" |

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Running instance of [scale-mcp-server](https://github.ibm.com/HPC-POCs/scale-mcp-server)
- (Optional) Ollama with a function calling model for LLM reasoning

## Installation

```bash
cd scale-agents
uv venv
source .venv/bin/activate

# Basic installation (pattern based routing)
uv pip install -e .

# With LLM reasoning support
uv pip install -e ".[llm]"

# Full development setup
uv pip install -e ".[all]"
```

## Configuration

Scale Agents uses a hierarchical configuration system:

1. `config.yaml` (primary configuration file)
2. Environment variables (override YAML settings)
3. Default values

### Configuration File

Copy the template and customize:

```bash
cp config.yaml.template config.yaml
```

Edit `config.yaml`:

```yaml
# MCP Server Connection
mcp:
  server_url: "http://localhost:8000/mcp"

# LLM Configuration (optional)
llm:
  enabled: false
  provider: "ollama"
  model: "qwen3:30b-a3b"
  base_url: "http://localhost:11434"

# Server Configuration
server:
  host: "0.0.0.0"
  port: 8080
```

### Environment Variables

Override any setting with environment variables:

```bash
export SCALE_AGENTS_MCP_SERVER_URL="http://scale-mcp:8000/mcp"
export SCALE_AGENTS_LLM_ENABLED="true"
export SCALE_AGENTS_LLM_PROVIDER="ollama"
export SCALE_AGENTS_LLM_MODEL="qwen3:30b-a3b"
```

## Running

### Standalone Server

```bash
# Using the module
python -m scale_agents.server

# Or using the run function
python -c "from scale_agents import run; run()"
```

### With AgentStack

```bash
# Add to AgentStack
agentstack add /path/to/scale-agents

# List registered agents
agentstack list

# Run the agent
agentstack run scale_agent "Show cluster health"
```

### Docker

```bash
# Build
docker build -t scale-agents:latest .

# Run
docker run -p 8080:8080 \
  -e SCALE_AGENTS_MCP_SERVER_URL=http://scale-mcp:8000/mcp \
  scale-agents:latest
```

## Usage Examples

```text
User: Show cluster health
Agent: [Routes to Health handler] -> Returns health overview

User: List all filesystems
Agent: [Routes to Storage handler] -> Returns filesystem list

User: What's the quota for fileset data01?
Agent: [Routes to Quota handler] -> Returns quota information

User: Analyze performance bottlenecks
Agent: [Routes to Performance handler] -> Returns performance analysis

User: Create a snapshot of fs01
Agent: [Routes to Admin handler] -> Creates snapshot
```

## AgentStack Architecture Note

AgentStack SDK only supports one agent per server instance. Scale Agents implements this constraint by exposing a single `scale_agent` that internally routes to specialized handlers based on intent classification.

## License

Apache 2.0
