const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Dish {
  id: string;
  name: string;
  description: string | null;
  price: number;
  weight: string | null;
  calories: string | null;
  image_url: string | null;
  tags: string[];
  allergens: string[];
  is_available: boolean;
}

export interface Category {
  id: string;
  name: string;
  slug: string;
  sort_order: number;
  dishes: Dish[];
}

export interface PublicMenu {
  venue: {
    id: string;
    name: string;
    logo_url: string | null;
    settings: Record<string, unknown>;
  };
  categories: Category[];
}

export interface TableInfo {
  id: string;
  number: number;
  label: string | null;
}

export async function fetchMenu(slug: string): Promise<PublicMenu> {
  const res = await fetch(`${API_BASE}/menu/${slug}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Menu not found");
  return res.json();
}

export async function fetchTableInfo(
  slug: string,
  tableNumber: number
): Promise<TableInfo> {
  const res = await fetch(`${API_BASE}/menu/${slug}/table/${tableNumber}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Table not found");
  return res.json();
}
