# Repair Service — заявки на ремонт без гонки мастеров

> Клиент нажал «починить». Два мастера одновременно нажали «взять».  
> В плохом сервисе оба уверены, что работа их. В этом — один получает `200`, второй `409`.  
> Потому что **база данных не верит в судьбу**, она верит в `UPDATE … WHERE`.

Веб-сервис приёма и ведения заявок на ремонт: форма → диспетчер → мастер → «готово».  
Портфолио-проект с упором на **корректность, тестируемость** и журнал решений ([DECISIONS.md](DECISIONS.md)).

Автор: Роман Неклюдов · **[r0meo1.ru](https://r0meo1.ru)**

## За 20 секунд

| | |
|--|--|
| **Что** | FastAPI-сервис заявок: роли, статусы, atomic take |
| **Зачем** | Два мастера не «делят» одну заявку — один `200`, второй `409` |
| **Проверить** | `pytest` · `docker compose up` · [DECISIONS.md](DECISIONS.md) |

---

## Фичи (без маркетингового сиропа)

- **Публичная форма** — имя, телефон, адрес, «что сломалось»
- **Роли** — `dispatcher` и `master`, проверка прав на сервере (куки — не крепость, но и не «security through hope»)
- **Панель диспетчера** — фильтры, назначение, отмена
- **Панель мастера** — свои заявки, atomic *take*, *done*
- **Защита от гонок** — взять заявку можно ровно один раз; проигравший concurrent получает `409 Conflict`
- **Жизненный цикл** — `new → assigned → in_progress → done` (+ `canceled`)
- **Auth** — cookie + bcrypt

---

## Стек

| Слой | Технологии |
|------|------------|
| Backend | Python 3.11, FastAPI |
| ORM | SQLAlchemy 2.0, Alembic |
| UI | Jinja2 + Bootstrap 5 (SSR, без «ещё одного SPA ради резюме») |
| БД | SQLite по умолчанию / Postgres через `DATABASE_URL` |
| Тесты | pytest + TestClient |
| Рантайм | Docker Compose или uvicorn |

---

## Архитектура

```
Браузер / curl
      │
      ▼
FastAPI (app/main.py)
  ├─ HTML  → Jinja2
  ├─ JSON  → /api/requests/{id}/take
  ├─ Auth  → cookie + bcrypt
  └─ ORM   → SQLAlchemy
                 │
                 ▼
            SQLite / Postgres
```

«Взять в работу» = atomic `UPDATE … WHERE status = 'assigned'`.  
Один победитель, остальные — `rowcount == 0`. Подробности и почему так, а не «select for update и молитва» — в [DECISIONS.md](DECISIONS.md).

---

## Быстрый старт

### Docker (рекомендуется)

```bash
docker compose up --build
```

→ http://localhost:8000  
Сиды (юзеры и заявки) поднимаются сами. Магия? Нет, `seed` на старте.

### Локально

```bash
pip install -r requirements.txt
alembic upgrade head
python seed.py
uvicorn app.main:app --reload
```

См. [.env.example](.env.example). По сути — `DATABASE_URL`.

### Демо-пользователи

| Роль | Логин | Пароль |
|------|-------|--------|
| Диспетчер | `dispatcher` | `pass123` |
| Мастер 1 | `master1` | `pass123` |
| Мастер 2 | `master2` | `pass123` |

> Это **демо**, не прод. Если у вас в проде `pass123` — мы уже знакомы по инцидентам.

---

## Страницы и API

Swagger: http://localhost:8000/docs

| Метод | Путь | Кто | Что |
|-------|------|-----|-----|
| GET/POST | `/` | public | Форма заявки |
| GET/POST | `/login` | public | Вход |
| GET | `/logout` | any | Выход |
| GET | `/dispatcher` | dispatcher | Панель (`?status=`) |
| POST | `/dispatcher/assign/{id}` | dispatcher | Назначить |
| POST | `/dispatcher/cancel/{id}` | dispatcher | Отменить |
| GET | `/master` | master | Мои заявки |
| POST | `/master/take/{id}` | master | Взять |
| POST | `/master/done/{id}` | master | Готово |
| POST | `/api/requests/{id}/take` | — | JSON-гонка (демо) |

---

## Проверка гонки

Два терминала, одновременно:

```bash
curl -X POST http://localhost:8000/api/requests/1/take
```

Или пачкой:

```bash
bash race_test.sh      # заявка #1
bash race_test.sh 2    # другая
```

Один `200`, остальные `409`. Если все `200` — либо вы в параллельной вселенной, либо пора читать DECISIONS.md заново.

---

## Тесты

```bash
pytest tests/ -v
```

Отдельный SQLite, TestClient, в том числе threaded race-test.  
**Python 3.11** (как в Dockerfile). 3.13 + этот SQLAlchemy = боль. Не надо.

---

## Контакты

**[r0meo1.ru](https://r0meo1.ru)** · [@r0meo1](https://t.me/r0meo1) · r0meo1@ya.ru

## Лицензия

[MIT](LICENSE) — чините код, не чините прод в пятницу вечером… ладно, иногда придётся.
