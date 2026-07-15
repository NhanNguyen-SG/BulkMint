import { AuthenticationRequiredError } from "./authenticated-fetch";

export async function apiError(
  response: Response,
  fallback: string,
): Promise<Error> {
  try {
    const body: unknown = await response.json();
    if (
      typeof body === "object" &&
      body !== null &&
      "detail" in body &&
      typeof body.detail === "string"
    ) {
      return new Error(body.detail);
    }
  } catch {
    // Use the status-based fallback when the response is not JSON.
  }

  return new Error(`${fallback} (HTTP ${response.status})`);
}

export function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof AuthenticationRequiredError) {
    return "Log in before continuing.";
  }
  return error instanceof Error ? error.message : fallback;
}

export function reportUnexpectedError(message: string, error: unknown) {
  if (!(error instanceof AuthenticationRequiredError)) {
    console.error(message, error);
  }
}
