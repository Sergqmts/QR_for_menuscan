"use client";

import { useState } from "react";

export interface DiffChange {
  dish_id: string | null;
  action: "add" | "update" | "remove";
  name: string;
  old_price?: number;
  new_price?: number;
  old_weight?: string;
  new_weight?: string;
  description?: string;
}

interface Props {
  changes: DiffChange[];
  onClose: () => void;
  onApply: (selected: DiffChange[]) => Promise<void>;
}

export default function DiffReview({ changes, onClose, onApply }: Props) {
  const [selected, setSelected] = useState(() => new Set(changes.map((_, i) => i)));
  const [applying, setApplying] = useState(false);

  function toggle(i: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(i) ? next.delete(i) : next.add(i);
      return next;
    });
  }

  async function handleApply() {
    setApplying(true);
    try {
      await onApply(changes.filter((_, i) => selected.has(i)));
      onClose();
    } finally {
      setApplying(false);
    }
  }

  if (changes.length === 0) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
        <div className="bg-white rounded-2xl p-6 w-full max-w-md text-center">
          <p className="text-gray-500 text-sm">Изменений не обнаружено</p>
          <button onClick={onClose} className="mt-4 px-4 py-2 bg-gray-100 rounded-lg text-sm font-medium hover:bg-gray-200">
            Закрыть
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white rounded-2xl p-6 w-full max-w-lg flex flex-col max-h-[80vh]">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-bold text-gray-900">Изменения из источника</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">×</button>
        </div>
        <div className="flex-1 overflow-y-auto space-y-1">
          {changes.map((change, i) => (
            <label key={i} className="flex items-start gap-3 p-3 rounded-lg hover:bg-gray-50 cursor-pointer">
              <input type="checkbox" checked={selected.has(i)} onChange={() => toggle(i)} className="mt-0.5 accent-orange-500" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900">{change.name}</p>
                <div className="text-xs text-gray-500 mt-0.5">
                  {change.action === "add" && <span className="text-green-600">+ Новое · {change.new_price} ₽</span>}
                  {change.action === "remove" && <span className="text-red-500">− Удалено из источника</span>}
                  {change.action === "update" && (
                    <>
                      {change.old_price !== change.new_price && <span>Цена: {change.old_price} → {change.new_price} ₽ </span>}
                      {change.old_weight !== change.new_weight && <span>Вес: {change.old_weight} → {change.new_weight}</span>}
                    </>
                  )}
                </div>
              </div>
            </label>
          ))}
        </div>
        <div className="flex gap-3 mt-4 pt-4 border-t border-gray-100">
          <button onClick={onClose} className="flex-1 border border-gray-200 text-gray-700 py-2 rounded-lg text-sm font-medium hover:bg-gray-50">
            Отмена
          </button>
          <button onClick={handleApply} disabled={applying || selected.size === 0} className="flex-1 bg-orange-500 text-white py-2 rounded-lg text-sm font-medium hover:bg-orange-600 disabled:opacity-60">
            {applying ? "Применяем..." : `Принять (${selected.size})`}
          </button>
        </div>
      </div>
    </div>
  );
}
