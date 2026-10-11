# Contributing to Rankings Bot

## Development Setup

1. Clone the repo and `cd Rankings-Bot`
2. Create venv: `python3 -m venv .venv && source .venv/bin/activate`
3. Install: `pip install -r requirements.txt -r requirements-api.txt`
4. Frontend: `cd frontend && npm install`
5. Database: Set `DATABASE_URL` (PostgreSQL). Run `alembic upgrade head`

## Running

- API: `uvicorn api.main:app --host 0.0.0.0 --port 8003`
- Frontend: `cd frontend && npm run dev`

## Code Standards

- Follow [.github/CODING_STANDARDS.md](.github/CODING_STANDARDS.md)
- Python: type hints, docstrings for public APIs
- Frontend: TypeScript, React best practices

## Documentation

- Add/update docs in `docs/`
- Update [docs/INDEX.md](docs/INDEX.md) for new topics
- Completion reports go in `docs/archive/`

## Pull Requests

1. Branch from `main` (or current dev branch)
2. Run tests before submitting
3. Keep PRs focused; link related issues
