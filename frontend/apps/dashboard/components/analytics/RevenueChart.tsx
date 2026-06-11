"use client";

import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

export default function RevenueChart({ data }: { data: Array<{ date: string; revenue: string; orders: number }> }) {
  if (data.length === 0) {
    return <div className="h-48 flex items-center justify-center text-gray-400 text-sm">Нет данных за период</div>;
  }
  const chartData = data.map((d) => ({ date: d.date.slice(5), revenue: Number(d.revenue), orders: d.orders }));
  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={chartData}>
        <defs>
          <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#FF6B35" stopOpacity={0.2} />
            <stop offset="95%" stopColor="#FF6B35" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
        <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#9ca3af" }} />
        <YAxis tick={{ fontSize: 11, fill: "#9ca3af" }} />
        <Tooltip formatter={(v: number, n: string) => [n === "revenue" ? `${v.toLocaleString("ru-RU")} ₽` : v, n === "revenue" ? "Выручка" : "Заказов"]} />
        <Area type="monotone" dataKey="revenue" stroke="#FF6B35" fill="url(#g)" strokeWidth={2} />
      </AreaChart>
    </ResponsiveContainer>
  );
}
