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
Simple cookie-based sessions. Passwords stored as bcrypt hashes. No JWT needed per task requirements.

## 6. Frontend: Jinja2 + Bootstrap 5
Server-side rendering with Jinja2 templates. Bootstrap 5 for styling without writing custom CSS.

## 7. Launch: Docker Compose
Single command `docker compose up --build` starts the app. Migrations and seeds run automatically on container start.
