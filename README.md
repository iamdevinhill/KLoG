# KG Log

A knowledge graph note-taking app with a 3D graph view, multi-provider AI assistant, and WebXR VR mode. Built with FastAPI, Neo4j, and vanilla JS.

Inspired by [Logseq](https://github.com/logseq/logseq), an open-source knowledge management tool licensed under AGPL-3.0.

## Features

- **Block-based editor** — bullet-style blocks with `[[wikilinks]]` that auto-create linked pages
- **Daily journal** — auto-creates a page for today's date
- **Search** — fulltext search across all your pages
- **Backlinks** — see which pages link to the current page
- **3D graph view** — interactive force-directed graph using Three.js with glowing nodes and orbit controls
- **AI assistant** — streaming chat with context from your notes; supports Ollama, OpenAI, and Anthropic
- **WebXR VR mode** — explore your knowledge graph in VR with controller raycasting
- **User accounts** — signup/login with JWT auth; each user's pages are isolated
- **Bulk delete** — multi-select pages in the sidebar and delete them in one action
- **Onboarding guide** — interactive walkthrough shown to new users on first login

## Quick Start (Docker)

```bash
# Clone the repo
git clone https://github.com/iamdevinhill/kg_log.git && cd kg_log

# Copy and configure environment
cp .env.example .env
# Edit .env — at minimum, change JWT_SECRET and NEO4J_PASSWORD

# Start the stack
docker compose up -d --build

# Open in browser
open http://localhost:8000
```

The app will wait for Neo4j to be ready before starting.

## Configuration

Copy `.env.example` to `.env` and configure:

| Variable | Default | Description |
|---|---|---|
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j connection URI |
| `NEO4J_USER` | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | `neo4jpassword` | Neo4j database password |
| `JWT_SECRET` | *(must change)* | Secret key for JWT token signing |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API URL |
| `CORS_ORIGINS` | `*` | Comma-separated allowed CORS origins |

> **Important:** Always set a strong, unique `JWT_SECRET` before deploying. The app will log a warning if the default value is detected.

## Development (without Docker)

```bash
# Prerequisites: Python 3.12+, Neo4j 5+

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env  # edit with your Neo4j credentials

# Run the server
uvicorn main:app --reload --port 8000
```

### Running Tests

```bash
pytest tests/ -v
```

## AI Assistant

The built-in AI assistant uses your notes as context when answering questions. Choose a provider from the settings panel inside the app.

### Ollama (Local)

Run models locally with no API key required. The app auto-detects models you have installed.

```bash
# Install Ollama: https://ollama.com
ollama pull qwen3:8b
```

When running via Docker, the app reaches Ollama on your host machine through `host.docker.internal`. Override with the `OLLAMA_BASE_URL` env variable if needed.

### OpenAI (ChatGPT)

Use any OpenAI chat model (e.g. `gpt-4o`, `gpt-4o-mini`). Enter your API key in the settings panel.

Get an API key at [platform.openai.com/api-keys](https://platform.openai.com/api-keys).

### Anthropic (Claude)

Use any Anthropic model (e.g. `claude-sonnet-4-5-20250929`). Enter your API key in the settings panel.

Get an API key at [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys).

> API keys are stored in your browser's localStorage and sent directly to the provider — they are never saved on the server.

## API Endpoints

### Health

- `GET /health` — health check (returns Neo4j connectivity status)

### Auth

- `POST /signup` — create account (JSON: `username`, `password`)
- `POST /login` — get JWT token (JSON: `username`, `password`)

### Pages (requires `Authorization: Bearer <token>`)

- `GET /pages` — list all pages
- `GET /pages/{title}` — get a single page with links and backlinks
- `POST /pages` — create a page (JSON: `title`, `content`)
- `PUT /pages/{title}` — update a page (JSON: `content`)
- `DELETE /pages/{title}` — delete a page
- `POST /pages/bulk-delete` — delete multiple pages (JSON: `titles`)

### Graph

- `GET /graph` — get all nodes and edges for the graph view

### AI

- `POST /ask` — streaming AI response (JSON: `question`, `provider`, `model`, `api_key`)
- `GET /ollama/models` — list locally available Ollama models

## Architecture

```
app/
  config.py      — environment variables and configuration
  database.py    — Neo4j driver management
  auth.py        — JWT authentication helpers
  models.py      — Pydantic request/response models
  pages.py       — page CRUD routes and wikilink parsing
  graph.py       — knowledge graph routes
  ai.py          — multi-provider AI streaming routes
main.py          — FastAPI app setup, lifespan, auth endpoints
static/index.html — single-file frontend (editor, graph, AI panel, VR)
tests/           — test suite
Dockerfile       — Python 3.12 slim image with non-root user
docker-compose.yml — app + Neo4j stack
```

### Neo4j Schema

- `(:User {username, password})` — user accounts
- `(:Page {title, content, createdAt, updatedAt})` — note pages
- `(:User)-[:OWNS]->(:Page)` — ownership
- `(:Page)-[:LINKS_TO]->(:Page)` — wikilink connections

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## License

This project is licensed under the [GNU Affero General Public License v3.0](LICENSE).

KG Log is inspired by [Logseq](https://github.com/logseq/logseq), which is also licensed under AGPL-3.0.
