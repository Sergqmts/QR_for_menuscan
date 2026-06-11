import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function GET(_req: Request, { params }: { params: { venueId: string } }) {
  const token = cookies().get("token")?.value ?? "";
  const res = await fetch(`${API_BASE}/venues/${params.venueId}/qr/download`, {
    headers: { Authorization: `Bearer ${token}` },
    redirect: "follow",
  });

  if (!res.ok) {
    return NextResponse.json({ error: "Not found" }, { status: res.status });
  }

  const blob = await res.blob();
  return new NextResponse(blob, {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": `attachment; filename="qr_${params.venueId}.pdf"`,
    },
  });
}
