# Архитектура системы — MenuScan

> Версия: 1.0

---

## 1. Обзор стека

| Слой | Технология | Обоснование |
|---|---|---|
| Backend API | FastAPI (Python) | Async из коробки, автодокументация, типизация |
| WebSocket | FastAPI WebSocket + Redis Pub/Sub | Масштабируемая синхронизация между инстансами |
| База данных | PostgreSQL 16 | Реляционные данные, JSONB для гибкого меню |
| Кэш / очереди | Redis 7 | Pub/Sub для WS, кэш меню, сессии столов |
| Парсер | Playwright + BeautifulSoup4 | Поддержка JS-рендеренных страниц |
| Frontend (Dashboard) | Next.js 14 (App Router) | SSR для SEO, React для интерактивности |
| Frontend (Гость / Кухня) | Next.js 14 PWA | Один фреймворк, офлайн-поддержка |
| Хранилище файлов | S3-совместимый (MinIO / Cloudflare R2) | Фото блюд, QR PDF |
| Генерация QR | `qrcode` (Python lib) + ReportLab | Пакетная генерация PDF |
| Деплой | Docker Compose → Railway / Render | Простой старт, лёгкий переезд |
| CI/CD | GitHub Actions | Авто-тесты + деплой на push |

---

## 2. Общая архитектура (C4 — Context)

```mermaid
C4Context
    title Контекстная диаграмма MenuScan

    Person(owner, "Владелец заведения", "Подключает меню, получает QR, смотрит аналитику")
    Person(guest, "Гость", "Сканирует QR, заказывает через телефон")
    Person(chef, "Повар / кухня", "Видит входящие заказы на экране")

    System(menuscan, "MenuScan", "SaaS-платформа цифрового меню")

    System_Ext(restaurant_site, "Сайт ресторана", "Источник данных меню")
    System_Ext(pos, "POS-системы (iiko, r_keeper)", "Приём заказов (v2)")
    System_Ext(s3, "S3-хранилище", "Фото блюд, QR PDF")

    Rel(owner, menuscan, "Управляет через Dashboard")
    Rel(guest, menuscan, "Использует через браузер (QR)")
    Rel(chef, menuscan, "Смотрит Kitchen Display")
    Rel(menuscan, restaurant_site, "Парсит меню")
    Rel(menuscan, pos, "Отправляет заказы (webhook)")
    Rel(menuscan, s3, "Хранит медиафайлы")
```

---

## 3. Компонентная архитектура (C4 — Container)

```mermaid
C4Container
    title Контейнерная диаграмма MenuScan

    Person(owner, "Владелец")
    Person(guest, "Гость")
    Person(chef, "Повар")

    Container(dashboard, "Dashboard SPA", "Next.js 14", "Управление заведением, меню, аналитика")
    Container(guest_app, "Guest App (PWA)", "Next.js 14 PWA", "Меню, корзина стола, статус заказа")
    Container(kitchen_app, "Kitchen Display", "Next.js 14", "Список заказов по столам, смена статусов")

    Container(api, "Backend API", "FastAPI", "REST API + WebSocket сервер")
    Container(parser, "Menu Parser Service", "Python + Playwright", "Scraping сайтов, нормализация меню")
    Container(qr_service, "QR Generator", "Python + qrcode + ReportLab", "Генерация QR, сборка PDF")

    ContainerDb(pg, "PostgreSQL", "Database", "Заведения, меню, заказы, пользователи")
    ContainerDb(redis, "Redis", "Cache + Pub/Sub", "Сессии столов, синхронизация корзины")
    ContainerDb(s3, "S3 Storage", "Object Storage", "Фото блюд, QR PDF")

    Rel(owner, dashboard, "HTTPS")
    Rel(guest, guest_app, "HTTPS / PWA")
    Rel(chef, kitchen_app, "HTTPS")

    Rel(dashboard, api, "REST API / HTTPS")
    Rel(guest_app, api, "REST API + WebSocket")
    Rel(kitchen_app, api, "REST API + WebSocket")

    Rel(api, pg, "asyncpg / SQLAlchemy")
    Rel(api, redis, "aioredis")
    Rel(api, parser, "Internal HTTP / Task queue")
    Rel(api, qr_service, "Internal HTTP")
    Rel(api, s3, "boto3")

    Rel(parser, pg, "Сохраняет меню")
    Rel(qr_service, s3, "Загружает PDF")
```

---

## 4. Поток данных — подключение заведения

```mermaid
sequenceDiagram
    actor Owner as Владелец
    participant Dashboard
    participant API
    participant Parser
    participant DB as PostgreSQL
    participant S3

    Owner->>Dashboard: Вводит URL сайта + кол-во столов
    Dashboard->>API: POST /venues (url, table_count)
    API->>DB: Создаёт запись venue (status=pending)
    API->>Parser: Задача: parse_menu(url, venue_id)
    API-->>Dashboard: 202 Accepted {job_id}

    Parser->>Parser: Playwright → рендер страницы
    Parser->>Parser: BeautifulSoup → извлечение блюд
    Parser->>DB: Сохраняет categories + dishes
    Parser->>API: Callback: job complete

    API->>API: Генерирует QR-коды (N столов)
    API->>S3: Загружает PDF с QR-кодами
    API->>DB: venue.status = active
    API->>Dashboard: WebSocket push: parsing_done
    Dashboard->>Owner: Показывает предпросмотр меню + ссылку на PDF
```

---

## 5. Поток данных — гость за столом

```mermaid
sequenceDiagram
    actor G1 as Гость 1
    actor G2 as Гость 2
    participant App as Guest App
    participant API
    participant Redis
    participant DB as PostgreSQL
    participant Kitchen as Кухонный экран

    G1->>App: Сканирует QR → открывает /menu/venue_id/table_id
    App->>API: GET /menu/{venue_id} → получает блюда
    App->>API: WS CONNECT /ws/table/{table_id}
    API->>Redis: Создаёт сессию стола (если нет)
    API-->>App: WS: table_state (текущая корзина)

    G2->>App: Сканирует тот же QR
    App->>API: WS CONNECT /ws/table/{table_id}
    API->>Redis: Присоединяется к существующей сессии
    API-->>App: WS: table_state (то же состояние)

    G1->>App: Добавляет блюдо в корзину
    App->>API: WS EVENT: add_item {dish_id, qty, comment, guest_name}
    API->>Redis: Обновляет состояние корзины стола
    API->>Redis: PUBLISH table:{table_id} → cart_updated
    Redis-->>API: (инстанс 2 получает событие)
    API-->>App: WS BROADCAST: cart_updated (G1 и G2 видят изменение)

    G1->>App: Нажимает «Оформить заказ»
    App->>API: POST /orders {table_id, items}
    API->>DB: Создаёт order + order_items
    API->>Redis: PUBLISH kitchen:{venue_id} → new_order
    Redis-->>Kitchen: WS: new_order (появляется тикет)
    API-->>App: WS: order_confirmed {order_id, status: accepted}
```

---

## 6. Поток данных — смена статуса заказа

```mermaid
sequenceDiagram
    participant Kitchen as Кухонный экран
    participant API
    participant Redis
    participant App as Guest App

    Kitchen->>API: PATCH /orders/{order_id}/status {status: cooking}
    API->>DB: Обновляет order.status
    API->>Redis: PUBLISH table:{table_id} → order_status_changed
    Redis-->>App: WS: order_status_changed {status: cooking}
    App->>App: Показывает "Готовится..."

    Kitchen->>API: PATCH /orders/{order_id}/status {status: ready}
    API->>Redis: PUBLISH table:{table_id} → order_status_changed
    Redis-->>App: WS: order_status_changed {status: ready}
    App->>App: Показывает "Заказ готов! 🎉"
```

---

## 7. Инфраструктура деплоя

```mermaid
graph TB
    subgraph Internet
        CDN[Cloudflare CDN]
    end

    subgraph Railway / Render
        subgraph App Cluster
            API1[FastAPI instance 1]
            API2[FastAPI instance 2]
        end
        subgraph Workers
            Parser[Parser Worker]
            QRGen[QR Generator]
        end
        PG[(PostgreSQL)]
        Redis[(Redis)]
    end

    subgraph Cloudflare R2
        S3[Object Storage]
    end

    CDN --> API1
    CDN --> API2
    API1 <--> Redis
    API2 <--> Redis
    API1 --> PG
    API2 --> PG
    API1 --> Parser
    API1 --> QRGen
    QRGen --> S3
    Parser --> PG
```

---

## 8. Решения по ключевым техническим вопросам

### 8.1 Синхронизация корзины между устройствами
**Решение:** Redis Pub/Sub.  
Каждый WebSocket-хэндлер подписывается на канал `table:{table_id}`. При любом изменении корзины API публикует событие в Redis — все подключённые клиенты стола мгновенно получают обновление. Это работает и при горизонтальном масштабировании (несколько инстансов API).

### 8.2 Парсер — JS-рендеренные сайты
**Решение:** Playwright headless browser.  
Запускается как отдельный Worker-процесс. Получает задачи через внутренний HTTP. Лимит: одна задача парсинга не дольше 60 сек, после — fallback на ручной ввод.

### 8.3 Идентификация гостя
**Решение:** Анонимная сессия.  
При первом открытии генерируется `guest_id` (UUID) в localStorage. Гость вводит имя (опционально). Нет регистрации — снижаем порог входа до нуля.

### 8.4 Масштабирование WebSocket
**Решение:** Redis Pub/Sub как message broker между инстансами.  
Клиент может подключиться к любому инстансу API — все синхронизированы через Redis.

### 8.5 Консистентность корзины
**Решение:** Корзина хранится в Redis (быстрый доступ) и реплицируется в PostgreSQL при оформлении заказа. TTL сессии стола — 4 часа (сбрасывается при активности).
