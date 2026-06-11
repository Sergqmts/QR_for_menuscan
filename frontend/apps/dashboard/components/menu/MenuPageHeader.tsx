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
    const token = document.cookie.match(/(?:^|;\s*)token=([^;]+)/)?.[1] ?? "";
    const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    try {
      await fetch(`${API}/venues/${venueId}/reparse-diff`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      const deadline = Date.now() + 60000;
      while (Date.now() < deadline) {
        await new Promise((r) => setTimeout(r, 2000));
        const res = await fetch(`${API}/venues/${venueId}/parse-status`, {
          headers: { Authorization: `Bearer ${token}` },
        });
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
      alert("Парсинг занял слишком долго");
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
