import { createClient } from "@/lib/supabase/client";

const DEFAULT_API_URL = "http://localhost:8000";
const REFRESH_TOKEN_NOT_FOUND = "refresh_token_not_found";

export class AuthenticationRequiredError extends Error {
  constructor() {
    super("An authenticated Supabase session is required");
    this.name = "AuthenticationRequiredError";
  }
}

function apiUrl(path: string): string {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_URL;
  const normalizedBaseUrl = `${baseUrl.replace(/\/+$/, "")}/`;

  return new URL(path.replace(/^\/+/, ""), normalizedBaseUrl).toString();
}

function isStaleRefreshTokenError(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "code" in error &&
    error.code === REFRESH_TOKEN_NOT_FOUND
  );
}

export async function authenticatedApiFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const supabase = createClient();
  const {
    data: { session },
    error,
  } = await supabase.auth.getSession();

  if (error) {
    if (isStaleRefreshTokenError(error)) {
      // Supabase normally removes an expired session after a rejected refresh.
      // Local sign-out also clears any remaining browser cookie chunks.
      await supabase.auth.signOut({ scope: "local" });
      throw new AuthenticationRequiredError();
    }

    throw new Error(`Unable to read Supabase session: ${error.message}`);
  }

  if (!session) {
    throw new AuthenticationRequiredError();
  }

  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${session.access_token}`);

  return fetch(apiUrl(path), {
    ...init,
    cache: init.cache ?? "no-store",
    headers,
  });
}
