import { setupServer } from "msw/node";

/**
 * No default handlers: every test declares the responses it depends on, so a
 * test can never pass because some other test's stub happened to match.
 */
export const server = setupServer();
