# Phase 15 — Farmer listing photos in Supabase Storage

The new Supabase project now has an `agriroute-produce-images` bucket for
produce listing photos. The bucket permits public reads so marketplace listings
can show their photos, limits objects to PNG/JPEG/WebP, and caps each object at
5 MiB. Only the FastAPI server uploads objects; there is no anonymous upload
policy and the browser never receives the server key.

`POST /produce/{batch_id}/image` requires the farmer's FastAPI bearer token and
the farmer must own the batch. The API checks the declared MIME type, verifies
the image signature, enforces the size limit, uploads to a random farmer/batch
path, and saves the resulting public URL to `produce_batches.image_url`. An
upload failure leaves the batch listed and reports that its photo was not saved.
Produce cards show the stored image for users who can see that listing.

## Configure the API

Add these variables to the private `backend/.env` file:

```dotenv
SUPABASE_URL=https://suhewsisyqhitnxoabqv.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<legacy service_role key from Supabase API keys settings>
```

Use the legacy `service_role` key only on the backend. Never use it in `VITE_` variables,
the frontend bundle, source control, or chat. Supabase's Storage bucket and
upload limits were created in the project; the service key must be copied
directly into the local ignored `.env` file by the project owner. The app does
not print or return this key.

Install the backend dependencies after updating `requirements.txt`, then
restart FastAPI. The upload route requires `httpx` and `python-multipart`.

## Boundaries

- Public-read bucket URLs are intentionally shareable. Do not upload private
  documents or sensitive personal images to this bucket.
- Uploading a photo is optional. The listing remains saved when the storage
  service is not configured or an upload fails.
- The visual quality assessment remains a clearly labeled fixed demo result;
  storing an image does not run image analysis.
- Replacing/deleting photos, image resizing, retention cleanup, and signed
  private image delivery remain future work.

## Verification status

The bucket was created in the new Supabase project and verified with public
reads, the allowed image MIME types, and a 5 MiB limit. Migration
`9c71d435bc02` was applied, and the active Supabase project/database were
confirmed through the Supabase connection. Backend dependencies were installed
in a new `backend/.venv-local` environment, and FastAPI imported successfully
with the image upload route present in OpenAPI. `backend/.gitignore` excludes
that local environment. `backend/app/database.py` explicitly selects the
installed psycopg2 driver for plain PostgreSQL URLs.

The new project's `SUPABASE_URL` and the provided server-only
`SUPABASE_SERVICE_ROLE_KEY` are now set in the ignored local `backend/.env`.
The supplied HTTPS `/rest/v1/` endpoint is an API URL, not a PostgreSQL
`DATABASE_URL`. The project pooler URLs are now configured locally, and the
`pgbouncer=true` hint is removed from the SQLAlchemy connection options because
psycopg2 rejects it. Read-only checks reached both poolers, but Supabase
rejected the supplied database password on ports 6543 and 5432. No live local
API-to-database or Storage upload check passed. Reset or re-copy the database
password in Supabase and update both URLs in `backend/.env`. The service key
was pasted into chat, so rotate it in Supabase before production use. Do not
paste replacement secrets into chat or frontend configuration.
