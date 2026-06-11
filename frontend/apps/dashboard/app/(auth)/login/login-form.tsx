"use client";

import { useFormState, useFormStatus } from "react-dom";
import { loginAction } from "@/lib/actions";

function SubmitButton() {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      className="w-full bg-orange-500 hover:bg-orange-600 disabled:opacity-60 text-white font-semibold py-2.5 rounded-lg transition-colors"
    >
      {pending ? "Входим..." : "Войти"}
    </button>
  );
}

export default function LoginForm() {
  const [state, formAction] = useFormState(loginAction, { error: null });
  return (
    <form action={formAction} className="space-y-4">
      <div>
        <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">Email</label>
        <input id="email" name="email" type="email" required className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-orange-500" />
      </div>
      <div>
        <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">Пароль</label>
        <input id="password" name="password" type="password" required className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-orange-500" />
      </div>
      {state?.error && <p className="text-red-500 text-sm">{state.error}</p>}
      <SubmitButton />
    </form>
  );
}
