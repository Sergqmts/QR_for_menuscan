# MenuScan Phase 3 — Dashboard Design

**Date:** 2026-06-10  
**Status:** Approved  
**Scope:** Owner dashboard — menu editor, table/QR management, analytics

---

## Overview

Phase 3 builds the owner-facing dashboard SPA: a Next.js 14 App Router application at `frontend/apps/dashboard/`. It lets venue owners manage their menu, tables, QR codes, and view sales analytics — completing the full product loop that started in Phases 1 and 2.

**Exit criteria:** An owner can log in, fully manage their venue (menu, photos, tables, QR), view revenue and top-dish analytics, and export order history.

---

## Architecture

### Tech Stack

| Layer | Technology |
|---|---|
| Frontend framework | Next.js 14 App Router |
| UI components | shadcn/ui (Radix UI + Tailwind) |
| Charts | Recharts |
| Image crop | react-image-crop |
| Drag-and-drop | dnd-kit |
| Tables | TanStack Table (via shadcn DataTable) |

### Data Fetching Strategy

**Mixed RSC + Client Islands** — the standard Next.js 14 App Router pattern:

- **Server Components** handle initial data fetching (categories, dishes, orders, analytics) and page shells. No client-side JS cost for read-heavy views.
- **Client Components** are scoped to interactive islands: `MenuEditor`, `DiffReview`, `TableGrid`, `RevenueChart`, `TopDishesChart`, `OrdersTable`.
- **Server Actions** handle all mutations, keeping API call logic server-side and type-safe.

### Auth Flow

Login → `POST /auth/login` → JWT stored in `httpOnly` cookie → Next.js middleware reads cookie on every protected route → redirects to `/login` if missing or expired.

Using `httpOnly` cookie (not localStorage) to prevent XSS token theft.

---

## File Structure

```
frontend/apps/dashboard/
├── app/
│   ├── layout.tsx                        # RootLayout, ThemeProvider
│   ├── middleware.ts                     # JWT cookie check, redirect to /login
│   ├── (auth)/
│   │   └── login/
│   │       └── page.tsx                  # RSC shell, LoginForm is Client
│   └── (dashboard)/
│       ├── layout.tsx                    # Sidebar + top bar (RSC)
│       ├── page.tsx                      # Redirect → /venues
│       └── venues/
│           ├── page.tsx                  # Venue list (RSC)
│           └── [id]/
│               ├── menu/page.tsx         # Menu editor (RSC shell)
│               ├── tables/page.tsx       # Tables & QR (RSC shell)
│               └── analytics/page.tsx   # Analytics (RSC shell)
├── components/
│   ├── menu/
│   │   ├── MenuEditor.tsx               # Client — category list + dish table
│   │   ├── DishRow.tsx                  # Client — inline price/availability edit
│   │   ├── CategoryEditor.tsx           # Client — drag-and-drop category reorder
│   │   ├── DiffReview.tsx               # Client — per-row diff accept/reject
│   │   └── ImageUpload.tsx              # Client — react-image-crop → S3
│   ├── tables/
│   │   ├── TableGrid.tsx                # Client — cards grid, inline name edit
│   │   └── QRPreview.tsx                # Client — QR image + download action
│   └── analytics/
│       ├── SummaryCards.tsx             # RSC — 4 stat cards
│       ├── PeriodFilter.tsx             # Client — 7d/30d/90d + date range picker
│       ├── RevenueChart.tsx             # Client — Recharts AreaChart
│       ├── TopDishesChart.tsx           # Client — Recharts horizontal BarChart
│       └── OrdersTable.tsx              # Client — TanStack Table, server pagination
├── lib/
│   ├── api.ts                           # Server-side fetch wrappers (uses cookie)
│   ├── actions.ts                       # Server Actions for all mutations
│   └── auth.ts                          # getServerSession() helper
├── package.json
├── next.config.js
├── tailwind.config.js
└── tsconfig.json
```

---

## Section 1: Menu Management

### Page: `/venues/[id]/menu`

RSC fetches categories + dishes for the venue, renders sidebar and `<MenuEditor>` with initial data.

### MenuEditor (Client Component)

Two-panel layout:
- **Left:** `CategoryEditor` — list of categories with dnd-kit drag handles for reorder. Inline name edit, visibility toggle, delete button.
- **Right:** `DishRow` table for the active category.

### DishRow — Inline Editing

Each row shows: photo thumbnail, name, weight, price, availability switch, actions.

- **Price edit:** click → `<Input>` replaces the cell → blur or Enter → Server Action `updateDishPrice(dishId, price)` → `PATCH /venues/{id}/dishes/{dish_id}`. Optimistic update in local state.
- **Availability toggle:** shadcn `Switch` → Server Action `toggleDishAvailability(dishId)`. Optimistic flip, revert on error.
- **Photo:** click thumbnail → `ImageUpload` modal.

### ImageUpload Modal

1. `<input type="file">` → file selected
2. `react-image-crop` with `aspect=1` — user crops to square
3. Canvas `toBlob()` → `Blob`
4. Server Action `uploadDishImage(dishId, blob)`:
   - Backend issues presigned S3 PUT URL via `POST /venues/{id}/dishes/{dish_id}/upload-url`
   - Client PUTs blob directly to S3 (presigned URL)
   - Server Action then calls `PATCH /venues/{id}/dishes/{dish_id}` with the resulting `image_url`
5. Modal closes, row thumbnail updates.

### Re-parse Diff

1. Button «Обновить из источника» → Server Action triggers `POST /venues/{id}/parse`
2. Client polls `GET /venues/{id}/parse-status` every 2s until `status === "done"`
3. `DiffReview` modal opens with parse results:

```
┌─────────────────────────────────────────────────────────┐
│ ☑ Борщ            350 ₽ → 390 ₽                         │
│ ☑ Котлета         420 ₽ → 420 ₽  [вес: 200г → 180г]    │
│ ☐ Новое блюдо     — → 280 ₽                             │
│ ☑ Удалённое       320 ₽ → [отсутствует]                 │
└─────────────────────────────────────────────────────────┘
  [Принять выбранные]  [Отмена]
```

4. «Принять выбранные» → Server Action `applyParseDiff(changes[])` → batch `PATCH` requests.

### Server Actions (actions.ts)

```typescript
updateDishPrice(dishId: string, price: number): Promise<void>
toggleDishAvailability(dishId: string, available: boolean): Promise<void>
uploadDishImage(dishId: string, blob: Blob): Promise<string>  // returns image_url
reorderCategories(venueId: string, categoryIds: string[]): Promise<void>
applyParseDiff(venueId: string, changes: DiffChange[]): Promise<void>
```

---

## Section 2: Tables & QR Management

### Page: `/venues/[id]/tables`

RSC fetches all tables for the venue, renders `<TableGrid>`.

### TableGrid (Client Component)

CSS grid of `TableCard` components. Each card shows:
- Table number + label (inline editable — click → `<Input>` → blur/Enter → `PATCH`)
- QR code preview (`<img src={qr_code_url}>` or placeholder)
- Active/inactive toggle

**Panel actions:**
- «Скачать PDF» → `GET /venues/{id}/qr/download` → open S3 link
- «Перегенерировать QR» → `POST /venues/{id}/qr/generate` → poll status → refresh cards
- «Добавить столы» → shadcn `Dialog` with number input → `PATCH /venues/{id}` with updated `table_count`

When `qr_code_url` is null: placeholder card with a «Сгенерировать» button.

---

## Section 3: Analytics

### Page: `/venues/[id]/analytics`

RSC reads `?from` and `?to` query params (default: last 30 days), fetches from new backend endpoint, renders `<SummaryCards>` (RSC) and passes data to client charts.

### New Backend Endpoint

`GET /venues/{id}/analytics?from=2026-05-01&to=2026-06-01`

```json
{
  "summary": {
    "orders": 142,
    "revenue": 87400.00,
    "avg_check": 615.49,
    "top_dish": "Борщ"
  },
  "daily": [
    { "date": "2026-05-01", "revenue": 4200.00, "orders": 7 }
  ],
  "top_dishes": [
    { "name": "Борщ", "count": 34, "revenue": 11900.00 }
  ]
}
```

Implementation: three SQL aggregation queries in a new `analytics_service.py`. All run in a single async gather.

### SummaryCards (RSC)

Four stat cards rendered on the server: total orders, revenue, avg check, top dish name. No JS needed.

### PeriodFilter (Client Component)

Buttons «7д / 30д / 90д» + shadcn `DatePickerWithRange` for custom range. On change → `router.push` with updated `?from=&to=` query params → RSC re-fetches.

### Charts (Client Components)

- `RevenueChart`: Recharts `AreaChart`, X axis = date, Y axis = revenue in ₽, tooltip shows orders count.
- `TopDishesChart`: Recharts horizontal `BarChart`, top 10 dishes by order count.

### OrdersTable (Client Component)

shadcn `DataTable` built on TanStack Table:
- Columns: date/time, table label, status (badge), total amount, item count
- Filter by status (shadcn `Select`)
- Sort by date (default desc) and amount
- Server-side pagination: `GET /venues/{id}/orders?page=&limit=20`
- «Экспорт CSV» button → `GET /venues/{id}/orders?format=csv` → browser download

---

## Backend Changes

Phase 3 requires three new backend additions:

1. **`GET /venues/{id}/analytics`** — new endpoint in `backend/app/api/analytics.py`, backed by `analytics_service.py` with three aggregation queries.

2. **`POST /venues/{id}/dishes/{dish_id}/upload-url`** — returns a presigned S3 PUT URL for direct browser upload. Reuses existing S3 client from `qr_service.py`.

3. **`PATCH /venues/{id}/categories/reorder`** — accepts `{ category_ids: string[] }`, bulk-updates `sort_order` values. Single transaction.

All existing endpoints from Phases 1–2 remain unchanged.

---

## Error Handling

- Inline edit failures: revert optimistic update, show shadcn `toast` with error message.
- Parse diff: if polling exceeds 60s, show «Парсинг занял слишком долго» toast and reset button.
- Image upload: if S3 upload fails, show error toast, keep old image.
- Analytics: if date range returns no data, show empty state illustration per chart.
- Auth: middleware redirects expired sessions to `/login` with `?redirect=` param for post-login return.

---

## Out of Scope (Phase 3)

- Real-time order notifications in dashboard (Phase 4+)
- Multi-venue switching in one session (single venue per login is sufficient for MVP)
- Role-based access (admin vs staff) — single owner role only
- Dark mode
