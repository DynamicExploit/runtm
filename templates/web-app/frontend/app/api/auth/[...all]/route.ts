/**
 * Better Auth API route handler.
 *
 * This catch-all route handles all Better Auth API endpoints:
 * - POST /api/auth/sign-in/email
 * - POST /api/auth/sign-up/email
 * - POST /api/auth/sign-out
 * - GET /api/auth/session
 * - And more...
 *
 * This file is ONLY used when features.auth is enabled.
 */

import { handler } from "@/lib/auth";
import { toNextJsHandler } from "better-auth/next-js";

export const { GET, POST } = toNextJsHandler(handler);

