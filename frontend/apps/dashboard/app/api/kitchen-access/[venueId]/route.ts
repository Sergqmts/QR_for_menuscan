import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const KITCHEN_BASE = process.env.NEXT_PUBLIC_KITCHEN_URL ?? "http://localhost:3001";

export async function GET(_req: Request, { params }: { params: { venueId: string } }) {
  const token = cookies().get("token")?.value ?? "";

  if (!token) {
    return NextResponse.redirect(new URL("/login", _req.url));
  }

  // Exchange the long-lived JWT for a 60-second single-use handoff code.
  // The code is stored in Redis server-side; the JWT never appears in any URL.
  const res = await fetch(`${API_BASE}/auth/kitchen-handoff`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) {
    return NextResponse.json({ error: "Failed to generate kitchen access code" }, { status: 502 });
  }

  const { code } = await res.json();
  return NextResponse.redirect(`${KITCHEN_BASE}/${params.venueId}?code=${code}`);
}
