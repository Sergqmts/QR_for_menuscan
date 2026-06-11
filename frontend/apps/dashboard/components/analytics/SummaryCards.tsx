interface Summary {
  orders: number;
  revenue: string;
  avg_check: string;
  top_dish: string | null;
}

export default function SummaryCards({ summary }: { summary: Summary }) {
  const cards = [
    { label: "Заказов", value: summary.orders.toLocaleString("ru-RU") },
    { label: "Выручка", value: `${Number(summary.revenue).toLocaleString("ru-RU")} ₽` },
    { label: "Средний чек", value: `${Number(summary.avg_check).toLocaleString("ru-RU", { maximumFractionDigits: 0 })} ₽` },
    { label: "Топ блюдо", value: summary.top_dish ?? "—" },
  ];
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((c) => (
        <div key={c.label} className="bg-white rounded-xl border border-gray-200 p-5">
          <p className="text-sm text-gray-500">{c.label}</p>
          <p className="text-2xl font-bold text-gray-900 mt-1 truncate">{c.value}</p>
        </div>
      ))}
    </div>
  );
}
