# Workspace Instructions — Rankings Bot

## Coding Standards (MANDATORY)

**ALL code must follow standards-driven development** based on official documentation and industry best practices.

- **Consult official docs first** — FastAPI, React, PostgreSQL, Docker, SQLAlchemy
- **Follow language standards** — PEP 8 (Python), TypeScript strict mode
- **Security best practices** — Input validation, secure auth, no hardcoded secrets
- **Performance patterns** — Query optimization, caching, async operations
- **Testing requirements** — 80%+ coverage, proper mocking, AAA pattern
- **Documentation** — Docstrings, type hints, API docs

**See:** [CODING_STANDARDS.md](CODING_STANDARDS.md) for complete reference.

---

## Project Structure

Rankings Bot is a web application for tournament management with:
- **Frontend:** React + Vite + TypeScript (path alias: `@/`)
- **Backend:** FastAPI + SQLAlchemy + PostgreSQL
- **Special feature:** Uses `@/contexts/AuthContext` (plural, unlike other bots)

---

## Docker & Deployment

### Docker Standards
- Use multi-stage builds for frontend
- Include health checks in all containers
- Run as non-root user where possible
- Use named volumes for persistence
- Configure proper networking between services

### Environment Variables
- Store all secrets in `.env` files (never commit)
- Use `.env.example` as template
- Document all required environment variables

---

## Database Standards

### PostgreSQL
- Follow 3NF normalization
- Add indexes for frequently queried fields
- Use foreign key constraints
- Include `created_at` and `updated_at` timestamps
- Use transactions for multi-statement operations

### Migrations
- Use Alembic for all schema changes
- Test migrations up and down
- Document breaking changes

---

## API Development

### FastAPI Best Practices
- Use Pydantic models for all request/response validation
- Implement proper error handling with HTTPException
- Use dependency injection (Depends) for auth and database sessions
- Document endpoints with descriptions and examples
- Return correct HTTP status codes

### Authentication
- Verify JWT tokens on all protected endpoints
- Use secure password hashing (bcrypt)
- Implement proper CORS configuration
- Never log sensitive data (passwords, tokens)

---

## Frontend Development

### React + TypeScript
- Use functional components with hooks
- Define TypeScript interfaces for all props and API responses
- Use `@/` path alias for imports
- Implement error boundaries
- Show loading states for async operations

### State Management
- Use Context API for global state (AuthContext, ThemeContext)
- Keep local state minimal with useState
- Use useMemo for expensive computations
- Proper cleanup in useEffect hooks

---

## Testing Standards

### Unit Tests
- 80%+ code coverage
- Follow AAA pattern (Arrange, Act, Assert)
- Mock external dependencies
- Each test should be independent
- Use descriptive test names

### Integration Tests
- Test complete user workflows
- Rollback database after each test
- Test error scenarios and edge cases

---

## Security Standards

### Input Validation
- Validate all API inputs with Pydantic
- Use parameterized queries (SQLAlchemy ORM prevents SQL injection)
- Sanitize user inputs displayed in frontend
- Implement rate limiting on sensitive endpoints

### Secrets Management
- Never hardcode secrets
- Use environment variables
- Document secret rotation procedures
- Use least privilege access for database roles

---

## Rankings Bot Specific

### Tournament Management
- Ensure data integrity for tournaments and players
- Validate bracket logic before persisting
- Handle concurrent updates properly
- Document ranking calculation algorithms

### Web Scraping
- Respect rate limits of target sites
- Cache scraped data appropriately
- Handle parsing errors gracefully
- Use appropriate user agent strings

### AI Coach Integration
- Monitor and respect API rate limits (OpenAI, Grok)
- Track token usage and costs
- Version control prompts
- Implement fallback strategies for API failures

---

## Commit Standards

Use Conventional Commits format:
- `feat:` — New feature
- `fix:` — Bug fix
- `docs:` — Documentation
- `refactor:` — Code refactoring
- `test:` — Tests
- `chore:` — Maintenance

Example: `feat: add tournament bracket generation`

---

## References

- [CODING_STANDARDS.md](.github/CODING_STANDARDS.md) — Complete coding standards
- [Roadmap.md](Roadmap.md) — Project roadmap and feature plans
- [README.md](README.md) — Setup and getting started
- [docs/](docs/) — Additional documentation

**When in doubt, consult the official documentation first.**
