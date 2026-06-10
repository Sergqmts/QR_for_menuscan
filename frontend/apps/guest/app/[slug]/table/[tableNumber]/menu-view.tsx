"use client";

import { useState, useMemo, useEffect } from "react";
import type { PublicMenu, TableInfo, Dish } from "@/lib/api";
import { useCartStore } from "@/lib/cartStore";
import { useTableWebSocket } from "@/lib/useTableWebSocket";
import CategoryTabs from "@/components/CategoryTabs";
import DishCard from "@/components/DishCard";
import CartDrawer from "@/components/CartDrawer";
import GuestNameModal from "@/components/GuestNameModal";

interface Props {
  menu: PublicMenu;
  tableInfo: TableInfo;
  venueSlug: string;
}

export default function MenuView({ menu, tableInfo, venueSlug }: Props) {
  const [activeSlug, setActiveSlug] = useState(menu.categories[0]?.slug ?? "");
  const [search, setSearch] = useState("");
  const [cartOpen, setCartOpen] = useState(false);
  const [nameAsked, setNameAsked] = useState(false);

  const {
    guestId,
    guestName,
    setGuestName,
    cart,
    total,
    wsStatus,
    lastOrder,
  } = useCartStore();

  const { send } = useTableWebSocket(tableInfo.id, menu.venue.id);

  useEffect(() => {
    if (!guestName) setNameAsked(false);
    else setNameAsked(true);
  }, [guestName]);

  function handleSetName(name: string) {
    setGuestName(name);
    setNameAsked(true);
  }

  function handleAddDish(dish: Dish) {
    const cart_item_id = crypto.randomUUID();
    send("add_item", {
      cart_item_id,
      dish_id: dish.id,
      dish_name: dish.name,
      unit_price: Number(dish.price),
      quantity: 1,
      comment: "",
      guest_id: guestId,
      guest_name: guestName || "Гость",
    });
  }

  function handleSubmitOrder() {
    send("submit_order", { table_comment: "" });
    setCartOpen(false);
  }

  const filteredCategories = useMemo(() => {
    if (!search.trim()) return menu.categories;
    const q = search.toLowerCase();
    return menu.categories
      .map((cat) => ({
        ...cat,
        dishes: cat.dishes.filter(
          (d) =>
            d.name.toLowerCase().includes(q) ||
            (d.description ?? "").toLowerCase().includes(q)
        ),
      }))
      .filter((cat) => cat.dishes.length > 0);
  }, [menu.categories, search]);

  const activeCategory =
    filteredCategories.find((c) => c.slug === activeSlug) ?? filteredCategories[0];

  const statusLabel: Record<string, string> = {
    accepted: "✅ Принят",
    cooking: "👨‍🍳 Готовится",
    ready: "🎉 Готов!",
    served: "✔️ Подан",
  };

  return (
    <div className="max-w-lg mx-auto min-h-screen flex flex-col">
      {!nameAsked && <GuestNameModal onConfirm={handleSetName} />}

      {/* Header */}
      <div className="bg-white px-4 pt-4 pb-2 shadow-sm">
        <div className="flex items-center justify-between mb-2">
          <div>
            <h1 className="text-lg font-bold text-gray-900">{menu.venue.name}</h1>
            <p className="text-sm text-gray-500">
              {tableInfo.label ?? `Стол ${tableInfo.number}`}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${wsStatus === "connected" ? "bg-green-400" : "bg-gray-300"}`} />
            {cart.length > 0 && (
              <button
                onClick={() => setCartOpen(true)}
                className="bg-orange-500 text-white text-sm font-semibold px-3 py-1.5 rounded-lg"
              >
                🛒 {cart.length} · {total.toLocaleString("ru-RU")} ₽
              </button>
            )}
          </div>
        </div>

        {lastOrder && (
          <div className="bg-orange-50 border border-orange-200 rounded-lg px-3 py-2 mb-2 text-sm">
            Заказ #{lastOrder.order_id.slice(-6)}: {statusLabel[lastOrder.status] ?? lastOrder.status}
          </div>
        )}

        <input
          type="search"
          placeholder="Поиск по меню..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full bg-gray-100 rounded-lg px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-orange-500"
        />
      </div>

      {!search && (
        <CategoryTabs
          categories={menu.categories}
          activeSlug={activeSlug}
          onSelect={setActiveSlug}
        />
      )}

      <div className="flex-1 px-4 py-4 space-y-3 pb-24">
        {(search ? filteredCategories : activeCategory ? [activeCategory] : []).map((cat) => (
          <div key={cat.id}>
            {search && (
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
                {cat.name}
              </h2>
            )}
            {cat.dishes.map((dish) => (
              <div key={dish.id} className="mb-3">
                <DishCard dish={dish} onAdd={handleAddDish} />
              </div>
            ))}
          </div>
        ))}
        {filteredCategories.length === 0 && (
          <p className="text-center text-gray-400 mt-12">Ничего не найдено</p>
        )}
      </div>

      <CartDrawer
        open={cartOpen}
        onClose={() => setCartOpen(false)}
        onSubmitOrder={handleSubmitOrder}
      />
    </div>
  );
}
