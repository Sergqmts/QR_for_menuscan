"use client";

import { useState } from "react";
import type { Dish } from "@/lib/api";
import { updateDishPrice, toggleDishAvailability } from "@/lib/actions";
import ImageUpload from "./ImageUpload";

export default function DishRow({ dish, venueId }: { dish: Dish; venueId: string }) {
  const [price, setPrice] = useState(dish.price);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(dish.price);
  const [available, setAvailable] = useState(dish.is_available);
  const [showUpload, setShowUpload] = useState(false);
  const [imageUrl, setImageUrl] = useState(dish.image_url);

  async function commitPrice() {
    setEditing(false);
    const p = parseFloat(draft);
    if (isNaN(p) || Math.abs(p - parseFloat(price)) < 0.001) return;
    const prev = price;
    setPrice(String(p));
    try {
      await updateDishPrice(venueId, dish.id, p);
    } catch {
      setPrice(prev);
    }
  }

  async function handleToggle() {
    const next = !available;
    setAvailable(next);
    try {
      await toggleDishAvailability(venueId, dish.id, next);
    } catch {
      setAvailable(!next);
    }
  }

  return (
    <>
      <div className="bg-white rounded-xl border border-gray-200 p-4 flex items-center gap-4">
        <button
          onClick={() => setShowUpload(true)}
          className="w-16 h-16 flex-shrink-0 rounded-lg overflow-hidden bg-gray-100 hover:opacity-75 transition-opacity"
          title="Изменить фото"
        >
          {imageUrl ? (
            <img src={imageUrl} alt={dish.name} className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-gray-400 text-xs">Фото</div>
          )}
        </button>

        <div className="flex-1 min-w-0">
          <p className="font-semibold text-gray-900 text-sm">{dish.name}</p>
          {dish.description && <p className="text-gray-500 text-xs mt-0.5 line-clamp-1">{dish.description}</p>}
          {(dish.weight || dish.calories) && (
            <p className="text-gray-400 text-xs mt-0.5">{[dish.weight, dish.calories].filter(Boolean).join(" · ")}</p>
          )}
        </div>

        <div className="flex items-center gap-4 flex-shrink-0">
          {editing ? (
            <input
              autoFocus
              type="number"
              step="0.01"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onBlur={commitPrice}
              onKeyDown={(e) => e.key === "Enter" && commitPrice()}
              className="w-24 border border-orange-400 rounded-lg px-2 py-1 text-sm font-bold text-right outline-none focus:ring-2 focus:ring-orange-400"
            />
          ) : (
            <button
              onClick={() => { setDraft(price); setEditing(true); }}
              className="w-24 text-right text-sm font-bold text-gray-900 hover:text-orange-500 transition-colors"
              title="Нажмите для редактирования"
            >
              {Number(price).toLocaleString("ru-RU")} ₽
            </button>
          )}

          <label className="relative inline-flex items-center cursor-pointer" title={available ? "Доступно" : "Недоступно"}>
            <input type="checkbox" checked={available} onChange={handleToggle} className="sr-only peer" />
            <div className="w-9 h-5 bg-gray-200 rounded-full peer peer-checked:bg-orange-500 after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-4" />
          </label>
        </div>
      </div>

      {showUpload && (
        <ImageUpload
          venueId={venueId}
          dish={dish}
          onClose={() => setShowUpload(false)}
          onSuccess={(url) => setImageUrl(url)}
        />
      )}
    </>
  );
}
