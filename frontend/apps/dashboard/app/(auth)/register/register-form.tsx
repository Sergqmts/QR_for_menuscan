"use client";

import { useFormState, useFormStatus } from "react-dom";
import { registerAction } from "@/lib/actions";
import Link from "next/link";

function SubmitButton() {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      className="w-full bg-orange-500 hover:bg-orange-600 disabled:opacity-60 text-white font-semibold py-2.5 rounded-lg transition-colors"
    >
      {pending ? "Регистрируем..." : "Зарегистрироваться"}
    </button>
  );
}

export default function RegisterForm() {
  const [state, formAction] = useFormState(registerAction, { error: null });
  return (
    <form action={formAction} className="space-y-4">
      <div>
        <label htmlFor="full_name" className="block text-sm font-medium text-gray-700 mb-1">Имя</label>
        <input id="full_name" name="full_name" type="text" className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-orange-500" />
      </div>
      <div>
        <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">Email</label>
        <input id="email" name="email" type="email" required className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-orange-500" />
      </div>
      <div>
        <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">Пароль</label>
        <input id="password" name="password" type="password" required minLength={6} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-orange-500" />
      </div>
      {state?.error && <p className="text-red-500 text-sm">{state.error}</p>}
      <SubmitButton />
      <p className="text-center text-sm text-gray-500">
        Уже есть аккаунт?{" "}
        <Link href="/login" className="text-orange-500 hover:underline">Войти</Link>
      </p>
    </form>
  );
}
