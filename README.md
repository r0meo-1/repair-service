# Repair Service

Веб-сервис для приёма и обработки заявок в ремонтную службу.

## Стек

- **Backend:** Python 3.11, FastAPI, SQLAlchemy, Alembic
- **Frontend:** Jinja2 templates, Bootstrap 5
- **DB:** SQLite
- **Запуск:** Docker Compose или локально

## Быстрый старт (Docker)

```bash
docker compose up --build
```

Приложение будет доступно по адресу: http://localhost:8000

## Локальный запуск (без Docker)

```bash
pip install -r requirements.txt
alembic upgrade head
python seed.py
uvicorn app.main:app --reload
```

## Тестовые пользователи

| Роль | Логин | Пароль |
|------|-------|--------|
| Диспетчер | dispatcher | pass123 |
| Мастер 1 | master1 | pass123 |
| Мастер 2 | master2 | pass123 |

## Страницы

- `/` — создание заявки (публичная)
- `/login` — авторизация
- `/dispatcher` — панель диспетчера
- `/master` — панель мастера

## Проверка защиты от гонки (race condition)

Заявку можно взять в работу только один раз. Реализовано через оптимистичную блокировку (SELECT + UPDATE с проверкой статуса в одной транзакции).

Проверка двумя терминалами:

```bash
# Терминал 1
curl -X POST http://localhost:8000/api/requests/1/take -H "Authorization: master1:pass123"

# Терминал 2 (одновременно)
curl -X POST http://localhost:8000/api/requests/1/take -H "Authorization: master1:pass123"
```

Или скриптом:

```bash
bash race_test.sh
```

Один запрос получит `200 OK`, второй — `409 Conflict`.

## Автотесты

```bash
pytest tests/ -v
```
