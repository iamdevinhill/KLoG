# Contributing to KLoG

Thanks for your interest in contributing! This guide will help you get started.

## Getting Started

### Prerequisites

- Python 3.12+
- Neo4j 5+ (or Docker)
- Git

### Local Development Setup

```bash
# Clone the repo
git clone https://github.com/iamdevinhill/kg_log.git
cd kg_log

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment config
cp .env.example .env
# Edit .env with your Neo4j credentials

# Start Neo4j (via Docker, or use a local installation)
docker compose up neo4j -d

# Run the dev server
uvicorn main:app --reload --port 8000
```

### Running Tests

```bash
pytest tests/ -v
```

## How to Contribute

### Reporting Bugs

- Use the [Bug Report](https://github.com/iamdevinhill/kg_log/issues/new?template=bug_report.md) template
- Include steps to reproduce, expected vs actual behavior, and your environment details

### Suggesting Features

- Use the [Feature Request](https://github.com/iamdevinhill/kg_log/issues/new?template=feature_request.md) template
- Describe the use case and why it would be valuable

### Submitting Code

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Run tests (`pytest tests/ -v`)
5. Commit with a clear message
6. Push to your fork and open a Pull Request

### Code Style

- Follow existing patterns in the codebase
- Keep functions focused and small
- Use type hints where practical
- Write tests for new functionality

## Project Structure

```
app/
  config.py    - Environment variables and configuration
  database.py  - Neo4j driver management
  auth.py      - JWT authentication helpers
  models.py    - Pydantic request/response models
  pages.py     - Page CRUD routes and wikilink parsing
  graph.py     - Knowledge graph routes
  ai.py        - Multi-provider AI streaming routes
main.py        - FastAPI app setup, lifespan, auth endpoints
static/        - Frontend (single-page app)
tests/         - Test suite
```

## Questions?

Open a [Discussion](https://github.com/iamdevinhill/kg_log/discussions) or file an issue.
