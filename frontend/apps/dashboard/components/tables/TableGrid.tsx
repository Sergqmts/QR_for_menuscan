"use client";

import { useState } from "react";
import type { Table } from "@/lib/api";
import QRPreview from "./QRPreview";

export default function TableGrid({ venueId, initialTables }: { venueId: string; initialTables: Table[] }) {
  const [tables, setTables] = useState(initialTables);
  const [generating, setGenerating] = useState(false);

  const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  function getToken() {
    return document.cookie.match(/(?:^|;\s*)token=([^;]+)/)?.[1] ?? "";
  }

  async function handleGenerateQR() {
    setGenerating(true);
    try {
      await fetch(`${API}/venues/${venueId}/qr/generate`, {
        method: "POST",
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      await new Promise((r) => setTimeout(r, 3500));
      const res = await fetch(`${API}/venues/${venueId}/tables`, {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      const data = await res.json();
      setTables(data.tables);
    } finally {
      setGenerating(false);
    }
  }

  async function handleDownloadPDF() {
    const res = await fetch(`${API}/venues/${venueId}/qr/download`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    if (res.ok) {
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `qr_${venueId}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } else {
      alert("PDF ещё не сгенерирован. Нажмите «Перегенерировать QR» сначала.");
    }
  }

  return (
    <div>
      <div className="flex gap-3 mb-6">
        <button
          onClick={handleGenerateQR}
          disabled={generating}
          className="bg-orange-500 hover:bg-orange-600 disabled:opacity-60 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          {generating ? "Генерируем..." : "Перегенерировать QR"}
        </button>
        <button
          onClick={handleDownloadPDF}
          className="border border-gray-200 hover:bg-gray-50 text-gray-700 text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          Скачать PDF
        </button>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
        {tables.map((table) => (
          <QRPreview key={table.id} table={table} />
        ))}
      </div>
    </div>
  );
}
