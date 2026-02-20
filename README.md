# KG Log

A knowledge graph note-taking app with a 3D graph view, multi-provider AI assistant, and WebXR VR mode. Built with FastAPI, Neo4j, and vanilla JS.

## Features

- **Block-based editor** — bullet-style blocks with `[[wikilinks]]` that auto-create linked pages
- **Daily journal** — auto-creates a page for today's date
- **Search** — fulltext search across all your pages
- **Backlinks** — see which pages link to the current page
- **3D graph view** — interactive force-directed graph using Three.js with glowing nodes and orbit controls
- **AI assistant** — streaming chat with context from your notes; supports Ollama, OpenAI, and Anthropic
- **WebXR VR mode** — explore your knowledge graph in VR with controller raycasting
- **User accounts** — signup/login with JWT auth; each user's pages are isolated

## Quick Start (Docker)

```bash
# Clone the repo
git clone https://github.com/iamdevinhill/kg_log.git && cd kg_log

# Start the stack
docker compose up -d --build

# Open in browser
open http://localhost:8000
```

The app will wait for Neo4j to be ready before starting.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `NEO4J_PASSWORD` | `neo4jpassword` | Neo4j database password |
| `JWT_SECRET` | `change_me_in_production` | Secret key for JWT token signing |
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | Ollama API URL (auto-resolves to host in Docker) |

Set these in a `.env` file or export them before running `docker compose up`.

## Development (without Docker)

```bash
# Prerequisites: Python 3.12+, Neo4j 5+

# Install dependencies
pip install -r requirements.txt

# Configure .env
cp .env.example .env  # edit with your Neo4j credentials

# Run the server
uvicorn main:app --reload --port 8000
```

## AI Assistant

The built-in AI assistant uses your notes as context when answering questions. It supports three providers — choose one from the settings panel inside the app.

### Ollama (Local)

Run models locally with no API key required. The app auto-detects models you have installed.

```bash
# Install Ollama: https://ollama.com
# Pull a model
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

### Auth
- `POST /signup` — create account (JSON: `username`, `password`)
- `POST /login` — get JWT token (JSON: `username`, `password`)

### Pages (requires `Authorization: Bearer <token>`)
- `GET /pages` — list all pages
- `GET /pages/{title}` — get a single page
- `POST /pages` — create a page (JSON: `title`, `blocks`)
- `PUT /pages/{title}` — update a page (JSON: `blocks`)
- `DELETE /pages/{title}` — delete a page

### Graph
- `GET /graph` — get all nodes and edges for the graph view

### AI
- `POST /ask` — streaming AI response (JSON: `question`, `provider`, `model`, `api_key`)
- `GET /ollama/models` — list locally available Ollama models

## Architecture

```
main.py          — FastAPI backend (auth, CRUD, AI streaming, graph)
static/index.html — single-file frontend (editor, graph, AI panel, VR)
Dockerfile        — Python 3.12 slim image
docker-compose.yml — app + Neo4j stack
```

Neo4j schema:
- `(:User {username, password_hash})` — user accounts
- `(:Page {title, blocks, updated_at})` — note pages
- `(:User)-[:OWNS]->(:Page)` — ownership
- `(:Page)-[:LINKS_TO]->(:Page)` — wikilink connections


