# Inversiq Frontend Refactor Baseline

## Current state

- Existing UI is server-rendered through FastAPI/Jinja templates with HTMX and inline scripts.
- Styling is mostly inline Tailwind CDN and template-local CSS, which limits consistency and reusability.
- Data fetching and UI composition are mixed inside templates, making large-scale UX refactors harder.

## Target architecture

- `src/app/`: route-level composition (Next.js App Router).
- `src/components/ui/`: shadcn/ui primitives.
- `src/components/layout/`: shell, sidebar, topbar, shared frame.
- `src/components/dashboard/`: dashboard-specific feature components.
- `src/components/forms/`: form composition with React Hook Form + Zod.
- `src/lib/api/`: explicit API wrappers to existing FastAPI endpoints.
- `src/hooks/`: reusable TanStack Query hooks for server state.
- `src/types/`: shared API payload types.

## Integration principles

- FastAPI remains source of truth for auth, workflow logic, pricing, uploads, and tenant behavior.
- Frontend only handles presentation state and lightweight client interactions.
- API contracts are consumed as-is; frontend wrappers isolate fetch/error behavior.
