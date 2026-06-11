"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken() {
  return cookies().get("token")?.value ?? "";
}

export async function registerAction(
  _prevState: { error: string | null },
  formData: FormData
): Promise<{ error: string | null }> {
  const email = formData.get("email") as string;
  const password = formData.get("password") as string;
  const full_name = formData.get("full_name") as string;

  const res = await fetch(`${API_BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, full_name: full_name || undefined }),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = body?.detail;
    if (typeof detail === "string" && detail.includes("already")) {
      return { error: "Пользователь с таким email уже существует" };
    }
    return { error: "Ошибка при регистрации" };
  }

  const { access_token } = await res.json();
  cookies().set("token", access_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24,
  });
  redirect("/venues");
}

export async function loginAction(
  _prevState: { error: string | null },
  formData: FormData
): Promise<{ error: string | null }> {
  const email = formData.get("email") as string;
  const password = formData.get("password") as string;

  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!res.ok) return { error: "Неверный email или пароль" };

  const { access_token } = await res.json();
  cookies().set("token", access_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24,
  });
  redirect("/venues");
}

export async function logoutAction() {
  cookies().delete("token");
  redirect("/login");
}

export async function createVenueAction(
  formData: FormData
): Promise<{ error: string } | void> {
  const name = formData.get("name") as string;
  const address = (formData.get("address") as string) || undefined;
  const cuisine_type = (formData.get("cuisine_type") as string) || undefined;
  const website_url = (formData.get("website_url") as string) || undefined;
  const table_count = parseInt((formData.get("table_count") as string) || "0", 10);

  const res = await fetch(`${API_BASE}/venues`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
    body: JSON.stringify({ name, address, cuisine_type, website_url, table_count }),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    return { error: body?.detail ?? "Ошибка при создании заведения" };
  }

  revalidatePath("/venues");
}

export async function updateDishPrice(venueId: string, dishId: string, price: number): Promise<void> {
  await fetch(`${API_BASE}/venues/${venueId}/dishes/${dishId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
    body: JSON.stringify({ price }),
  });
  revalidatePath(`/venues/${venueId}/menu`);
}

export async function toggleDishAvailability(venueId: string, dishId: string, available: boolean): Promise<void> {
  await fetch(`${API_BASE}/venues/${venueId}/dishes/${dishId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
    body: JSON.stringify({ is_available: available }),
  });
  revalidatePath(`/venues/${venueId}/menu`);
}

export async function getUploadUrl(venueId: string, dishId: string): Promise<{ upload_url: string; image_url: string }> {
  const res = await fetch(`${API_BASE}/venues/${venueId}/dishes/${dishId}/upload-url`, {
    method: "POST",
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  return res.json();
}

export async function confirmDishImage(venueId: string, dishId: string, imageUrl: string): Promise<void> {
  await fetch(`${API_BASE}/venues/${venueId}/dishes/${dishId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
    body: JSON.stringify({ image_url: imageUrl }),
  });
  revalidatePath(`/venues/${venueId}/menu`);
}

export async function reorderCategories(venueId: string, categoryIds: string[]): Promise<void> {
  await fetch(`${API_BASE}/venues/${venueId}/categories/reorder`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
    body: JSON.stringify({ category_ids: categoryIds }),
  });
  revalidatePath(`/venues/${venueId}/menu`);
}

export async function updateVenueAction(
  venueId: string,
  formData: FormData
): Promise<{ error: string } | void> {
  const name = (formData.get("name") as string) || undefined;
  const address = (formData.get("address") as string) || undefined;
  const cuisine_type = (formData.get("cuisine_type") as string) || undefined;
  const website_url = (formData.get("website_url") as string) || undefined;

  const res = await fetch(`${API_BASE}/venues/${venueId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
    body: JSON.stringify({ name, address, cuisine_type, website_url }),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    return { error: body?.detail ?? "Ошибка при сохранении" };
  }

  revalidatePath("/venues");
}

export async function generateQRAction(venueId: string): Promise<{ error?: string }> {
  const res = await fetch(`${API_BASE}/venues/${venueId}/qr/generate`, {
    method: "POST",
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!res.ok) return { error: "Ошибка при генерации QR" };
  return {};
}

export async function applyParseDiff(venueId: string, changes: object[]): Promise<void> {
  await fetch(`${API_BASE}/venues/${venueId}/parse/apply-diff`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
    body: JSON.stringify({ changes }),
  });
  revalidatePath(`/venues/${venueId}/menu`);
}
