import { createClient } from "@/lib/supabase/client";

const DEFAULT_API_URL = "http://localhost:8000";

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
