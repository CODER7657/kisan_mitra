# Deploy checklist

Backend and frontend are two Vercel projects on the Hobby plan (free, no card). Do them in
this order, because the frontend needs the backend's URL at build time.

## 1. Backend: `kisan-mitra-api`

1. Vercel > **Add New > Project**, import `CODER7657/kisan_mitra`, root directory `backend`.
   Framework preset **FastAPI**; the entry point is [backend/index.py](../backend/index.py)
   and [backend/vercel.json](../backend/vercel.json) pins the region to Mumbai (`bom1`).
2. Environment variables (Production):

   | Name | Value |
   |---|---|
   | `GROQ_API_KEY` | your Groq key (mark it Sensitive) |
   | `ALLOWED_ORIGINS` | the frontend's origin, e.g. `https://kisan-mitra-gilt.vercel.app` |
   | `RATE_LIMIT_PER_MIN` | optional, requests per client per minute |
   | `STORE_UPLOADS`, `BLOB_READ_WRITE_TOKEN` | optional, only to keep uploads in Vercel Blob |

3. Deploy, then check:

   ```bash
   curl https://kisan-mitra-api.vercel.app/health
   ```

   Expect `{"status":"ok"}`. Then open `https://kisan-mitra-api.vercel.app/` and confirm
   `"provider": "groq"` and `"photo_classifier": true`.

## 2. Frontend: `kisan-mitra`

1. Import the same repository again, root directory `frontend` (`adapter-static`).
2. Environment variable `VITE_API_URL` = `https://kisan-mitra-api.vercel.app` (https, no
   trailing path). It is read at build time, so redeploy after any change. A build without
   it, or pointing at localhost, fails on purpose with `VITE_API_URL is not set`.
   Do not mark it Sensitive: a build that pulls it would get a placeholder instead.

## 3. Check it as a visitor

- Open the site on a phone, type a question, send it. In the browser's network tab,
  `/analyze/` should go to the API URL, not localhost.
- Try a photo from the phone camera: the page shrinks it before upload, so it stays under
  Vercel's 4.5 MB request limit.
- Preview deployments have their own origins, which `ALLOWED_ORIGINS` does not list, so
  their requests are refused by CORS. Add a preview origin there only if you need it.

## Known limits of the free setup

- Groq's free tier is shared by the site and the nightly safety gate. When it is exhausted
  the API answers 503 with a plain message; the gate retries with longer timeouts.
- A function that has been idle starts on the next request. The page pings `/health` on
  load so that start overlaps with the farmer filling the form.
