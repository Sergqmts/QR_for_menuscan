"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { logoutAction } from "@/lib/actions";

export default function Sidebar({ userEmail }: { userEmail: string }) {
  const pathname = usePathname();
  return (
    <aside className="w-60 bg-white border-r border-gray-200 flex flex-col flex-shrink-0">
      <div className="p-6 border-b border-gray-100">
        <h1 className="text-xl font-bold text-orange-500">MenuScan</h1>
      </div>
      <nav className="flex-1 p-3 space-y-1">
        <Link
          href="/venues"
          className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
            pathname.startsWith("/venues") ? "bg-orange-50 text-orange-600" : "text-gray-600 hover:bg-gray-50"
          }`}
        >
          Заведения
        </Link>
      </nav>
      <div className="p-4 border-t border-gray-100">
        <p className="text-xs text-gray-400 truncate mb-2">{userEmail}</p>
        <form action={logoutAction}>
          <button type="submit" className="text-sm text-gray-500 hover:text-gray-900 transition-colors">
            Выйти
          </button>
        </form>
      </div>
    </aside>
  );
}
