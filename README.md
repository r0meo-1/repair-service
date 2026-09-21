# Repair Service — заявки на ремонт без гонки мастеров

> Клиент нажал «починить». Назначенный мастер дважды одновременно нажал «взять».
> Один запрос к JSON API получает `200`, второй `409`; другой мастер изменить заявку не может.
> Потому что **база данных не верит в судьбу**, она верит в `UPDATE … WHERE`.

Веб-сервис приёма и ведения заявок на ремонт: форма → диспетчер → мастер → «готово».  
Портфолио-проект с упором на **корректность, тестируемость** и журнал решений ([DECISIONS.md](DECISIONS.md)).

Автор: Роман Неклюдов · **[r0meo1.ru](https://r0meo1.ru)**

## За 20 секунд

| | |
|--|--|
| **Что** | FastAPI-сервис заявок: роли, статусы, atomic take |
| **Зачем** | Назначенный мастер берёт заявку один раз — один `200`, остальные `409` |
| **Проверить** | `pytest` · `docker compose up` · [DECISIONS.md](DECISIONS.md) |

---

## Фичи (без маркетингового сиропа)

- **Публичная форма** — имя, телефон, адрес, «что сломалось»
- **Роли** — `dispatcher` и `master`, проверка прав на сервере (куки — не крепость, но и не «security through hope»)
- **Панель диспетчера** — фильтры, назначение, отмена
- **Панель мастера** — свои заявки, atomic *take*, *done*
- **Защита от гонок** — взять заявку можно ровно один раз; проигравший concurrent получает `409 Conflict`
- **Жизненный цикл** — `new → assigned → in_progress → done` (+ `canceled`)
- **Auth** — подписанная сессия (HttpOnly, SameSite=Lax, 8 часов) + bcrypt

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

Для постоянных сессий задайте случайный `SESSION_SECRET` длиной не менее 32 символов
в окружении процесса; все workers должны использовать один ключ. Без него локальное
демо генерирует ключ при запуске, поэтому перезапуск завершает все сессии.
При работе только через HTTPS задайте `SESSION_HTTPS_ONLY=true`. Docker Compose
передаёт эти значения из `.env`; при локальном запуске экспортируйте их в окружение.
Старые неподписанные cookies `user_id` больше не принимаются: требуется новый вход.

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
| POST | `/api/requests/{id}/take` | assigned master | Взять через JSON API |

---

## Проверка гонки

Сначала назначьте новую заявку мастеру `master1` через панель диспетчера.
Войдите под ним и сохраните сессию локально:

```bash
curl --data-urlencode 'username=master1' --data-urlencode 'password=pass123' \
  --cookie-jar .race-session.cookies http://localhost:8000/login
```

Отправьте десять параллельных запросов для ID назначенной заявки:

```bash
bash race_test.sh 1 .race-session.cookies
```

Один `200`, остальные `409`; скрипт завершается с ошибкой при другом результате.
Для повторного прогона создайте и назначьте новую заявку. Не публикуйте cookie-файл.
Без входа или с ролью диспетчера API возвращает `403`, для чужой заявки — `409`.
Завершить заявку может только назначенный мастер из статуса `in_progress`.
Диспетчер назначает только `new`/`assigned` и отменяет только незавершённые заявки.

---

## Тесты

```bash
python -m pytest tests/ -v
```

Каждый тест использует отдельный временный SQLite и собственный TestClient.
Импорт приложения в тестах не открывает локальную рабочую БД.
Проверяются создание заявки, назначение, выполнение и конкурентное взятие:
из пяти одновременных запросов ровно один успешен, остальные получают `409`.
Для HTML-маршрута успех — редирект `302`, для демонстрационного API — `200`.

GitHub Actions запускает набор на Python 3.11 и 3.12 при push и pull request.
В Docker используется **Python 3.11**. Проверки не являются аудитом безопасности.

---

## Контакты

**[r0meo1.ru](https://r0meo1.ru)** · [@r0meo1](https://t.me/r0meo1) · r0meo1@ya.ru

## Лицензия

[MIT](LICENSE) — чините код, не чините прод в пятницу вечером… ладно, иногда придётся.
