import type { Table } from "@/lib/api";

export default function QRPreview({ table }: { table: Table }) {
  const qrSrc = table.qr_code_url
    ? `https://api.qrserver.com/v1/create-qr-code/?size=120x120&data=${encodeURIComponent(table.qr_code_url)}`
    : null;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 flex flex-col items-center gap-3">
      <div className="w-28 h-28 flex items-center justify-center bg-gray-50 rounded-lg">
        {qrSrc ? (
          <img src={qrSrc} alt={`QR стол ${table.number}`} className="w-24 h-24" />
        ) : (
          <span className="text-gray-400 text-xs text-center px-2">QR не сгенерирован</span>
        )}
      </div>
      <div className="text-center">
        <p className="font-semibold text-gray-900 text-sm">{table.label ?? `Стол ${table.number}`}</p>
        <span className={`text-xs ${table.is_active ? "text-green-600" : "text-gray-400"}`}>
          {table.is_active ? "Активен" : "Неактивен"}
        </span>
      </div>
    </div>
  );
}
