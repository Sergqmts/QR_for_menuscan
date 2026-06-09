# REST API Specification — MenuScan

> Base URL: `https://api.menuscan.io/v1`  
> Auth: Bearer JWT (для защищённых эндпоинтов)  
> Content-Type: `application/json`

---

## Условные обозначения

- 🔒 — требует авторизации (JWT владельца)
- 🔓 — публичный эндпоинт
- 🍳 — только для кухонного экрана

---

## 1. Auth

### POST `/auth/register`
Регистрация нового владельца.

**Request:**
```json
{
  "email": "owner@cafe.ru",
  "password": "SecurePass123",
  "full_name": "Иван Петров"
}
```

**Response `201`:**
```json
{
  "user": {
    "id": "uuid",
    "email": "owner@cafe.ru",
    "full_name": "Иван Петров"
  },
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

**Errors:** `400` email уже занят, `422` валидация.

---

### POST `/auth/login`
Авторизация по email/password.

**Request:**
```json
{
  "email": "owner@cafe.ru",
  "password": "SecurePass123"
}
```

**Response `200`:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

**Errors:** `401` неверные данные.

---

### POST `/auth/refresh` 🔒
Обновление access token.

**Response `200`:**
```json
{
  "access_token": "eyJ...",
  "expires_in": 86400
}
```

---

## 2. Venues (заведения)

### POST `/venues` 🔒
Создание заведения и запуск парсинга меню.

**Request:**
```json
{
  "name": "Кафе Белуга",
  "website_url": "https://beluga-cafe.ru/menu",
  "table_count": 12,
  "address": "Москва, ул. Ленина 5",
  "cuisine_type": "Европейская"
}
```

**Response `202`:**
```json
{
  "venue": {
    "id": "uuid",
    "name": "Кафе Белуга",
    "slug": "beluga-cafe",
    "parse_status": "parsing"
  },
  "parse_job_id": "uuid"
}
```

---

### GET `/venues` 🔒
Список заведений текущего пользователя.

**Response `200`:**
```json
{
  "venues": [
    {
      "id": "uuid",
      "name": "Кафе Белуга",
      "slug": "beluga-cafe",
      "table_count": 12,
      "parse_status": "done",
      "is_active": true,
      "subscription": {
        "plan": "business",
        "status": "active"
      }
    }
  ]
}
```

---

### GET `/venues/{venue_id}` 🔒
Детальная информация о заведении.

**Response `200`:**
```json
{
  "id": "uuid",
  "name": "Кафе Белуга",
  "slug": "beluga-cafe",
  "address": "Москва, ул. Ленина 5",
  "cuisine_type": "Европейская",
  "logo_url": "https://...",
  "table_count": 12,
  "parse_status": "done",
  "settings": {
    "primary_color": "#FF6B35",
    "language": "ru",
    "show_calories": true
  },
  "is_active": true,
  "created_at": "2026-01-15T10:00:00Z"
}
```

---

### PATCH `/venues/{venue_id}` 🔒
Обновление настроек заведения.

**Request** (любые поля):
```json
{
  "name": "Белуга Bistro",
  "settings": {
    "primary_color": "#2D6BE4"
  }
}
```

**Response `200`:** Обновлённый объект venue.

---

### POST `/venues/{venue_id}/reparse` 🔒
Повторный запуск парсера (при обновлении меню на сайте).

**Response `202`:**
```json
{
  "parse_job_id": "uuid",
  "status": "queued"
}
```

---

### GET `/venues/{venue_id}/parse-status` 🔒
Статус задачи парсинга (для polling или SSE).

**Response `200`:**
```json
{
  "job_id": "uuid",
  "status": "done",
  "dishes_found": 47,
  "finished_at": "2026-01-15T10:02:30Z"
}
```

---

## 3. Tables (столы)

### GET `/venues/{venue_id}/tables` 🔒
Список столов заведения.

**Response `200`:**
```json
{
  "tables": [
    {
      "id": "uuid",
      "number": 1,
      "label": "Стол 1",
      "qr_code_url": "https://s3.../qr/table-1.png",
      "is_active": true
    }
  ]
}
```

---

### PATCH `/venues/{venue_id}/tables/{table_id}` 🔒
Переименование или деактивация стола.

**Request:**
```json
{
  "label": "Терраса VIP",
  "is_active": true
}
```

---

### POST `/venues/{venue_id}/qr/generate` 🔒
Генерация или перегенерация QR-кодов и PDF.

**Request:**
```json
{
  "table_count": 15
}
```

**Response `202`:**
```json
{
  "batch_id": "uuid",
  "status": "generating"
}
```

---

### GET `/venues/{venue_id}/qr/download` 🔒
Скачать PDF с QR-кодами.

**Response `200`:** Редирект на S3 URL PDF-файла.

---

## 4. Menu (публичное меню)

### GET `/menu/{venue_slug}` 🔓
Получение полного меню заведения (для Guest App).

**Query params:**
- `lang` — язык (`ru`, `en`), по умолчанию `ru`

**Response `200`:**
```json
{
  "venue": {
    "id": "uuid",
    "name": "Кафе Белуга",
    "logo_url": "https://...",
    "settings": {
      "primary_color": "#FF6B35"
    }
  },
  "categories": [
    {
      "id": "uuid",
      "name": "Завтраки",
      "slug": "zavtraki",
      "sort_order": 1,
      "dishes": [
        {
          "id": "uuid",
          "name": "Яйца Бенедикт",
          "description": "Яйца пашот, голландский соус, тосты",
          "price": 490.00,
          "weight": "280г",
          "calories": "540 ккал",
          "image_url": "https://...",
          "tags": ["vegetarian"],
          "allergens": ["gluten", "eggs"],
          "is_available": true
        }
      ]
    }
  ]
}
```

**Errors:** `404` заведение не найдено или неактивно.

---

## 5. Dishes (управление блюдами)

### GET `/venues/{venue_id}/dishes` 🔒
Список всех блюд (для редактора Dashboard).

**Query params:**
- `category_id` — фильтр по категории
- `is_available` — `true`/`false`
- `search` — поиск по названию

---

### POST `/venues/{venue_id}/dishes` 🔒
Добавление нового блюда вручную.

**Request:**
```json
{
  "category_id": "uuid",
  "name": "Брускетта с томатами",
  "description": "Хрустящий хлеб, помидоры черри, базилик",
  "price": 320.00,
  "weight": "180г",
  "calories": "290 ккал",
  "tags": ["vegetarian"],
  "allergens": ["gluten"]
}
```

**Response `201`:** Созданный объект блюда.

---

### PATCH `/venues/{venue_id}/dishes/{dish_id}` 🔒
Обновление блюда.

**Request** (любые поля):
```json
{
  "price": 350.00,
  "is_available": false
}
```

---

### DELETE `/venues/{venue_id}/dishes/{dish_id}` 🔒
Удаление блюда.

**Response `204`:** No Content.

---

### POST `/venues/{venue_id}/dishes/{dish_id}/image` 🔒
Загрузка фото блюда.

**Request:** `multipart/form-data` с полем `image` (JPEG/PNG, max 5MB).

**Response `200`:**
```json
{
  "image_url": "https://cdn.menuscan.io/dishes/uuid.jpg"
}
```

---

## 6. Orders (заказы)

### POST `/orders` 🔓
Оформление заказа гостем.

**Request:**
```json
{
  "venue_id": "uuid",
  "table_id": "uuid",
  "session_id": "redis-session-id",
  "items": [
    {
      "dish_id": "uuid",
      "quantity": 2,
      "comment": "без лука",
      "guest_id": "guest-uuid-from-localstorage",
      "guest_name": "Алексей"
    },
    {
      "dish_id": "uuid",
      "quantity": 1,
      "comment": "",
      "guest_id": "another-guest-uuid",
      "guest_name": "Мария"
    }
  ],
  "comment": "Поздравляем с днём рождения!"
}
```

**Response `201`:**
```json
{
  "order_id": "uuid",
  "status": "accepted",
  "total_amount": 1280.00,
  "created_at": "2026-01-15T19:35:00Z"
}
```

---

### GET `/orders/{order_id}/status` 🔓
Статус заказа (для Guest App — polling или WebSocket).

**Response `200`:**
```json
{
  "order_id": "uuid",
  "status": "cooking",
  "updated_at": "2026-01-15T19:37:00Z"
}
```

---

### GET `/venues/{venue_id}/orders` 🔒 🍳
Список заказов заведения (для Dashboard и Kitchen Display).

**Query params:**
- `status` — фильтр по статусу
- `table_id` — фильтр по столу
- `date` — дата в формате `YYYY-MM-DD`
- `limit` — по умолчанию `50`
- `offset`

**Response `200`:**
```json
{
  "orders": [
    {
      "id": "uuid",
      "table": { "id": "uuid", "number": 5, "label": "Стол 5" },
      "status": "cooking",
      "total_amount": 1280.00,
      "items_count": 3,
      "created_at": "2026-01-15T19:35:00Z",
      "items": [
        {
          "dish_name": "Яйца Бенедикт",
          "quantity": 2,
          "unit_price": 490.00,
          "comment": "без лука",
          "guest_name": "Алексей"
        }
      ]
    }
  ],
  "total": 12
}
```

---

### PATCH `/orders/{order_id}/status` 🔒 🍳
Смена статуса заказа кухней.

**Request:**
```json
{
  "status": "cooking"
}
```

**Допустимые переходы:**
```
accepted → cooking → ready → served
any → cancelled (только владелец)
```

**Response `200`:** Обновлённый заказ.

---

## 7. Analytics

### GET `/venues/{venue_id}/analytics/summary` 🔒
Сводная аналитика.

**Query params:** `period` — `day`, `week`, `month`

**Response `200`:**
```json
{
  "period": "week",
  "total_orders": 143,
  "total_revenue": 187430.00,
  "avg_check": 1310.00,
  "avg_time_to_order_sec": 240,
  "top_dishes": [
    { "dish_name": "Яйца Бенедикт", "orders_count": 38 },
    { "dish_name": "Капучино", "orders_count": 97 }
  ]
}
```

---

## 8. Kitchen (кухонный экран)

### GET `/kitchen/{venue_id}/pin` 🔒
Получение / сброс PIN для доступа к кухонному экрану.

**Response `200`:**
```json
{
  "pin": "4821",
  "expires_at": null
}
```

### POST `/kitchen/auth`
Авторизация на кухонном экране по PIN.

**Request:**
```json
{
  "venue_id": "uuid",
  "pin": "4821"
}
```

**Response `200`:**
```json
{
  "kitchen_token": "eyJ...",
  "venue_id": "uuid"
}
```

---

## 9. Общие коды ошибок

| Код | Смысл |
|---|---|
| `400` | Невалидные данные запроса |
| `401` | Не авторизован / истёк токен |
| `403` | Нет прав на ресурс |
| `404` | Ресурс не найден |
| `409` | Конфликт (например, email уже занят) |
| `422` | Ошибка валидации Pydantic |
| `429` | Rate limit exceeded |
| `500` | Внутренняя ошибка сервера |

**Формат ошибки:**
```json
{
  "error": {
    "code": "VENUE_NOT_FOUND",
    "message": "Заведение не найдено или неактивно",
    "details": null
  }
}
```
