import { cookies } from "next/headers";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function authHeaders(): Record<string, string> {
  const token = cookies().get("token")?.value;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export interface Venue {
  id: string;
  name: string;
  slug: string;
  address: string | null;
  cuisine_type: string | null;
  table_count: number;
  parse_status: string;
  is_active: boolean;
  created_at: string;
}

export interface Category {
  id: string;
  name: string;
  slug: string;
  sort_order: number;
  is_visible: boolean;
}

export interface Dish {
  id: string;
  venue_id: string;
  category_id: string | null;
  name: string;
  description: string | null;
  price: string;
  weight: string | null;
  calories: string | null;
  image_url: string | null;
  tags: string[];
  allergens: string[];
  is_available: boolean;
  sort_order: number;
}

export interface Table {
  id: string;
  number: number;
  label: string | null;
  qr_code_url: string | null;
  is_active: boolean;
}

export interface Order {
  id: string;
  table_id: string;
  status: string;
  total_amount: string;
  created_at: string;
  session_id: string;
  items: Array<{
    id: string;
    dish_id: string;
    quantity: number;
    unit_price: string;
    guest_name: string | null;
  }>;
}

export interface AnalyticsData {
  summary: { orders: number; revenue: string; avg_check: string; top_dish: string | null };
  daily: Array<{ date: string; revenue: string; orders: number }>;
  top_dishes: Array<{ name: string; count: number; revenue: string }>;
}

export async function fetchVenues(): Promise<{ venues: Venue[] }> {
  const res = await fetch(`${API_BASE}/venues`, { headers: authHeaders(), cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch venues");
  return res.json();
}

export async function fetchVenue(id: string): Promise<Venue> {
  const res = await fetch(`${API_BASE}/venues/${id}`, { headers: authHeaders(), cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch venue");
  return res.json();
}

export async function fetchCategories(venueId: string): Promise<{ categories: Category[] }> {
  const res = await fetch(`${API_BASE}/venues/${venueId}/categories`, { headers: authHeaders(), cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch categories");
  return res.json();
}

export async function fetchDishes(venueId: string): Promise<{ dishes: Dish[] }> {
  const res = await fetch(`${API_BASE}/venues/${venueId}/dishes`, { headers: authHeaders(), cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch dishes");
  return res.json();
}

export async function fetchTables(venueId: string): Promise<{ tables: Table[] }> {
  const res = await fetch(`${API_BASE}/venues/${venueId}/tables`, { headers: authHeaders(), cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch tables");
  return res.json();
}

export async function fetchAnalytics(venueId: string, from?: string, to?: string): Promise<AnalyticsData> {
  const sp = new URLSearchParams();
  if (from) sp.set("from", from);
  if (to) sp.set("to", to);
  const res = await fetch(`${API_BASE}/venues/${venueId}/analytics?${sp}`, { headers: authHeaders(), cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch analytics");
  return res.json();
}
