# Inversiq Frontend

Next.js frontend for Inversiq, built with Tailwind CSS and shadcn/ui.

## Tech stack

- Next.js App Router
- Tailwind CSS (v4)
- shadcn/ui component primitives
- TanStack Query for server state
- React Hook Form + Zod for forms

## Run locally

1. Copy `.env.example` to `.env.local`.
2. Set `NEXT_PUBLIC_API_BASE_URL` to your FastAPI backend URL.
3. Install dependencies and run:

```bash
npm install
npm run dev
```

The app runs on [http://localhost:3000](http://localhost:3000).

## Architecture

See `docs/frontend-architecture.md` for the current migration baseline and target structure.
