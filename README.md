# Repair Service

A web service for receiving and managing repair requests, from intake to completion.

Clients submit requests through a public form; a **dispatcher** assigns them to **masters** (technicians); masters take assigned work and mark it done. The service is built around a realistic operational workflow and includes a concurrency-safe "take request" operation that is protected against race conditions.

> Built as a portfolio project by a QA engineer, with a deliberate focus on correctness, testability, and a documented decision log ([DECISIONS.md](DECISIONS.md)).

## Features

- **Public request intake** — anyone can submit a repair request (client name, phone, address, problem description).
- **Role-based access** — two roles, `dispatcher` and `master`, with separate panels and server-side authorization checks.
- **Dispatcher panel** — view all requests, filter by status, assign a request to a master, or cancel it.
- **Master panel** — view assigned requests, atomically *take* a request into work, and mark it *done*.
- **Race-condition protection** — a request can be taken into work exactly once, enforced by a conditional `UPDATE` in a single transaction (returns `409 Conflict` to losers of the race).
- **Request lifecycle** — `new → assigned → in_progress → done`, plus `canceled`.
- **Cookie-based auth** with bcrypt-hashed passwords.

## Tech Stack

- **Backend:** Python 3.11, FastAPI
- **ORM / migrations:** SQLAlchemy 2.0, Alembic
- **Frontend:** server-side rendered Jinja2 templates + Bootstrap 5
- **Database:** SQLite by default (swap to Postgres via `DATABASE_URL`)
- **Auth:** session cookie + `bcrypt` password hashing
- **Tests:** pytest + FastAPI `TestClient`
- **Runtime:** Docker / Docker Compose, or local `uvicorn`

## Architecture

```
Browser / curl
      │
      ▼
FastAPI app (app/main.py)
  ├─ HTML routes  → Jinja2 templates (app/templates/)
  ├─ JSON route   → /api/requests/{id}/take
  ├─ Auth         → cookie "user_id" + bcrypt (get_current_user)
  └─ Data access  → SQLAlchemy ORM (app/models.py)
                          │
                          ▼
                 SQLite / Postgres (DATABASE_URL)
```

The "take into work" path uses an atomic `UPDATE ... WHERE status = 'assigned'`. The database guarantees only one concurrent caller updates the row; everyone else sees `rowcount == 0` and receives `409 Conflict`. See [DECISIONS.md](DECISIONS.md) for the full rationale behind these choices.

## Getting Started

### Run with Docker (recommended)

```bash
docker compose up --build
```

The app will be available at http://localhost:8000. Seed data (demo users and sample requests) is loaded automatically on container start.

### Run locally (without Docker)

```bash
pip install -r requirements.txt
alembic upgrade head      # create schema
python seed.py            # load demo users + sample requests
uvicorn app.main:app --reload
```

Configuration is via environment variables — see [.env.example](.env.example). The only setting is `DATABASE_URL` (defaults to a local SQLite file).

### Demo users

| Role       | Username     | Password  |
|------------|--------------|-----------|
| Dispatcher | `dispatcher` | `pass123` |
| Master 1   | `master1`    | `pass123` |
| Master 2   | `master2`    | `pass123` |

> These are seed credentials for local/demo use only — not production secrets.

## Pages & API Overview

Interactive API docs are available at http://localhost:8000/docs (FastAPI Swagger UI).

| Method | Path                          | Auth        | Description                                  |
|--------|-------------------------------|-------------|----------------------------------------------|
| GET    | `/`                           | public      | Request creation form                        |
| POST   | `/`                           | public      | Submit a new repair request                  |
| GET    | `/login`                      | public      | Login form                                   |
| POST   | `/login`                      | public      | Authenticate and set session cookie          |
| GET    | `/logout`                     | any         | Clear session                                |
| GET    | `/dispatcher`                 | dispatcher  | Dispatcher panel (filter by `?status=`)      |
| POST   | `/dispatcher/assign/{req_id}` | dispatcher  | Assign a request to a master                 |
| POST   | `/dispatcher/cancel/{req_id}` | dispatcher  | Cancel a request                             |
| GET    | `/master`                     | master      | Master panel (own assigned requests)         |
| POST   | `/master/take/{req_id}`       | master      | Take an assigned request into work           |
| POST   | `/master/done/{req_id}`       | master      | Mark a request as done                       |
| POST   | `/api/requests/{req_id}/take` | —           | JSON endpoint to take a request (race demo)  |

## Race-Condition Check

A request can be taken into work only once. Two concurrent requests for the same ID: one returns `200 OK`, the other `409 Conflict`.

Manually, from two terminals at the same time:

```bash
curl -X POST http://localhost:8000/api/requests/1/take
```

Or with the bundled script (fires 10 parallel requests):

```bash
bash race_test.sh          # defaults to request #1
bash race_test.sh 2        # specific request id
```

## Tests

```bash
pytest tests/ -v
```

The test suite uses an isolated SQLite database and FastAPI's `TestClient`, including a threaded test that exercises the race-condition guarantee.

> Note: the project targets Python 3.11 (as pinned in the `Dockerfile`). The pinned SQLAlchemy version is not compatible with Python 3.13, so run tests under 3.11.

## Project Structure

```
repair-service/
├── app/
│   ├── main.py             # FastAPI routes, auth, request lifecycle
│   ├── models.py           # SQLAlchemy models (User, Request) + enums
│   ├── database.py         # engine, session, DATABASE_URL config
│   └── templates/          # Jinja2 + Bootstrap 5 templates
├── migrations/             # Alembic migrations
│   └── versions/
├── tests/                  # pytest suite (incl. race-condition test)
├── seed.py                 # demo users + sample requests
├── race_test.sh            # parallel "take" race-condition script
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── DECISIONS.md            # architecture & design decisions
└── README.md
```

## Documentation

- [DECISIONS.md](DECISIONS.md) — why FastAPI, SQLite, the race-condition approach, auth model, and other design choices.

## License

[MIT](LICENSE) © 2026 r0meo-1
