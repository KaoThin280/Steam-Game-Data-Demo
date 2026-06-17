# Front-end (placeholder)

This directory will hold the user-facing web application. It is intended to be deployed on **Vercel** and kept entirely separate from the back-end VPS to keep the GCP free-tier VM lightweight.

## Tech stack (suggested)

- **Next.js 14+ (App Router)** with TypeScript
- **Tailwind CSS** for styling
- **Chart.js** for rendering the configs produced by the AI `charting` tool
- **Fetch / SWR / TanStack Query** for API calls

## Talking to the back-end

All requests go through one environment variable:

```
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
```

The front-end only calls the public REST API exposed under `/api/v1`. There is no direct database access from the browser.

## Deploying to Vercel

1. Push your front-end code to this repository's `front_end/` directory.
2. In Vercel, **Add New → Project → Import Git Repository**.
3. Set **Root Directory** to `front_end`.
4. Vercel auto-detects Next.js. Override the build command if needed (`next build`).
5. Add environment variables:
   - `NEXT_PUBLIC_API_URL` = the public URL of the back-end.
6. Click **Deploy**. Vercel issues `https://<project>.vercel.app` immediately.

Subsequent pushes to `main` automatically trigger a new Vercel deployment.

## Local development

```bash
cd front_end
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```

The front-end will be available at <http://localhost:3000>. Make sure the back-end is running on port 8000 (see `../back_end/README.md`).

## Why is this folder empty?

The front-end has not been implemented yet. It will be added in a future milestone. Until then the directory contains only this README so the layout is documented.