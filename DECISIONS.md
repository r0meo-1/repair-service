# DECISIONS.md

## 1. Framework: FastAPI
FastAPI chosen for auto validation via Pydantic, built-in Swagger docs, async support and performance.

## 2. Database: SQLite
SQLite for zero-dependency local run. Easy to swap to Postgres by changing DATABASE_URL.

## 3. ORM: SQLAlchemy + Alembic
SQLAlchemy for DB access, Alembic for schema versioning and migrations.

## 4. Race condition protection
Implemented via UPDATE ... WHERE status='assigned' in one transaction. If 0 rows updated - request already taken, return 409 Conflict.

## 5. Auth: session cookie + bcrypt
Signed, timestamped sessions use Starlette SessionMiddleware with HttpOnly and
SameSite=Lax cookies and an eight-hour lifetime. SESSION_SECRET provides a shared
random key for persistent or multi-worker deployments; the local demo uses a
process-local random key when unset. SESSION_HTTPS_ONLY enables Secure cookies.
Unsigned legacy user_id cookies are ignored. Roles are loaded from the database.
Both HTML and JSON take routes require the assigned master. Ownership and prior
status are predicates of the same atomic UPDATE. Done requires in_progress;
assignment accepts only new/assigned and cancellation excludes terminal states.
Passwords remain bcrypt hashes. No JWT is needed.

## 6. Frontend: Jinja2 + Bootstrap 5
Server-side rendering with Jinja2 templates. Bootstrap 5 for styling without writing custom CSS.

## 7. Launch: Docker Compose
Single command `docker compose up --build` starts the app. Migrations and seeds run automatically on container start.
