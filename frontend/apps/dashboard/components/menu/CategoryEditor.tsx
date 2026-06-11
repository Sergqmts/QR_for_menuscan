"use client";

import { useState } from "react";
import {
  DndContext,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
  arrayMove,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type { Category } from "@/lib/api";
import { reorderCategories } from "@/lib/actions";

function SortableItem({
  category,
  isActive,
  onSelect,
}: {
  category: Category;
  isActive: boolean;
  onSelect: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id: category.id });
  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-colors ${
        isActive ? "bg-orange-50 text-orange-600" : "hover:bg-gray-50 text-gray-700"
      }`}
    >
      <span {...attributes} {...listeners} className="text-gray-300 cursor-grab active:cursor-grabbing select-none text-xs">
        ⠿
      </span>
      <button onClick={onSelect} className="flex-1 text-left text-sm font-medium truncate">
        {category.name}
      </button>
    </div>
  );
}

interface Props {
  venueId: string;
  categories: Category[];
  activeCategoryId: string | null;
  onSelectCategory: (id: string) => void;
}

export default function CategoryEditor({ venueId, categories, activeCategoryId, onSelectCategory }: Props) {
  const [items, setItems] = useState(categories);
  const sensors = useSensors(useSensor(PointerSensor));

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = items.findIndex((c) => c.id === active.id);
    const newIndex = items.findIndex((c) => c.id === over.id);
    const reordered = arrayMove(items, oldIndex, newIndex);
    setItems(reordered);
    await reorderCategories(venueId, reordered.map((c) => c.id));
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-2">
      <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider px-3 py-2">Категории</p>
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={items.map((c) => c.id)} strategy={verticalListSortingStrategy}>
          {items.map((cat) => (
            <SortableItem
              key={cat.id}
              category={cat}
              isActive={cat.id === activeCategoryId}
              onSelect={() => onSelectCategory(cat.id)}
            />
          ))}
        </SortableContext>
      </DndContext>
    </div>
  );
}
