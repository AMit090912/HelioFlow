# HelioFlow

**From First Lead to Solar Power.**

Lead qualification, quotation and project tracking for a rooftop solar installer in Vidarbha.
Homeowners upload an electricity bill, AI reads it, the system scores the lead and recommends a size,
sales sends a same-day quote with subsidy and payback, and customers follow their project on a status link.

| | |
|---|---|
| Frontend | Next.js (App Router, TypeScript), Tailwind CSS, shadcn/ui, next-intl (English, हिन्दी, मराठी) |
| Backend | FastAPI, SQLAlchemy 2, Alembic, PostgreSQL |
| AI | Groq vision (primary), Gemini Flash (fallback), manual entry (final fallback) |

- Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Local setup and deployment: `docs/deployment.md` (written in Milestone 7)
