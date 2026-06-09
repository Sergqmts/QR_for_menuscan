# MenuScan — Документация

> SaaS-платформа цифрового меню с совместной корзиной для кафе и ресторанов

---

## Структура документации

| Файл | Содержание |
|---|---|
| [01_PRD.md](./01_PRD.md) | Product Requirements Document — что строим и зачем |
| [02_ARCHITECTURE.md](./02_ARCHITECTURE.md) | Архитектура системы, C4-диаграммы, стек, ключевые решения |
| [03_DATABASE.md](./03_DATABASE.md) | Схема БД (ERD), DDL-скрипты, Redis-структуры |
| [04_API.md](./04_API.md) | REST API — все эндпоинты с примерами запросов и ответов |
| [05_WEBSOCKET.md](./05_WEBSOCKET.md) | WebSocket — все события, форматы, reconnect-логика |
| [06_ROADMAP.md](./06_ROADMAP.md) | Роадмап разработки по фазам с Gantt-диаграммой |

---

## Быстрый старт (для разработки)

```bash
# Клонировать репозиторий
git clone https://github.com/your-org/menuscan.git
cd menuscan

# Запустить инфраструктуру
docker-compose up -d

# Backend
cd backend
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload

# Frontend (guest app)
cd frontend/apps/guest
npm install && npm run dev
```

---

## Ключевые URL (local dev)

| Сервис | URL |
|---|---|
| API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| Dashboard | http://localhost:3000 |
| Guest App | http://localhost:3001 |
| Kitchen Display | http://localhost:3002 |
| Redis Commander | http://localhost:8081 |
