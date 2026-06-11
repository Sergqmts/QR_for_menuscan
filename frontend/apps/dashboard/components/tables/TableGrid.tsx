"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import type { Table } from "@/lib/api";
import QRPreview from "./QRPreview";
import { generateQRAction } from "@/lib/actions";

export default function TableGrid({ venueId, initialTables }: { venueId: string; initialTables: Table[] }) {
  const tables = initialTables;
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const router = useRouter();

  const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  async function handleGenerateQR() {
    setGenerating(true);
    setError(null);
    try {
      const result = await generateQRAction(venueId);
      if (result.error) {
        setError(result.error);
        return;
      }
      await new Promise((r) => setTimeout(r, 3500));
      startTransition(() => router.refresh());
    } finally {
      setGenerating(false);
    }
  }

  async function handleDownloadPDF() {
    startTransition(async () => {
      const res = await fetch(`/api/venues/${venueId}/qr/download`);
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
        setError("PDF ещё не сгенерирован. Нажмите «Перегенерировать QR» сначала.");
      }
    });
  }

  return (
    <div>
      <div className="flex gap-3 mb-6 items-center">
        <button
          onClick={handleGenerateQR}
          disabled={generating || isPending}
          className="bg-orange-500 hover:bg-orange-600 disabled:opacity-60 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          {generating ? "Генерируем..." : "Перегенерировать QR"}
        </button>
        <button
          onClick={handleDownloadPDF}
          disabled={isPending}
          className="border border-gray-200 hover:bg-gray-50 disabled:opacity-60 text-gray-700 text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          Скачать PDF
        </button>
        {error && <p className="text-red-500 text-sm">{error}</p>}
      </div>
      {tables.length === 0 ? (
        <p className="text-gray-400 text-sm">Столов нет. Добавьте столы при создании или редактировании заведения.</p>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
          {tables.map((table) => (
            <QRPreview key={table.id} table={table} />
          ))}
        </div>
      )}
    </div>
  );
}
