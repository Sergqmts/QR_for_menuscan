"use client";

import { useCartStore } from "@/lib/cartStore";

interface Props {
  open: boolean;
  onClose: () => void;
  onSubmitOrder: () => void;
}

export default function CartDrawer({ open, onClose, onSubmitOrder }: Props) {
  const { cart, total, guestId } = useCartStore();

  if (!open) return null;

  const myItems = cart.filter((i) => i.guest_id === guestId);
  const othersItems = cart.filter((i) => i.guest_id !== guestId);

  return (
    <div className="fixed inset-0 z-40 flex items-end">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white w-full max-w-lg mx-auto rounded-t-2xl p-5 max-h-[80vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold">Корзина стола</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">&times;</button>
        </div>

        {cart.length === 0 && (
          <p className="text-gray-400 text-center py-6">Корзина пуста</p>
        )}

        {myItems.length > 0 && (
          <div className="mb-4">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Ваш заказ</p>
            {myItems.map((item) => (
              <div key={item.cart_item_id} className="flex justify-between items-center py-2 border-b border-gray-100 last:border-0">
                <div>
                  <p className="text-sm font-medium">{item.dish_name}</p>
                  {item.comment && <p className="text-xs text-gray-400">{item.comment}</p>}
                </div>
                <div className="text-right">
                  <p className="text-sm font-semibold">{(item.unit_price * item.quantity).toLocaleString("ru-RU")} ₽</p>
                  <p className="text-xs text-gray-400">{item.quantity} шт × {Number(item.unit_price).toLocaleString("ru-RU")} ₽</p>
                </div>
              </div>
            ))}
          </div>
        )}

        {othersItems.length > 0 && (
          <div className="mb-4">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Другие гости</p>
            {othersItems.map((item) => (
              <div key={item.cart_item_id} className="flex justify-between items-center py-2 border-b border-gray-100 last:border-0">
                <div>
                  <p className="text-sm font-medium">{item.dish_name}</p>
                  <p className="text-xs text-gray-400">{item.guest_name}</p>
                </div>
                <p className="text-sm font-semibold">{(item.unit_price * item.quantity).toLocaleString("ru-RU")} ₽</p>
              </div>
            ))}
          </div>
        )}

        {cart.length > 0 && (
          <div className="sticky bottom-0 bg-white pt-3 border-t border-gray-100">
            <div className="flex justify-between items-center mb-3">
              <span className="font-semibold text-gray-700">Итого</span>
              <span className="font-bold text-lg">{total.toLocaleString("ru-RU")} ₽</span>
            </div>
            <button
              onClick={onSubmitOrder}
              className="w-full bg-orange-500 hover:bg-orange-600 text-white font-bold py-3 rounded-xl transition-colors"
            >
              Оформить заказ
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
