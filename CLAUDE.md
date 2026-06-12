# MenuScan — CLAUDE.md

SaaS-платформа цифрового QR-меню с совместной корзиной стола для кафе и ресторанов.

## Что строим

Три продукта в одном монорепо:
- **Dashboard** — кабинет владельца (управление меню, QR-коды, аналитика)
- **Guest App (PWA)** — гость сканирует QR, видит меню, заказывает вместе с другими за столом
- **Kitchen Display (KDS)** — повар видит входящие заказы и меняет статусы

## Стек

| Слой | Технология |
|---|---|
| Backend API | FastAPI (Python), asyncpg, SQLAlchemy |
| БД | PostgreSQL 16 |
| Кэш / Pub/Sub | Redis 7 |
| Очередь задач | arq (async Redis queue) |
| Frontend | Next.js 14 (App Router), PWA |
| Парсер меню | Playwright + BeautifulSoup4 |
| QR / PDF | qrcode + ReportLab |
| Хранилище файлов | S3-совместимый (MinIO local / Cloudflare R2 prod) |
| Деплой | Docker Compose → Railway / Render |
| CI/CD | GitHub Actions |

## Структура репозитория

```
menuscan/
├── backend/
│   ├── app/
│   │   ├── api/        # роутеры FastAPI (auth, venues, categories, dishes, menu, orders, tables, parse, qr, analytics)
│   │   ├── core/       # config, security, deps, database, redis, arq_queue
│   │   ├── models/     # SQLAlchemy модели (User, Venue, Table, Category, Dish, ParseJob, Order, OrderItem, QRBatch)
│   │   ├── schemas/    # Pydantic схемы
│   │   ├── services/   # бизнес-логика (auth, venue, menu, order, qr, analytics, table_session)
│   │   ├── ws/         # WebSocket хэндлеры (table, kitchen)
│   │   └── workers/    # parser (BS4+CSV), playwright_parser, arq_worker
│   ├── alembic/
│   │   └── versions/   # 4 миграции: initial_schema, add_orders, fix_orders_fk_cascade, add_parse_job_diff_fields
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   ├── apps/
│   │   ├── dashboard/  # кабинет владельца (Next.js 14, App Router, Tailwind)
│   │   ├── guest/      # PWA для гостей
│   │   └── kitchen/    # кухонный экран
│   └── packages/ui/    # общие компоненты
├── docs/               # вся документация + планы фаз
├── docker-compose.yml
├── docker-compose.prod.yml
├── railway.toml
└── render.yaml
```

## Документация

| Вопрос | Файл |
|---|---|
| Что строим и зачем, требования, монетизация | [docs/01_PRD.md](docs/01_PRD.md) |
| Архитектура, C4-диаграммы, потоки данных, ключевые решения | [docs/02_ARCHITECTURE.md](docs/02_ARCHITECTURE.md) |
| Схема БД (ERD), DDL-скрипты, Redis-структуры | [docs/03_DATABASE.md](docs/03_DATABASE.md) |
| REST API — все эндпоинты с примерами | [docs/04_API.md](docs/04_API.md) |
| WebSocket — события, форматы, reconnect-логика | [docs/05_WEBSOCKET.md](docs/05_WEBSOCKET.md) |
| Роадмап по фазам, Gantt, структура репозитория | [docs/06_ROADMAP.md](docs/06_ROADMAP.md) |

## Статус реализации

### ✅ Фаза 1 — Инфраструктура и бэкенд-ядро (реализовано)

- SQLAlchemy модели + Alembic-миграции: User, Venue, Table, Category, Dish, ParseJob, QRBatch
- Auth API: регистрация, логин, JWT Bearer (`/auth/register`, `/auth/login`, `/auth/me`)
- Venues CRUD + автосоздание столов при создании заведения
- Categories и Dishes CRUD + сортировка (`sort_order`)
- Публичное меню по slug: `GET /menu/{slug}`
- Парсер HTML (BeautifulSoup4) + CSV-fallback + parse-status endpoint
- Генерация QR-кодов и PDF (qrcode + ReportLab) + загрузка в MinIO/S3
- GitHub Actions CI: lint + pytest при каждом push

### ✅ Фаза 2 — Guest App, корзина, заказы, Kitchen Display (реализовано)

- Модели Order + OrderItem + миграция + fix FK cascade
- Redis-клиент + сервис сессии стола (cart, Redis Hash `table_session:{venue_id}:{table_id}`, TTL 4ч)
- arq-очередь для фоновых задач парсера (`arq_queue.py`, `arq_worker.py`)
- Orders REST API + публичный endpoint поиска стола
- WebSocket-хэндлер стола: Redis Pub/Sub синхронизация корзины (`table:{table_id}`)
- WebSocket-хэндлер кухни: броадкаст статусов заказов
- **Guest App** (PWA, Next.js 14): страница меню `[slug]/table/[tableNumber]`, корзина с real-time синхронизацией, ввод имени гостя
  - Компоненты: `DishCard`, `CategoryTabs`, `CartDrawer`, `GuestNameModal`
- **Kitchen Display**: экран кухни `[venueId]` с real-time обновлением статусов
  - Компонент: `OrderCard`

### ✅ Фаза 3 — Dashboard кабинет владельца (реализовано)

**Бэкенд:**
- Аналитика: `GET /venues/{id}/analytics` — выручка, средний чек, топ блюд, разбивка по дням
- Presigned S3 URL для загрузки фото блюд: `POST /venues/{id}/dishes/{dish_id}/upload-url`
- Реордер категорий: `PATCH /venues/{id}/categories/reorder`
- Diff-режим парсера: `POST /venues/{id}/reparse-diff`, `POST /venues/{id}/parse/apply-diff`
- Пагинация и CSV-экспорт заказов: `GET /venues/{id}/orders?page=&limit=&format=csv`
- Health: `GET /health` — возвращает 503 при degraded-состоянии

**Frontend (Next.js 14, App Router, Tailwind CSS):**

Авторизация:
- Логин-страница (`/login`) — форма с httpOnly JWT cookie
- Регистрация (`/register`) — форма с серверным action
- Middleware с редиректами для защищённых маршрутов

Заведения (`/venues`):
- Список заведений с навигацией в меню / столы / аналитику
- `CreateVenueModal` — создание нового заведения
- `EditVenueModal` — редактирование заведения

Редактор меню (`/venues/[id]/menu`):
- `MenuEditor` + `CategoryEditor` — DnD-сортировка категорий (`@dnd-kit`)
- `DishRow` — инлайн-редактирование цены, переключатель доступности
- `ImageUpload` — загрузка фото с кропом (`react-image-crop`) + PUT в S3 presigned URL
- `DiffReview` — модалка с чекбоксами для принятия/отклонения изменений из парсера
- `MenuPageHeader` — шапка с кнопкой запуска парсера

Столы (`/venues/[id]/tables`):
- `TableGrid` — сетка столов с превью QR-кодов
- `QRPreview` — превью QR-кода стола
- API-маршрут `GET /api/venues/[venueId]/qr/download` — скачивание PDF с QR-кодами

Аналитика (`/venues/[id]/analytics`):
- `SummaryCards` — карточки: выручка, заказы, средний чек
- `RevenueChart` — area-chart выручки (Recharts)
- `TopDishesChart` — bar-chart топ-блюд (Recharts)
- `OrdersTable` — таблица заказов с пагинацией и фильтром по статусу, CSV-экспорт
- `PeriodFilter` — фильтр периода аналитики

Инфраструктура:
- `Sidebar` — боковое меню навигации
- `lib/api.ts` — API-клиент
- `lib/actions.ts` — Server Actions
- `lib/auth.ts` — хелперы авторизации

### ✅ Деплой-конфиг (реализовано)

- `docker-compose.yml` — локальная разработка (api + worker + postgres + redis + minio)
- `docker-compose.prod.yml` — production без minio (api + parser-worker + postgres + redis)
- `railway.toml` — Railway deployment (api, worker, pg, redis)
- `render.yaml` — Render deployment
- Dockerfile для playwright parser worker

### ⏳ Фаза 4 — Бета-тест и публичный запуск (не реализовано)

- Интеграция и тестирование Playwright-парсера с реальными сайтами (файл `playwright_parser.py` есть, нужна интеграция)
- Бета-тест с реальными заведениями
- Публичный запуск

### ⏳ Фаза 5 (v2) — Расширения (не реализовано)

- Интеграция с iiko / r_keeper (POS)
- Оплата в меню
- Мультиязычность (i18n)

---

## Роадмап (соло-разработка, старт 2026-07-01)

1. **Фаза 1** ✅ — Инфраструктура, Auth API, парсер HTML, генерация QR PDF
2. **Фаза 2** ✅ — Guest App, WebSocket-корзина, оформление заказа, Kitchen Display
3. **Фаза 3** ✅ — Dashboard (меню, столы, аналитика, регистрация)
4. **Деплой-конфиг** ✅ — Docker Compose prod, Railway, Render
5. **Фаза 4** ⏳ — Playwright-парсер JS-сайтов, бета-тест, публичный запуск
6. **Фаза 5 (v2)** ⏳ — iiko/r_keeper, оплата в меню, мультиязычность

## Ключевые архитектурные решения

- **Синхронизация корзины** — Redis Pub/Sub, канал `table:{table_id}`, работает при горизонтальном масштабировании
- **Сессия стола** — Redis Hash `table_session:{venue_id}:{table_id}`, TTL 4ч
- **Фоновые задачи** — arq (async Redis queue): парсинг меню запускается в воркере
- **Гость анонимный** — UUID в localStorage, имя вводится опционально, без регистрации
- **WebSocket reconnect** — экспоненциальная задержка: 1→2→4→8→16→30 сек
- **Health check** — возвращает 503 при degraded (недоступен Redis или БД)

## MVP-ограничения

- Оплата через меню — нет
- Интеграция с POS (iiko, r_keeper) — нет
- Нативное мобильное приложение — нет (только PWA)
- Мультиязычность — только RU
