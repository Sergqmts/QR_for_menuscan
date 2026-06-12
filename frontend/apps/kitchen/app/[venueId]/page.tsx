"use client";

import { useState } from "react";
import { useKitchenWebSocket } from "@/lib/useKitchenWebSocket";
import OrderCard from "@/components/OrderCard";

export default function KitchenPage({
  params,
  searchParams,
}: {
  params: { venueId: string };
  searchParams: { token?: string; code?: string };
}) {
  const token = searchParams.token ?? "";
  const code = searchParams.code ?? "";
  const [filterStatus, setFilterStatus] = useState<string>("all");

  const { orders, status, updateOrderStatus } = useKitchenWebSocket(
    params.venueId,
    token,
    code,
  );

  const filtered =
    filterStatus === "all"
      ? orders
      : orders.filter((o) => o.status === filterStatus);

  const counts = {
    accepted: orders.filter((o) => o.status === "accepted").length,
    cooking: orders.filter((o) => o.status === "cooking").length,
    ready: orders.filter((o) => o.status === "ready").length,
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <div className="bg-gray-800 border-b border-gray-700 px-6 py-3 flex items-center justify-between">
        <h1 className="text-lg font-bold">Кухонный экран</h1>
        <div className="flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full ${
              status === "connected" ? "bg-green-400" : "bg-red-400"
            }`}
          />
          <span className="text-sm text-gray-400">
            {status === "connected" ? "Подключено" : "Нет связи"}
          </span>
        </div>
      </div>

      {/* Status filter */}
      <div className="flex gap-2 px-6 py-3 bg-gray-800 border-b border-gray-700">
        {[
          { key: "all", label: "Все" },
          { key: "accepted", label: `Ожидают (${counts.accepted})` },
          { key: "cooking", label: `Готовятся (${counts.cooking})` },
          { key: "ready", label: `Готово (${counts.ready})` },
        ].map((f) => (
          <button
            key={f.key}
            onClick={() => setFilterStatus(f.key)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              filterStatus === f.key
                ? "bg-orange-500 text-white"
                : "bg-gray-700 text-gray-300 hover:bg-gray-600"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Orders grid */}
      <div className="p-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.length === 0 && (
          <div className="col-span-full text-center text-gray-500 py-16">
            {orders.length === 0 ? "Нет активных заказов" : "Нет заказов с таким статусом"}
          </div>
        )}
        {filtered.map((order) => (
          <OrderCard
            key={order.order_id}
            order={order}
            onStatusChange={updateOrderStatus}
          />
        ))}
      </div>
    </div>
  );
}
