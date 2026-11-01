import { isApiError } from "../api/client";

/** The single place an unknown thrown value becomes user-facing text. */
export function errorMessage(error: unknown): string {
  if (isApiError(error)) {
    return error.isNetworkError
      ? "The server could not be reached. Check your connection and try again."
      : error.message;
  }
  if (error instanceof Error && error.message) return error.message;
  return "An unexpected error occurred.";
}
