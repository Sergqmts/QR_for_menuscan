import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function GET(req: Request, { params }: { params: { venueId: string } }) {
  const token = cookies().get("token")?.value ?? "";
  const { searchParams } = new URL(req.url);
  const qs = searchParams.toString();

  const res = await fetch(
    `${API_BASE}/venues/${params.venueId}/orders${qs ? `?${qs}` : ""}`,
    { headers: { Authorization: `Bearer ${token}` } }
  );

  if (!res.ok) {
    return NextResponse.json({ error: "Failed to fetch orders" }, { status: res.status });
  }

  const contentType = res.headers.get("content-type") ?? "";
  if (contentType.includes("text/csv")) {
    const blob = await res.blob();
    return new NextResponse(blob, {
      headers: {
        "Content-Type": "text/csv",
        "Content-Disposition": res.headers.get("content-disposition") ?? `attachment; filename="orders.csv"`,
      },
    });
  }

  const data = await res.json();
  return NextResponse.json(data);
}
