# Phase 4 — Playwright-парсер, деплой, бета-тест, запуск

**Дата:** 2026-06-11  
**Статус:** Утверждён  
**Фаза роадмапа:** 4 из 5

---

## Цель

Подготовить MenuScan к публичному запуску: заменить статичный HTML-парсер на Playwright для JS-рендеренных сайтов, настроить production-инфраструктуру, задеплоить на Railway и Render, провести бета-тест с 3–5 реальными заведениями, выйти на публичный запуск.

---

## Архитектура

### Новые компоненты

```
┌─────────────┐    enqueue     ┌─────────────┐    BRPOP    ┌──────────────────┐
│   API       │ ─────────────► │   Redis     │ ──────────► │  parser-worker   │
│  (FastAPI)  │                │  (ARQ queue)│             │  (ARQ + Playwright│
│             │ ◄───────────── │             │             │   Chromium)       │
└─────────────┘   job status   └─────────────┘             └──────────────────┘
       │                                                            │
       │ SQL                                                        │ SQL
       ▼                                                            ▼
┌─────────────┐                                           ┌─────────────────┐
│  PostgreSQL │                                           │  ParseJob update │
└─────────────┘                                           └─────────────────┘
```

**Файлы:**
- `backend/app/workers/arq_worker.py` — ARQ WorkerSettings + задача `run_parse_job`
- `backend/app/workers/playwright_parser.py` — Playwright-парсер
- `backend/Dockerfile.worker` — образ с Chromium
- `docker-compose.prod.yml` — production-конфиг
- `railway.toml` — Railway деплой
- `render.yaml` — Render деплой

**Изменения в существующем коде:**
- `backend/app/api/parse.py` — заменить `asyncio.create_task(run_parse_job(...))` на `await arq_queue.enqueue("run_parse_job", str(job_id))`
- `backend/app/workers/parser.py` — добавить автодетект: если `dishes_found < 3` после httpx, fallback на Playwright

---

## Playwright-парсер

### Логика выбора движка (автодетект)

```
httpx GET → BS4 парсинг → dishes_found < 3?
    → да:  Playwright fallback (JS-рендеринг)
    → нет: готово, Playwright не запускается
```

### `playwright_parser.py`

1. Запускает Chromium headless через `async_playwright`
2. Переходит на URL, ждёт `networkidle`
3. Скроллит страницу вниз 3 раза (триггерит lazy-load)
4. Извлекает HTML, передаёт в существующий `extract_dishes_from_html`
5. Таймаут 60 сек → `job.status = "failed"` при превышении

### ARQ Worker

```python
class WorkerSettings:
    functions = [run_parse_job]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs = 5        # параллельных задач
    job_timeout = 120   # секунд на задачу
    max_tries = 3       # автоматических ретраев
```

### `Dockerfile.worker`

```dockerfile
FROM python:3.12-slim
RUN pip install playwright arq asyncpg sqlalchemy httpx beautifulsoup4
RUN playwright install chromium --with-deps
COPY ./app /app
WORKDIR /app
CMD ["python", "-m", "arq", "app.workers.arq_worker.WorkerSettings"]
```

**Known limitation:** Playwright не решает капчи и закрытые (авторизованные) меню. Документируется в README.

---

## Production-конфиг

### `docker-compose.prod.yml`

Отличия от dev `docker-compose.yml`:
- API: без `--reload`, `--workers 2`
- Порты не пробрасываются на хост (только через reverse proxy)
- Новый сервис `parser-worker` с `Dockerfile.worker`
- MinIO убран — используется внешний S3/R2 (`S3_ENDPOINT_URL` из env)
- `restart: unless-stopped` на всех сервисах
- `parser-worker` зависит от healthcheck API

### Railway (`railway.toml`)

```toml
[build]
builder = "dockerfile"
dockerfilePath = "backend/Dockerfile"

[deploy]
startCommand = "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
```

- Отдельный Railway-сервис `parser-worker` с `Dockerfile.worker`
- PostgreSQL и Redis — managed Railway services

### Render (`render.yaml`)

```yaml
services:
  - type: web
    name: menuscan-api
    dockerfilePath: ./backend/Dockerfile
    healthCheckPath: /health
  - type: worker
    name: menuscan-parser
    dockerfilePath: ./backend/Dockerfile.worker
databases:
  - name: menuscan-pg
  - name: menuscan-redis
    plan: starter
```

### Мониторинг

- **UptimeRobot** (бесплатный) — пинг `/health` каждые 5 мин, алерт на email при даунтайме
- `GET /health` возвращает статус БД и Redis (проверить/добавить если отсутствует)

---

## Бета-тест

**Длительность:** ~2 недели  
**Количество заведений:** 3–5  
**Онбординг:** ручной

### Процесс

1. `POST /auth/register` + `POST /venues` — регистрируешь заведение сам
2. Передаёшь владельцу логин/пароль + ссылку на dashboard
3. Владелец загружает меню (парсер или CSV), генерирует QR-коды
4. Клеит QR на столы, гости сканируют

### Что фиксируем

- Баги парсера (JS-сайты, нестандартные структуры HTML)
- UX-проблемы dashboard (что непонятно без объяснений)
- Перформанс WebSocket при реальной нагрузке

---

## Критерии публичного запуска

| Технический | Продуктовый |
|---|---|
| 0 критических багов за 48ч | ≥1 заведение с живым меню |
| CI/CD деплой работает стабильно | ≥10 реальных заказов через систему |
| `/health` зелёный 7 дней подряд | Владелец работает самостоятельно |
| UptimeRobot: uptime >99% | Playwright-парсер сработал на ≥1 реальном сайте |

### Действия при запуске

- Landing page (минимум: README или простой HTML)
- `POST /auth/register` открыт без ограничений
- Анонс в профильных Telegram-чатах (рестораторы, автоматизация HoReCa)

---

## Порядок реализации

1. **ARQ-очередь** — переключить API с `asyncio.create_task` на ARQ enqueue
2. **Playwright-парсер** — `playwright_parser.py` + автодетект в `parser.py`
3. **Dockerfile.worker** — образ с Chromium
4. **`docker-compose.prod.yml`** — production-конфиг
5. **Railway деплой** — `railway.toml`, настройка managed services
6. **Render деплой** — `render.yaml`
7. **Мониторинг** — `GET /health` проверяет БД+Redis, UptimeRobot
8. **Бета-тест** — онбординг 3–5 заведений, фикс багов
9. **Публичный запуск** — открыть регистрацию, анонс
