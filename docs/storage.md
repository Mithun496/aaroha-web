# File Storage

## Local Development

`STORAGE_PROVIDER=local` stores randomized files below `UPLOAD_DIR` (default `instance/uploads`). Public image uploads are stored beneath `public/`; verification documents are stored beneath `private/`. Local storage is intended for development only and is rejected in production.

The local and S3-compatible upload paths enforce a maximum byte size (`MAX_UPLOAD_BYTES`, default 10 MiB), allowlisted extensions, and basic signature checks for JPEG, PNG, WebP, and PDF. Uploaded names are randomized. `MAX_CONTENT_LENGTH` also limits the complete HTTP request body.

## Production Storage

Production requires `STORAGE_PROVIDER=s3` and `STORAGE_BUCKET`. Optional settings:

| Variable | Use |
| --- | --- |
| `STORAGE_ENDPOINT` | S3-compatible service endpoint; omit for AWS S3. |
| `STORAGE_REGION` | Bucket region. |
| `STORAGE_ACCESS_KEY` | Access key when not using a workload/IAM role. |
| `STORAGE_SECRET_KEY` | Secret key paired with the access key; never commit it. |
| `STORAGE_PUBLIC_BASE_URL` | Optional origin for public media only. |
| `UPLOAD_DIR` | Local path configuration; it is not a substitute for production object storage. |

The SDK uses its default credential provider chain when explicit access keys are absent, allowing workload/IAM roles. No credentials are hardcoded. Configure the bucket with public access blocked by default. Uploads do not set a public ACL. Public distribution must be deliberately configured for the `public/` prefix only; `private/` objects must never be reachable through that origin.

Public images are retrieved through `/media/<key>` or a configured public media origin. Private identity/credential documents are retrieved only through the admin-protected `/admin/private-file/<key>` route. Both local and S3 paths enforce namespace/path validation; S3 missing-object errors are translated to not-found responses. S3 failures are not hidden by falling back to local storage.

## Verification Limits

Local storage traversal, signature, size, and public/private separation are covered by automated tests. No live S3 bucket, bucket policy, IAM role, provider endpoint, or private-object ACL behavior was tested in this workspace. Verify those controls in the actual cloud account before accepting real documents.
