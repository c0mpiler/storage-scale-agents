# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-01-06

### Added

- Initial release of IBM Storage Scale AI Agents
- Orchestrator agent for intent classification and routing
- Health agent for monitoring and diagnostics
- Storage agent for filesystem and fileset management
- Quota agent for capacity management
- Performance agent for bottleneck analysis
- Admin agent for cluster administration
- MCP client for communication with scale-mcp-server
- Confirmation gates for destructive operations
- Tool whitelisting per agent
- Structured logging with JSON support
- Docker and docker-compose deployment
- Comprehensive test suite

### Security

- Tool whitelisting enforces least privilege per agent
- Confirmation required for all destructive operations
- High-risk operations flagged with explicit warnings
- Domain isolation for multi-tenant deployments
