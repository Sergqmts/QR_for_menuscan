"use client";

import { useState } from "react";

interface Props {
  onConfirm: (name: string) => void;
}

export default function GuestNameModal({ onConfirm }: Props) {
  const [name, setName] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = name.trim() || "Гость";
    onConfirm(trimmed);
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-end z-50">
      <div className="bg-white w-full max-w-lg mx-auto rounded-t-2xl p-6">
        <h2 className="text-lg font-bold text-gray-900 mb-1">Как вас зовут?</h2>
        <p className="text-sm text-gray-500 mb-4">
          Другие гости за столом будут видеть ваше имя в корзине.
        </p>
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            autoFocus
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Имя (необязательно)"
            className="flex-1 bg-gray-100 rounded-lg px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-orange-500"
          />
          <button
            type="submit"
            className="bg-orange-500 hover:bg-orange-600 text-white font-semibold px-5 py-2.5 rounded-lg"
          >
            Войти
          </button>
        </form>
      </div>
    </div>
  );
}
