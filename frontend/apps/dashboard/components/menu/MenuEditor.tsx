"use client";

import { useState } from "react";
import type { Category, Dish } from "@/lib/api";
import CategoryEditor from "./CategoryEditor";
import DishRow from "./DishRow";

interface Props {
  venueId: string;
  initialCategories: Category[];
  initialDishes: Dish[];
}

export default function MenuEditor({ venueId, initialCategories, initialDishes }: Props) {
  const [activeCategoryId, setActiveCategoryId] = useState<string | null>(
    initialCategories[0]?.id ?? null
  );

  const activeDishes = initialDishes.filter((d) => d.category_id === activeCategoryId);

  return (
    <div className="flex gap-6 h-full overflow-hidden">
      <div className="w-64 flex-shrink-0 overflow-y-auto">
        <CategoryEditor
          venueId={venueId}
          categories={initialCategories}
          activeCategoryId={activeCategoryId}
          onSelectCategory={setActiveCategoryId}
        />
      </div>
      <div className="flex-1 overflow-y-auto">
        {activeCategoryId ? (
          activeDishes.length === 0 ? (
            <p className="text-gray-400 text-sm py-12 text-center">Нет блюд в этой категории</p>
          ) : (
            <div className="space-y-2 pb-8">
              {activeDishes.map((dish) => (
                <DishRow key={dish.id} dish={dish} venueId={venueId} />
              ))}
            </div>
          )
        ) : (
          <p className="text-gray-400 text-sm py-12 text-center">Выберите категорию</p>
        )}
      </div>
    </div>
  );
}
