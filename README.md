# IBM Storage Scale AI Agents

Multi-agent system for IBM Storage Scale administration built on [BeeAI AgentStack](https://agentstack.beeai.dev).

## Overview

Scale Agents provides an intelligent, conversational interface to IBM Storage Scale cluster management. It uses a hierarchical multi-agent architecture where an orchestrator routes natural language requests to specialized domain agents, each with access to specific MCP (Model Context Protocol) tools.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AGENTSTACK PLATFORM LAYER                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     ORCHESTRATOR AGENT (Router)                      │   │
│  │  - Intent classification (pattern or LLM)                           │   │
│  │  - Persona detection                                                │   │
│  │  - Agent dispatch                                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│         ┌──────────────┬───────────┼───────────┬──────────────┐            │
│         ▼              ▼           ▼           ▼              ▼            │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────┐ │
│  │   Health   │ │  Storage   │ │   Quota    │ │Performance │ │  Admin   │ │
│  │   Agent    │ │   Agent    │ │   Agent    │ │   Agent    │ │  Agent   │ │
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

## Agents

| Agent | Purpose | Persona | Tools |
|-------|---------|---------|-------|
| **Orchestrator** | Intent classification and routing | All users | N/A |
| **Health** | Monitoring, diagnostics, alerting | SREs, NOC | 9 read-only tools |
| **Storage** | Filesystem/fileset lifecycle | Storage Admins | 15 tools |
| **Quota** | Capacity governance | Storage Admins, Project Leads | 4 tools |
| **Performance** | Bottleneck analysis | Performance Engineers | 10 read-only tools |
| **Admin** | Cluster topology, snapshots | Cluster Administrators | 40+ tools |

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Running instance of [scale-mcp-server](https://github.ibm.com/HPC-POCs/scale-mcp-server)
- (Optional) Ollama with a function-calling model for LLM reasoning

## Installation

```bash
cd scale-agents
uv venv
source .venv/bin/activate

# Basic installation (pattern-based routing)
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
  server_url: "http://your-mcp-server:8000/mcp"
  timeout: 60.0
  domain: "StorageScaleDomain"

# LLM Reasoning (optional)
llm:
  enabled: true
  provider: "ollama"
  model: "qwen3:30b-a3b"
  base_url: "http://localhost:11434"

# Server Settings
server:
  host: "0.0.0.0"
  port: 8080

# Security
security:
  require_confirmation: true
  confirmation_timeout: 300

# Logging
logging:
  level: "INFO"
  format: "json"

# Per-agent configuration
agents:
  health:
    enabled: true
  storage:
    enabled: true
  quota:
    enabled: true
  performance:
    enabled: true
  admin:
    enabled: true
```

### Environment Variables

Environment variables use the format `SCALE_AGENTS_<SECTION>_<KEY>`:

```bash
# MCP Server
export SCALE_AGENTS_MCP_SERVER_URL=http://localhost:8000/mcp

# LLM
export SCALE_AGENTS_LLM_ENABLED=true
export SCALE_AGENTS_LLM_PROVIDER=ollama
export SCALE_AGENTS_LLM_MODEL=qwen3:30b-a3b

# Server
export SCALE_AGENTS_HOST=0.0.0.0
export SCALE_AGENTS_PORT=8080
```

## Usage

### Start the Agent Server

```bash
# Use config.yaml in current directory
uv run server

# Specify custom config path
SCALE_AGENTS_CONFIG=/path/to/config.yaml uv run server

# Or directly via Python
python -m scale_agents.server
```

### Via AgentStack

```bash
# Add agents to AgentStack (GitHub URL)
agentstack add https://github.ibm.com/HPC-POCs/scale-agents

# Run orchestrator (auto-routes to appropriate agent)
agentstack run scale_orchestrator "What is the health status of all nodes?"

# Direct agent access
agentstack run health_agent "Show filesystem health for gpfs01"
agentstack run storage_agent "List filesets in filesystem scratch"
agentstack run quota_agent "What is the usage of fileset user-homes?"
agentstack run admin_agent "Create snapshot daily-backup in filesystem gpfs01"
```

### Example Queries

**Health Monitoring:**
```
"Are there any unhealthy nodes?"
"Show me cluster health status"
"What filesystem alerts are active?"
```

**Storage Management:**
```
"List all filesystems"
"Create fileset project-data in gpfs01"
"Mount filesystem scratch on node3"
```

**Quota Management:**
```
"Set 10TB quota on fileset user-homes"
"Show usage for fileset project-x"
"List quotas exceeding 80%"
```

**Administration:**
```
"Create snapshot daily-backup in gpfs01"
"List all snapshots"
"Show cluster configuration"
```

## LLM Reasoning

When LLM mode is enabled via BeeAI Framework's RequirementAgent, agents gain enhanced capabilities:

| Feature | Pattern Mode | LLM Mode |
|---------|--------------|----------|
| Intent Classification | Regex patterns | Semantic understanding |
| Parameter Extraction | Keyword matching | Natural language parsing |
| Multi-step Planning | Not supported | RequirementAgent chains |
| Ambiguity Handling | Fails | Clarifying questions |
| Complex Queries | Limited | Full support |

Example of LLM advantage:
```
Query: "The project-x fileset is almost full, increase the quota to handle next quarter's data growth"

Pattern Mode: May fail to extract parameters
LLM Mode: Extracts fileset=project-x, understands quota increase intent, can ask for specific limit
```

## Deployment

### Docker

```bash
# Build
docker build -t scale-agents:latest .

# Run with docker-compose
docker-compose up -d

# View logs
docker-compose logs -f
```

### AgentStack UI

1. Push to GitHub repository
2. In AgentStack UI, click "Add new agent"
3. Select "Github repository URL"
4. Enter: `https://github.ibm.com/HPC-POCs/scale-agents`

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for detailed deployment instructions.

## Development

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=scale_agents --cov-report=html

# Type checking
mypy src/

# Linting
ruff check src/
ruff format src/

# Pre-commit hooks
pre-commit install
```

See [docs/TESTING.md](docs/TESTING.md) for testing guide.

## Security

- **Tool Whitelisting**: Each agent restricted to specific tool subset (least privilege)
- **Confirmation Gates**: 35 destructive operations require explicit confirmation
- **Risk Levels**: HIGH (13 tools), MEDIUM (22 tools), LOW classification
- **Read-only Agents**: Health and Performance agents have no write access
- **Domain Isolation**: Storage Scale domain header for multi-tenancy
- **Audit Trail**: Structured JSON logging with operation tracking

## Project Structure

```
scale-agents/
├── src/scale_agents/
│   ├── agents/
│   │   ├── base.py           # Base agent class with tool whitelisting
│   │   ├── llm_agent.py      # LLM-powered agent base
│   │   ├── orchestrator.py   # Intent router (pattern + LLM)
│   │   ├── health.py         # Health monitoring (read-only)
│   │   ├── storage.py        # Storage management
│   │   ├── quota.py          # Quota management
│   │   ├── performance.py    # Performance analysis (read-only)
│   │   └── admin.py          # Cluster administration
│   ├── config/
│   │   ├── settings.py       # YAML + env configuration
│   │   └── tool_mappings.py  # Tool whitelists and risk levels
│   ├── core/
│   │   ├── exceptions.py     # Custom exceptions
│   │   ├── logging.py        # Structured logging
│   │   └── reasoning.py      # LLM reasoning layer
│   ├── tools/
│   │   ├── mcp_client.py     # Async MCP client
│   │   ├── confirmable.py    # Confirmation gate system
│   │   └── response_formatter.py
│   └── server.py             # AgentStack server entry point
├── tests/                    # Unit and integration tests
├── docs/                     # Documentation
├── agent.yaml                # AgentStack manifest
├── config.yaml               # Configuration file
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

## Related Projects

- [scale-mcp-server](https://github.ibm.com/HPC-POCs/scale-mcp-server): MCP server for Storage Scale REST API
- [BeeAI AgentStack](https://agentstack.beeai.dev): Agent hosting platform
- [BeeAI Framework](https://github.com/i-am-bee/beeai-framework): LLM agent framework

## License

Apache 2.0
