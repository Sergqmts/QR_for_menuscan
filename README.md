# MenuScan

SaaS QR-меню с совместной корзиной стола для кафе и ресторанов.

## Быстрый старт

```bash
cp backend/.env.example backend/.env
docker compose up -d
```

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- MinIO Console: http://localhost:9001 (minioadmin/minioadmin)

## Тесты

```bash
cd backend
pytest tests/ -v
```

## Миграции

```bash
cd backend
alembic upgrade head
```
