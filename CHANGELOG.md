# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- AGPL-3.0 license
- Contributing guide, code of conduct, and issue/PR templates
- Health check endpoint (`GET /health`)
- GitHub Actions CI (tests, lint, Docker build)
- Configurable CORS origins via `CORS_ORIGINS` env variable
- Warning when JWT_SECRET is set to a default value
- Dockerfile improvements: non-root user, healthcheck
- Test suite for auth, models, config, and wikilink parsing

### Changed

- Refactored `main.py` into modular `app/` package (config, database, auth, models, pages, graph, ai)
- Removed hardcoded `.env` from repository; added `.env.example` template

## [0.1.0] - 2025-02-20

### Added

- Initial release
- User authentication (signup/login with JWT)
- Page CRUD with `[[wikilink]]` support and backlinks
- 3D knowledge graph visualization (Three.js)
- AI assistant with streaming support (Ollama, OpenAI, Anthropic)
- WebXR VR mode
- Fulltext search via Neo4j
- Docker Compose deployment
