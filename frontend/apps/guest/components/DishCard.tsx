"use client";

import { Dish } from "@/lib/api";

interface Props {
  dish: Dish;
  onAdd: (dish: Dish) => void;
}

export default function DishCard({ dish, onAdd }: Props) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden flex gap-3 p-4">
      {dish.image_url && (
        <img
          src={dish.image_url}
          alt={dish.name}
          className="w-20 h-20 object-cover rounded-lg flex-shrink-0"
        />
      )}
      <div className="flex-1 min-w-0">
        <h3 className="font-semibold text-gray-900 text-sm leading-tight">{dish.name}</h3>
        {dish.description && (
          <p className="text-gray-500 text-xs mt-0.5 line-clamp-2">{dish.description}</p>
        )}
        <div className="flex items-center gap-2 mt-1">
          {dish.weight && (
            <span className="text-xs text-gray-400">{dish.weight}</span>
          )}
          {dish.calories && (
            <span className="text-xs text-gray-400">{dish.calories}</span>
          )}
        </div>
        <div className="flex items-center justify-between mt-2">
          <span className="font-bold text-gray-900">
            {Number(dish.price).toLocaleString("ru-RU")} ₽
          </span>
          {dish.is_available ? (
            <button
              onClick={() => onAdd(dish)}
              className="bg-orange-500 hover:bg-orange-600 text-white text-sm font-semibold px-4 py-1.5 rounded-lg transition-colors"
            >
              + В корзину
            </button>
          ) : (
            <span className="text-xs text-gray-400">Недоступно</span>
          )}
        </div>
      </div>
    </div>
  );
}
