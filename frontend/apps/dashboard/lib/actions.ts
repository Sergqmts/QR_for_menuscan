"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken() {
  return cookies().get("token")?.value ?? "";
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

export async function applyParseDiff(venueId: string, changes: object[]): Promise<void> {
  await fetch(`${API_BASE}/venues/${venueId}/parse/apply-diff`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
    body: JSON.stringify({ changes }),
  });
  revalidatePath(`/venues/${venueId}/menu`);
}
