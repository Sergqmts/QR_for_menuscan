"use client";

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

export default function TopDishesChart({ data }: { data: Array<{ name: string; count: number }> }) {
  if (data.length === 0) {
    return <div className="h-48 flex items-center justify-center text-gray-400 text-sm">Нет данных за период</div>;
  }
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} layout="vertical">
        <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
        <XAxis type="number" tick={{ fontSize: 11, fill: "#9ca3af" }} />
        <YAxis dataKey="name" type="category" tick={{ fontSize: 10, fill: "#6b7280" }} width={100} />
        <Tooltip formatter={(v: number) => [v, "Заказано"]} />
        <Bar dataKey="count" fill="#FF6B35" radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
