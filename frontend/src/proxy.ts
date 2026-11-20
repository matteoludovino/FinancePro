import { NextResponse, type NextRequest } from "next/server";

// An optimistic check only: whether a session cookie exists, not whether it is valid (the API decides
// that, and the app sends people back here on a 401). It saves a flash of the app for signed-out visitors.
const SESSION_COOKIES = ["__Host-fp_session", "fp_session"];
const AUTH_PAGES = ["/entrar", "/criar-conta"];

export function proxy(request: NextRequest) {
  const signedIn = SESSION_COOKIES.some((name) => request.cookies.has(name));
  const { pathname, search } = request.nextUrl;
  if (AUTH_PAGES.includes(pathname)) {
    return signedIn ? NextResponse.redirect(new URL("/painel", request.url)) : NextResponse.next();
  }
  if (!signedIn) {
    const login = new URL("/entrar", request.url);
    login.searchParams.set("next", pathname + search);
    return NextResponse.redirect(login);
  }
  return NextResponse.next();
}

export const config = {
  // The app's pages; the landing page, /api and static files never pass through here.
  matcher: [
    "/painel/:path*",
    "/contas/:path*",
    "/categorias/:path*",
    "/regras/:path*",
    "/configuracoes/:path*",
    "/entrar",
    "/criar-conta",
  ],
};
