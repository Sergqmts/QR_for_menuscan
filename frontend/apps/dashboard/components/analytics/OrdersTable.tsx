"use client";

import { useState, useEffect } from "react";

const STATUSES = [
  { value: "", label: "Все статусы" },
  { value: "accepted", label: "Принят" },
  { value: "cooking", label: "Готовится" },
  { value: "ready", label: "Готов" },
  { value: "served", label: "Подан" },
  { value: "cancelled", label: "Отменён" },
];

const STATUS_STYLE: Record<string, string> = {
  accepted: "bg-blue-100 text-blue-700",
  cooking: "bg-yellow-100 text-yellow-700",
  ready: "bg-green-100 text-green-700",
  served: "bg-gray-100 text-gray-600",
  cancelled: "bg-red-100 text-red-600",
};

interface Order {
  id: string;
  status: string;
  total_amount: string;
  created_at: string;
  items: Array<{ id: string }>;
}

export default function OrdersTable({ venueId }: { venueId: string }) {
  const [orders, setOrders] = useState<Order[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);

  const LIMIT = 20;

  useEffect(() => {
    const sp = new URLSearchParams({ page: String(page), limit: String(LIMIT) });
    if (status) sp.set("status", status);
    setLoading(true);
    fetch(`/api/venues/${venueId}/orders?${sp}`)
      .then((r) => r.json())
      .then((d) => { setOrders(d.orders ?? []); setTotal(d.total ?? 0); })
      .finally(() => setLoading(false));
  }, [page, status, venueId]);

  async function handleExportCSV() {
    const sp = new URLSearchParams({ format: "csv" });
    if (status) sp.set("status", status);
    const res = await fetch(`/api/venues/${venueId}/orders?${sp}`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `orders_${venueId}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  const totalPages = Math.ceil(total / LIMIT);

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <select
          value={status}
          onChange={(e) => { setStatus(e.target.value); setPage(1); }}
          className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-orange-500"
        >
          {STATUSES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
        <button onClick={handleExportCSV} className="ml-auto text-sm border border-gray-200 text-gray-600 px-3 py-1.5 rounded-lg hover:bg-gray-50 transition-colors">
          Экспорт CSV
        </button>
      </div>

      {loading ? (
        <div className="py-10 text-center text-gray-400 text-sm">Загрузка...</div>
      ) : orders.length === 0 ? (
        <div className="py-10 text-center text-gray-400 text-sm">Заказов нет</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-gray-500 font-medium">
                <th className="text-left py-3 px-2">Дата и время</th>
                <th className="text-left py-3 px-2">Статус</th>
                <th className="text-right py-3 px-2">Сумма</th>
                <th className="text-right py-3 px-2">Позиций</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => (
                <tr key={order.id} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="py-3 px-2 text-gray-600">
                    {new Date(order.created_at).toLocaleString("ru-RU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
                  </td>
                  <td className="py-3 px-2">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLE[order.status] ?? "bg-gray-100 text-gray-600"}`}>
                      {STATUSES.find((s) => s.value === order.status)?.label ?? order.status}
                    </span>
                  </td>
                  <td className="py-3 px-2 text-right font-medium text-gray-900">
                    {Number(order.total_amount).toLocaleString("ru-RU")} ₽
                  </td>
                  <td className="py-3 px-2 text-right text-gray-500">{order.items.length}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center gap-2 mt-4">
          <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm disabled:opacity-40 hover:bg-gray-50">
            ← Назад
          </button>
          <span className="text-sm text-gray-500">Стр. {page} из {totalPages}</span>
          <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages} className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm disabled:opacity-40 hover:bg-gray-50">
            Вперёд →
          </button>
        </div>
      )}
    </div>
  );
}
