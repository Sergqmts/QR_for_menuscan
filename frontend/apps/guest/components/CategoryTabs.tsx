"use client";

import { Category } from "@/lib/api";

interface Props {
  categories: Category[];
  activeSlug: string;
  onSelect: (slug: string) => void;
}

export default function CategoryTabs({ categories, activeSlug, onSelect }: Props) {
  return (
    <div className="sticky top-0 z-10 bg-white border-b border-gray-200 overflow-x-auto">
      <div className="flex gap-1 px-4 py-2 min-w-max">
        {categories.map((cat) => (
          <button
            key={cat.id}
            onClick={() => onSelect(cat.slug)}
            className={`px-4 py-1.5 rounded-full text-sm font-medium whitespace-nowrap transition-colors ${
              activeSlug === cat.slug
                ? "bg-orange-500 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {cat.name}
          </button>
        ))}
      </div>
    </div>
  );
}
