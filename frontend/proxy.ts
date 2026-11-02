import createMiddleware from "next-intl/middleware";

import { routing } from "./i18n/routing";

export default createMiddleware(routing);

export const config = {
  // Never run on /api: the Next.js proxy buffers request bodies (10 MB default,
  // silently truncating beyond that), which would corrupt bill uploads (ARCHITECTURE Q-9).
  // Also skip Next internals and files with an extension (icons, images).
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)"],
};
