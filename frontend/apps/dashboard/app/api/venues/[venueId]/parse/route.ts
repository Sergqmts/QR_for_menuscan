import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// GET  → proxy /venues/{id}/parse-status
// POST → proxy /venues/{id}/reparse-diff
export async function GET(_req: Request, { params }: { params: { venueId: string } }) {
  const token = cookies().get("token")?.value ?? "";
  const res = await fetch(`${API_BASE}/venues/${params.venueId}/parse-status`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

export async function POST(_req: Request, { params }: { params: { venueId: string } }) {
  const token = cookies().get("token")?.value ?? "";
  const res = await fetch(`${API_BASE}/venues/${params.venueId}/reparse-diff`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
