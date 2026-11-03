import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests (ARCHITECTURE §15.4) against the real stack: a production build of this app,
 * FastAPI and Postgres. The backend runs with AI_MODE=demo and no AI keys, so only the bundled
 * synthetic sample bill is read (deterministically, labelled as demo); nothing calls a live AI.
 *
 * The database must already be migrated and seeded (see docs/deployment.md, "End-to-end tests").
 * Ports 3100/8100 keep the suite clear of the dev servers on 3000/8000.
 */
const WEB = process.env.E2E_BASE_URL ?? "http://localhost:3100";
const API = process.env.E2E_API_URL ?? "http://localhost:8100";
const DATABASE_URL = process.env.E2E_DATABASE_URL ?? "postgresql+psycopg://helio:helio@localhost:5433/helio_e2e";

export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 15_000 },
  fullyParallel: false, // one shared database: the journey's steps depend on each other
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: WEB,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "uv run uvicorn app.main:app --port 8100",
      cwd: "../backend",
      url: `${API}/api/health`,
      // Never reuse: a leftover server on this port would test an old build.
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        DATABASE_URL,
        AI_MODE: "demo",
        // Explicitly empty: values here win over backend/.env, so a local run never calls live AI.
        GROQ_API_KEY: "",
        GEMINI_API_KEY: "",
        DEMO_LOGINS: "false",
        JWT_SECRET: process.env.JWT_SECRET ?? "e2e-only-not-a-secret-padded-to-32-bytes",
        COOKIE_SECURE: "false",
        FRONTEND_ORIGIN: WEB,
      },
    },
    {
      command: "npm run build && npm run start -- --port 3100",
      url: WEB,
      // Never reuse: a leftover server on this port would test an old build.
      reuseExistingServer: false,
      timeout: 300_000,
      env: { BACKEND_URL: API },
    },
  ],
});
