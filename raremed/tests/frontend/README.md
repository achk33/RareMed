# Frontend tests

Navigation and upload-placeholder tests live in the frontend package:

- `frontend/src/navigation.test.tsx`
- `frontend/src/upload-placeholder.test.tsx`

Run them from `frontend` with `npm test`. Vite resolves React from that package. Backend tests stay in `tests/backend` and run with pytest from the repository root.
