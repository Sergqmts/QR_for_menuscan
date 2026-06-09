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
│   │   ├── api/        # роутеры FastAPI
│   │   ├── core/       # config, security, deps
│   │   ├── models/     # SQLAlchemy модели
│   │   ├── schemas/    # Pydantic схемы
│   │   ├── services/   # бизнес-логика
│   │   ├── ws/         # WebSocket хэндлеры
│   │   └── workers/    # parser, qr_generator
│   ├── alembic/
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   ├── apps/
│   │   ├── dashboard/  # кабинет владельца
│   │   ├── guest/      # PWA для гостей
│   │   └── kitchen/    # кухонный экран
│   └── packages/ui/    # общие компоненты
├── docs/               # вся документация
└── docker-compose.yml
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

## Роадмап (соло-разработка, старт 2026-07-01)

1. **Фаза 1** — Инфраструктура, Auth API, парсер HTML, генерация QR PDF
2. **Фаза 2** — Guest App, WebSocket-корзина, оформление заказа, Kitchen Display
3. **Фаза 3** — Dashboard (меню, столы, аналитика)
4. **Фаза 4** — Playwright-парсер JS-сайтов, бета-тест, публичный запуск
5. **Фаза 5 (v2)** — iiko/r_keeper, оплата в меню, мультиязычность

## Ключевые архитектурные решения

- **Синхронизация корзины** — Redis Pub/Sub, канал `table:{table_id}`, работает при горизонтальном масштабировании
- **Сессия стола** — Redis Hash `table_session:{venue_id}:{table_id}`, TTL 4ч
- **Гость анонимный** — UUID в localStorage, имя вводится опционально, без регистрации
- **WebSocket reconnect** — экспоненциальная задержка: 1→2→4→8→16→30 сек

## MVP-ограничения

- Оплата через меню — нет
- Интеграция с POS (iiko, r_keeper) — нет
- Нативное мобильное приложение — нет (только PWA)
- Мультиязычность — только RU
