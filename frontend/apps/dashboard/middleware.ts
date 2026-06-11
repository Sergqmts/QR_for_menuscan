import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const token = request.cookies.get("token")?.value;
  const path = request.nextUrl.pathname;
  const isLoginPage = path === "/login";

  if (!token && !isLoginPage) {
    const url = new URL("/login", request.url);
    url.searchParams.set("redirect", path);
    return NextResponse.redirect(url);
  }

  if (token && isLoginPage) {
    return NextResponse.redirect(new URL("/venues", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
