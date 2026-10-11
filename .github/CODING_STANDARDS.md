# Coding Standards — Rankings Bot

**Principle:** All code must be standards-driven, following official manuals, documentation, and industry best practices.

---

## Core Principles

### 1. Follow Official Documentation First

When implementing features or fixing issues:
- **Consult official documentation** for the framework/library being used
- **Reference language specifications** for Python, TypeScript, JavaScript
- **Follow API documentation** exactly (FastAPI, React, Vite, PostgreSQL, SQLAlchemy)
- **Use proven patterns** from official examples and guides

**Never guess or assume** — look it up in the official docs.

---

## Language-Specific Standards

### Python (FastAPI Backend)

#### Style & Formatting
- **PEP 8** — Python style guide (line length, naming, imports)
- **PEP 257** — Docstring conventions
- **Type hints** — Use Python 3.10+ type annotations for all function signatures
- **Import order**: stdlib → third-party → local (alphabetized within each group)

```python
# Good
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from api.models.user import User
from api.dependencies import get_db
```

#### FastAPI Best Practices
- **Pydantic models** for all request/response validation
- **Dependency injection** for database sessions, auth
- **HTTP status codes** — Use correct semantic codes (200, 201, 400, 401, 404, 500)
- **Error handling** — Always raise `HTTPException` with proper status and detail
- **Async where appropriate** — Use `async def` for I/O-bound operations
- **Path parameters** — Use path operations with proper type validation

```python
# Good
@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db)
) -> UserResponse:
    """Get user by ID following FastAPI patterns."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
```

#### Database (SQLAlchemy / PostgreSQL)
- **Models** — Define SQLAlchemy models with proper relationships
- **Migrations** — Use Alembic for database migrations
- **Transactions** — Use context managers for database sessions
- **Indexes** — Add indexes for frequently queried fields
- **Constraints** — Define foreign keys, unique constraints in models
- **Connection pooling** — Configure proper pool size and timeout

```python
# Good
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    audit_logs = relationship("AuditLog", back_populates="user")
```

### TypeScript/JavaScript (React Frontend)

#### Style & Formatting
- **ESLint** — Follow configured linting rules
- **TypeScript strict mode** — Enable strict type checking
- **Naming** — PascalCase for components, camelCase for functions/variables
- **File names** — PascalCase for components (`LoginForm.tsx`), kebab-case for utils

#### React Best Practices (React 18+)
- **Functional components** — Always use function components with hooks
- **TypeScript interfaces** — Define types for all props, state, API responses
- **Hooks** — Use built-in hooks properly (useState, useEffect, useContext, useMemo)
- **Custom hooks** — Extract reusable logic into custom hooks (prefix with `use`)
- **Error boundaries** — Implement error boundaries for resilient UIs
- **Accessibility** — Use semantic HTML, ARIA labels where needed

```typescript
// Good
interface LoginFormProps {
  onSuccess: (token: string) => void;
  onError: (error: string) => void;
}

export const LoginForm: React.FC<LoginFormProps> = ({ onSuccess, onError }) => {
  const [email, setEmail] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  
  // Implementation...
};
```

#### State Management
- **Context API** — Use React Context for global state (auth, theme)
- **Local state** — Use useState for component-specific state
- **Derived state** — Use useMemo for computed values
- **Side effects** — Use useEffect with proper dependency arrays

#### API Integration
- **Axios/Fetch** — Use consistent error handling
- **Type safety** — Define TypeScript interfaces for all API responses
- **Loading states** — Always show loading indicators during async operations
- **Error handling** — Display user-friendly error messages

```typescript
// Good
interface ApiResponse<T> {
  data: T;
  message?: string;
}

const fetchUser = async (userId: number): Promise<User> => {
  try {
    const response = await axios.get<ApiResponse<User>>(`/api/users/${userId}`);
    return response.data.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      throw new Error(error.response?.data?.detail || 'Failed to fetch user');
    }
    throw error;
  }
};
```

---

## Docker & Deployment Standards

### BuildKit and Intelligent Layering
- **DOCKER_BUILDKIT=1** — Enable BuildKit for all builds (parallel stages, cache mounts, content-addressable cache)
- **Layer order** — Least-changing first: system deps → Python deps → app code (Docker docs)
- **Cache mounts** — Use `RUN --mount=type=cache,target=/root/.cache/pip` for pip to avoid bloated layers
- **Content hash** — `docker_build_hash.sh` tracks Dockerfile, requirements, app code; skip rebuild when unchanged

### Dockerfile Best Practices
- **Multi-stage builds** — Separate build and runtime stages
- **Minimal base images** — Use alpine or slim variants
- **Layer caching** — Order commands for optimal caching
- **Security** — Run as non-root user, scan for vulnerabilities
- **Health checks** — Always include HEALTHCHECK instruction

```dockerfile
# Good
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:80/ || exit 1
USER nginx
```

### Docker Compose Standards
- **Networks** — Use shared networks for service communication
- **Volumes** — Use named volumes for persistence
- **Environment** — Use `.env` files, never hardcode secrets
- **Dependencies** — Use `depends_on` with health checks
- **Restart policy** — Set `restart: unless-stopped` for production services

```yaml
# Good
services:
  api:
    image: rankings-bot-api:latest
    networks:
      - rankings-network
    environment:
      - DATABASE_URL=${DATABASE_URL}
    volumes:
      - api-data:/app/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

networks:
  rankings-network:
    driver: bridge

volumes:
  api-data:
```

---

## Database Standards

### Schema Design
- **Normalization** — Follow 3NF (third normal form) minimum
- **Primary keys** — Use auto-incrementing integers or UUIDs
- **Foreign keys** — Define all relationships with proper constraints
- **Timestamps** — Include `created_at` and `updated_at` on all tables
- **Soft deletes** — Add `deleted_at` for soft deletion pattern

### PostgreSQL Best Practices
- **Indexes** — Index foreign keys, frequently queried columns, and WHERE clause fields
- **Constraints** — Use NOT NULL, UNIQUE, CHECK constraints appropriately
- **Data types** — Use appropriate types (TIMESTAMP WITH TIME ZONE, JSONB, etc.)
- **Transactions** — Use transactions for multi-statement operations
- **Connection pooling** — Configure pgBouncer or SQLAlchemy pooling

```sql
-- Good
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_deleted_at ON users(deleted_at) WHERE deleted_at IS NULL;
```

---

## Security Standards

### Authentication & Authorization
- **JWT tokens** — Use short-lived access tokens (15-60 minutes)
- **Secure storage** — Never store passwords in plaintext; use bcrypt/argon2
- **Token validation** — Verify tokens on every protected endpoint
- **CORS** — Configure CORS properly (never use `*` in production)
- **HTTPS only** — Enforce SSL/TLS in production

### Input Validation
- **Pydantic validation** — Validate all API inputs with Pydantic models
- **SQL injection prevention** — Always use parameterized queries (SQLAlchemy ORM)
- **XSS prevention** — Sanitize user inputs, use Content Security Policy
- **CSRF protection** — Implement CSRF tokens for state-changing operations

### Secrets Management
- **Environment variables** — Store secrets in `.env` files (never commit)
- **Secret rotation** — Document secret rotation procedures
- **Least privilege** — Use minimum required permissions for database/API access

### Subprocess / running external commands
- **Prefer list form** — Use `subprocess.Popen([executable, arg1, ...])` or `subprocess.run([...])`; avoid `shell=True` to prevent injection.
- **Absolute path for executable** — Use e.g. `/bin/bash` (or a configurable constant) so commands work when `PATH` is empty (systemd, minimal Docker). See [Python subprocess docs](https://docs.python.org/3/library/subprocess.html#security-considerations).
- **No user input in command** — Never pass unsanitized user input as the executable or arguments; only run scripts/paths the application controls.
- **Logging** — Log PID and script path when starting background processes for debugging and audit.

```python
# Good
REBUILD_SHELL = "/bin/bash"
proc = subprocess.Popen(
    [REBUILD_SHELL, str(script_path)],
    cwd=str(app_root),
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    env=env,
)
logger.info("Rebuild started (PID %s), script=%s", proc.pid, script_path)
```

```python
# Good — Never do this
# password = "admin123"  # WRONG

# Good
import os
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)
```

---

## Testing Standards

### Unit Tests
- **Coverage** — Aim for 80%+ code coverage
- **Naming** — Test function names should describe what's being tested
- **Arrange-Act-Assert** — Follow AAA pattern
- **Mocking** — Mock external dependencies (databases, APIs)
- **Isolation** — Each test should be independent

```python
# Good
def test_user_creation_with_valid_data():
    # Arrange
    user_data = {"email": "test@example.com", "password": "secure123"}
    
    # Act
    user = create_user(user_data)
    
    # Assert
    assert user.email == user_data["email"]
    assert user.id is not None
```

### Integration Tests
- **Test real workflows** — Test complete user journeys
- **Database transactions** — Rollback after each test
- **API endpoints** — Test all HTTP methods and status codes
- **Error scenarios** — Test error handling and edge cases

---

## Git & Version Control Standards

### Commit Messages
- **Conventional Commits** — Use standardized commit format
  - `feat:` — New feature
  - `fix:` — Bug fix
  - `docs:` — Documentation changes
  - `refactor:` — Code refactoring
  - `test:` — Test additions/changes
  - `chore:` — Maintenance tasks

```bash
# Good
git commit -m "feat: add PostgreSQL migration for user table"
git commit -m "fix: resolve CORS issue in auth endpoints"
git commit -m "docs: update roadmap with Postgres upgrade plan"
```

### Branch Strategy
- **main** — Production-ready code
- **develop** — Integration branch
- **feature/** — New features (`feature/postgres-migration`)
- **fix/** — Bug fixes (`fix/cors-auth`)
- **hotfix/** — Urgent production fixes

### Pull Requests
- **Descriptive titles** — Summarize changes clearly
- **Linked issues** — Reference related issues
- **Review checklist** — Tests pass, docs updated, no vulnerabilities
- **Small PRs** — Keep changes focused and reviewable

---

## Documentation Standards

### Code Documentation
- **Docstrings** — Document all functions, classes, modules
- **Type hints** — Use type annotations for self-documenting code
- **Comments** — Explain WHY, not WHAT (code should be self-explanatory)
- **README** — Keep README.md up to date with setup instructions

```python
# Good
async def authenticate_user(email: str, password: str, db: Session) -> Optional[User]:
    """
    Authenticate user by email and password.
    
    Args:
        email: User's email address (validated by Pydantic)
        password: Plain text password to verify
        db: Database session for querying users
        
    Returns:
        User object if authentication succeeds, None if credentials invalid
        
    Raises:
        HTTPException: If database query fails
    """
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user
```

### API Documentation
- **OpenAPI/Swagger** — FastAPI auto-generates; ensure accuracy
- **Endpoint descriptions** — Document purpose, parameters, responses
- **Example requests** — Provide curl examples for common operations
- **Error responses** — Document all possible error codes

---

## Performance Standards

### Backend Performance
- **Database queries** — Optimize N+1 queries (use joins, eager loading)
- **Caching** — Cache expensive operations (Redis, in-memory)
- **Async operations** — Use async for I/O-bound tasks
- **Query optimization** — Use EXPLAIN ANALYZE for slow queries
- **Connection pooling** — Reuse database connections

### Frontend Performance
- **Code splitting** — Use React.lazy() for route-based splitting
- **Memoization** — Use useMemo, useCallback to prevent re-renders
- **Bundle size** — Monitor and minimize bundle size
- **Image optimization** — Use appropriate formats (WebP), lazy loading
- **API calls** — Debounce search inputs, implement pagination

---

## Error Handling Standards

### Backend Errors
- **HTTP status codes** — Use semantically correct codes
  - 200 OK, 201 Created, 204 No Content
  - 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found
  - 500 Internal Server Error, 503 Service Unavailable
- **Error responses** — Return consistent JSON structure
- **Logging** — Log errors with context (user ID, request ID, timestamp)
- **Graceful degradation** — Handle external API failures gracefully

```python
# Good
try:
    result = await external_api_call()
except ExternalAPIError as e:
    logger.error(f"External API failed: {e}", extra={"user_id": user.id})
    raise HTTPException(
        status_code=503,
        detail="External service temporarily unavailable. Please try again later."
    )
```

### Frontend Errors
- **User-friendly messages** — Never show raw error text to users
- **Error boundaries** — Catch runtime errors in React components
- **Retry logic** — Implement retry for transient failures
- **Loading states** — Always show loading indicators during async ops

---

## Configuration Standards

### Single Source of Truth, No Fallbacks
- **Config files** (e.g. `config/splash_config.json`) are the single source of truth.
- **Do not** add fallback values when config is missing or invalid — surface the error so operators fix it.
- **API:** Raise `HTTPException(503)` with a clear message when required config is missing.
- **Frontend:** Show error UI when config fails; do not silently substitute defaults.

See [docs/SPLASH_CONFIG.md](../docs/SPLASH_CONFIG.md) for the splash config policy.

---

## Monitoring & Logging Standards

### Logging
- **Structured logging** — Use JSON format for machine parsing
- **Log levels** — DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Context** — Include request ID, user ID, timestamp
- **Sensitive data** — Never log passwords, tokens, credit cards

```python
# Good
import logging

logger = logging.getLogger(__name__)

logger.info(
    "User logged in successfully",
    extra={
        "user_id": user.id,
        "email": user.email,
        "ip_address": request.client.host,
        "timestamp": datetime.utcnow().isoformat()
    }
)
```

### Health Checks
- **Endpoint** — `/api/health` or `/health`
- **Dependencies** — Check database, external APIs, cache
- **Response format** — Return status and component health

```python
# Good
@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint for monitoring."""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database": "connected",
        "version": "1.0.0"
    }
    
    try:
        # Test database connection
        db.execute("SELECT 1")
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["database"] = "disconnected"
        logger.error(f"Database health check failed: {e}")
        raise HTTPException(status_code=503, detail=health_status)
    
    return health_status
```

---

## Rankings Bot Specific Standards

### Tournament Management
- **Data integrity** — Ensure tournament and player data consistency
- **Real-time updates** — Use WebSockets or polling for live scores
- **Match scheduling** — Validate tournament bracket logic
- **Ranking calculations** — Document and test ranking algorithms

### Web Scraping
- **Rate limiting** — Respect target site rate limits
- **Error handling** — Handle network failures and parsing errors gracefully
- **Caching** — Cache scraped data to reduce load on target sites
- **User agents** — Use appropriate user agent strings

### AI Coach Integration
- **API limits** — Monitor and respect API rate limits (OpenAI, Grok)
- **Cost management** — Track token usage and costs
- **Prompt engineering** — Document prompts and versioning
- **Fallback strategies** — Handle API failures gracefully

---

## References

- **Python:** [PEP 8](https://peps.python.org/pep-0008/), [PEP 257](https://peps.python.org/pep-0257/)
- **FastAPI:** [Official Documentation](https://fastapi.tiangolo.com/)
- **React:** [Official Documentation](https://react.dev/)
- **TypeScript:** [Handbook](https://www.typescriptlang.org/docs/handbook/intro.html)
- **PostgreSQL:** [Official Documentation](https://www.postgresql.org/docs/)
- **Docker:** [Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- **SQLAlchemy:** [ORM Documentation](https://docs.sqlalchemy.org/)
- **OWASP:** [Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)

---

## Enforcement

These standards are **mandatory** for all code changes. Code reviews should verify:
- ✅ Follows official documentation and best practices
- ✅ Includes proper error handling and validation
- ✅ Has appropriate tests and documentation
- ✅ Meets security and performance standards
- ✅ Uses correct Docker networking and deployment patterns

**When in doubt, consult the official documentation first.**
