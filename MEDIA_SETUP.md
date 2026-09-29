# Media Storage Setup (business logos)

`Business.logo` is uploaded from the app, served back to the web UI, and drawn
into every invoice, receipt and report PDF.

## Why logos disappear on Render

Render gives a web service an **ephemeral filesystem**: anything written at
runtime is thrown away on every deploy and restart. Uploaded logos vanish, and the
frontend quietly falls back to a broken-image placeholder, so nothing looks wrong
until a client receives an invoice without the logo.

Persistent disks are not offered on Render's free instance type. On the free plan
the only durable option is an object store.

## Option A - Cloudinary (recommended, works on the free plan)

1. Create an account at https://cloudinary.com.
2. Copy the environment variable from Dashboard -> Product Environment
   Credentials. It looks like:

   ```text
   CLOUDINARY_URL=cloudinary://<api-key>:<api-secret>@<cloud-name>
   ```

3. Set `CLOUDINARY_URL` under *Environment* in the Render dashboard and redeploy.

`cloudinary` and `django-cloudinary-storage` are already in `requirements.txt`,
and `smartinvoice/settings.py` switches `STORAGES["default"]` to
`MediaCloudinaryStorage` as soon as the variable is present. No code change and no
migration is needed.

The `/media/` route is registered only while the default storage is a
`FileSystemStorage`, so with Cloudinary the API returns an absolute
`https://res.cloudinary.com/...` URL and the frontend loads it directly.

## Option B - a mounted disk (paid instance types)

Attach a disk in the Render dashboard, then point `MEDIA_ROOT` at its mount path:

```text
MEDIA_ROOT=/var/data/media
```

Leave `CLOUDINARY_URL` empty. `MEDIA_ROOT` defaults to `<repo>/media`, which is
correct locally and wrong on an ephemeral host.

## Option C - local development

With neither variable set, uploads are written under `<repo>/media` and Django
itself serves them at `/media/...`. This is the default and needs no setup.

## What breaks if the logo is not on durable storage

Nothing raises. The upload succeeds, the API returns a URL, and the PDF is still
generated - just without the mark. That is why the failure is easy to miss.

## Verifying

* `GET /api/business/` returns a `logo` value: an absolute
  `https://res.cloudinary.com/...` URL with Cloudinary, `/media/logos/...` on local
  disk.
* `GET /api/invoice/<id>/pdf/` renders the logo in the header. Logo loading reads
  through the storage API rather than `FieldFile.path`, so it works on a local disk
  and on a remote backend alike.
* Redeploy, then load the logo URL again. It should still resolve; if it 404s, the
  storage is still ephemeral.

## SendGrid-style gotcha: absolute URLs

Frontend logo rendering passes absolute URLs through untouched and only prefixes
the API origin for relative `/media/...` paths, so both layouts work without an
extra `next.config` image domain entry.