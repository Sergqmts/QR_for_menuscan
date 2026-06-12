"use client";

import { useState } from "react";
import Link from "next/link";
import type { Venue } from "@/lib/api";
import DiffReview, { type DiffChange } from "./DiffReview";
import { applyParseDiff } from "@/lib/actions";

interface Props {
  venue: Venue;
  venueId: string;
}

export default function MenuPageHeader({ venue, venueId }: Props) {
  const [parsing, setParsing] = useState(false);
  const [diffChanges, setDiffChanges] = useState<DiffChange[] | null>(null);

  async function handleParse() {
    setParsing(true);
    try {
      const startRes = await fetch(`/api/venues/${venueId}/parse`, { method: "POST" });
      if (!startRes.ok) {
        alert("Не удалось запустить парсинг");
        return;
      }

      // Poll for up to 3 minutes — Playwright on JS-heavy sites can take 1-2 min
      const deadline = Date.now() + 180_000;
      while (Date.now() < deadline) {
        await new Promise((r) => setTimeout(r, 3000));
        const res = await fetch(`/api/venues/${venueId}/parse`);
        const data = await res.json();
        if (data.status === "done") {
          setDiffChanges(data.diff_data ?? []);
          return;
        }
        if (data.status === "failed") {
          alert("Парсинг завершился с ошибкой: " + (data.error_message ?? ""));
          return;
        }
      }
      alert("Парсинг занял слишком долго (>3 мин)");
    } catch {
      alert("Ошибка при запуске парсинга");
    } finally {
      setParsing(false);
    }
  }

  async function handleApplyDiff(selected: DiffChange[]) {
    await applyParseDiff(venueId, selected);
  }

  return (
    <>
      <div className="flex items-center justify-between">
        <div>
          <nav className="text-sm text-gray-500 mb-1">
            <Link href="/venues" className="hover:text-orange-500">Заведения</Link>
            <span className="mx-2">/</span>
            <span className="text-gray-900">{venue.name}</span>
          </nav>
          <h1 className="text-2xl font-bold text-gray-900">Меню</h1>
        </div>
        {venue.parse_status !== "pending" && (
          <button
            onClick={handleParse}
            disabled={parsing}
            className="bg-gray-100 hover:bg-gray-200 disabled:opacity-60 text-gray-700 text-sm font-medium px-4 py-2 rounded-lg transition-colors"
          >
            {parsing ? "Парсим..." : "Обновить из источника"}
          </button>
        )}
      </div>
      {diffChanges !== null && (
        <DiffReview
          changes={diffChanges}
          onClose={() => setDiffChanges(null)}
          onApply={handleApplyDiff}
        />
      )}
    </>
  );
}
