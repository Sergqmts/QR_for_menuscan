"use client";

import { useRouter, useSearchParams } from "next/navigation";

const PERIODS = [{ label: "7д", days: 7 }, { label: "30д", days: 30 }, { label: "90д", days: 90 }];

export default function PeriodFilter() {
  const router = useRouter();
  const sp = useSearchParams();
  const currentFrom = sp.get("from");

  function activeDays() {
    if (!currentFrom) return 30;
    return Math.round((Date.now() - new Date(currentFrom).getTime()) / 86400000);
  }

  function setPeriod(days: number) {
    const to = new Date().toISOString().split("T")[0];
    const from = new Date(Date.now() - days * 86400000).toISOString().split("T")[0];
    const next = new URLSearchParams(sp);
    next.set("from", from);
    next.set("to", to);
    router.push(`?${next}`);
  }

  const active = activeDays();
  return (
    <div className="flex gap-2">
      {PERIODS.map(({ label, days }) => (
        <button
          key={label}
          onClick={() => setPeriod(days)}
          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            active === days ? "bg-orange-500 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
