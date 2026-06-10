"use client";

import { KitchenOrder } from "@/lib/useKitchenWebSocket";

interface Props {
  order: KitchenOrder;
  onStatusChange: (orderId: string, status: KitchenOrder["status"]) => void;
}

const STATUS_LABEL: Record<string, string> = {
  accepted: "Принят",
  cooking: "Готовится",
  ready: "Готово!",
  served: "Подан",
};

const STATUS_COLOR: Record<string, string> = {
  accepted: "border-yellow-400 bg-yellow-950",
  cooking: "border-blue-400 bg-blue-950",
  ready: "border-green-400 bg-green-950",
  served: "border-gray-500 bg-gray-800",
};

const NEXT_STATUS: Record<string, KitchenOrder["status"]> = {
  accepted: "cooking",
  cooking: "ready",
  ready: "served",
};

const NEXT_LABEL: Record<string, string> = {
  accepted: "Начать готовку",
  cooking: "Готово",
  ready: "Подано",
};

export default function OrderCard({ order, onStatusChange }: Props) {
  const elapsed = Math.round((Date.now() - new Date(order.created_at).getTime()) / 60000);
  const nextStatus = NEXT_STATUS[order.status];

  return (
    <div className={`rounded-xl border-2 p-4 ${STATUS_COLOR[order.status] ?? "border-gray-600 bg-gray-800"}`}>
      <div className="flex items-center justify-between mb-3">
        <div>
          <span className="text-lg font-bold">Стол {order.table.number}</span>
          {order.table.label && (
            <span className="text-sm text-gray-400 ml-2">{order.table.label}</span>
          )}
        </div>
        <div className="text-right">
          <p className="text-sm font-semibold text-gray-300">{STATUS_LABEL[order.status]}</p>
          <p className="text-xs text-gray-500">{elapsed} мин назад</p>
        </div>
      </div>

      <div className="space-y-1.5 mb-4">
        {order.items.map((item, i) => (
          <div key={i} className="flex items-start gap-2">
            <span className="font-bold text-orange-400 text-sm w-6 flex-shrink-0">{item.quantity}×</span>
            <div>
              <p className="text-sm font-medium">{item.dish_name || "Блюдо"}</p>
              {item.comment && <p className="text-xs text-gray-400 italic">{item.comment}</p>}
              {item.guest_name && <p className="text-xs text-gray-500">{item.guest_name}</p>}
            </div>
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-gray-300">
          {Number(order.total_amount).toLocaleString("ru-RU")} ₽
        </span>
        {nextStatus && (
          <button
            onClick={() => onStatusChange(order.order_id, nextStatus)}
            className="bg-orange-500 hover:bg-orange-600 text-white text-sm font-bold px-4 py-2 rounded-lg transition-colors"
          >
            {NEXT_LABEL[order.status]}
          </button>
        )}
      </div>
    </div>
  );
}
