# Deploy checklist

Backend on Render (free web service), frontend on Vercel (static). Do them in this order:
the frontend build needs the backend's URL, and the backend needs the frontend's origin.

## 1. Render: backend

1. Render dashboard > **New > Blueprint**, pick `CODER7657/kisan_mitra`, branch `main`.
   It reads [render.yaml](../render.yaml): service `kisan-mitra-api`, free plan, Singapore.
2. When asked for the secret values:

   | Variable | Value |
   |---|---|
   | `GROQ_API_KEY` | your Groq key (console.groq.com > API Keys). Never commit it. |
   | `ALLOWED_ORIGINS` | `https://kisan-mitra-gilt.vercel.app` (exact origin: https, no path; trailing slash is trimmed). Add more, comma separated, if you use a custom domain. |

   Optional, only if you change defaults: `GROQ_CHAT_MODEL`, `GROQ_ASR_MODEL`,
   `OPENAI_API_KEY` with `LLM_PROVIDER=openai` (sends photos to GPT-4o).
   Leave `STORE_UPLOADS` unset so farmers' photos and voice are not kept.
3. Wait for the deploy, then check:

   ```bash
   curl https://kisan-mitra-api.onrender.com/health
   ```

   Expect `{"status":"ok"}`. Then open `https://kisan-mitra-api.onrender.com/` and confirm
   `"provider": "groq"` and `"photo_classifier": true`. Use the URL Render shows if the
   name differs.

## 2. Vercel: frontend

1. Project settings > General: **Root Directory** `frontend`, framework SvelteKit.
2. Settings > Environment Variables, for **Production** (and Preview if you want previews to work):

   | Variable | Value |
   |---|---|
   | `VITE_API_URL` | `https://kisan-mitra-api.onrender.com` (the Render URL, https, no trailing path) |

3. Redeploy (Deployments > ... > Redeploy). `VITE_` values are baked in at build time, so a
   redeploy is needed after any change. A build without it, or pointing at localhost, fails
   on purpose with `VITE_API_URL is not set`.

## 3. Check it as a visitor

- Open the site on a phone, type a question, send it. The first answer after the backend
  has slept can take about a minute (Render free cold start); later ones are quick.
- In the browser's network tab, `/analyze/` should go to the Render URL, not localhost.
- Preview deployments have their own origins, which `ALLOWED_ORIGINS` does not list, so
  their requests are refused by CORS. Add a preview origin there only if you need it.

## Known limits of the free setup

- No rate limit on `/analyze/`: anyone with the URL can spend your Groq quota. Groq's own
  free-tier limits cap the damage; add a per-IP limit before sharing widely.
- One worker, 512 MB: measured peaks are in the README's Deploy section.
