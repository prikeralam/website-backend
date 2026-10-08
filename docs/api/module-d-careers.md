# Module D (minimal slice): job openings and applications

The careers page's openings, and one application form for fellowships, internships and jobs. This is a deliberately small part of Module D ([PRD](../PRDs/D-fellowship-internship-management-system.md)): no programmes, cohorts, review scoring or applicant accounts. Applications are always open (rolling), so there are no deadlines or rounds to manage.

## Endpoints

| Endpoint | Access | Filters |
|---|---|---|
| `GET /api/v1/jobs/`, `GET /api/v1/jobs/{slug}/` | Public read (published only); workflow like other content | |
| `POST/PATCH/DELETE /api/v1/jobs/…`, `POST /api/v1/jobs/{slug}/transition/` | Contributors draft, editors and admins review and publish | |
| `POST /api/v1/apply/` | Anyone (no token; one sent is ignored), multipart | |
| `GET /api/v1/applications/` | Editor, admin | `status`, `kind` |
| `GET/PATCH /api/v1/applications/{id}/` | Editor, admin; PATCH changes `status` only | |
| `GET /api/v1/applications/{id}/files/{cv\|sop}/` | Editor, admin | |

## Job openings

A `JobOpening` is `slug`, `title`, `summary`, `description`, `location`, `employment_type`, `rolling` (default `true`: apply any time), `deadline` (date or null; only meaningful when not rolling), `display_order` (lowest first, then oldest), plus the workflow fields.

Migration `careers/0002` creates the two openings PRI is hiring for, Research Associate and Data Analyst, both rolling and published, owned by the first admin. A database with no users gets none.

## Applying

`POST /api/v1/apply/` as `multipart/form-data`:

- `kind`: `fellowship`, `internship` or `job`.
- `job`: the opening's slug. Required when `kind` is `job`, and must be a published opening; ignored otherwise.
- `full_name`, `email`.
- `cv`, `sop`: PDF, DOC or DOCX, at most 5 MB each. The file's first bytes must match its extension, so a renamed file of another kind is refused.
- `website`: honeypot, must stay empty. A filled one gets `201` and nothing is stored or sent.

Answers `201 {"detail": "Received."}`, `400` with field errors, or `429` when throttled: 3 an hour per applicant address (`application`) and a ceiling on all applications together (`application_global`, 60 an hour, `APPLICATION_GLOBAL_RATE`). As with contact, the frontend limits per visitor IP.

Each application emails `CONTACT_EMAIL` the applicant's name, address and what they applied for, with Reply-To set to the applicant and a link to the dashboard. **The files are not attached.**

## Files are private

CVs and SOPs are stored under random names (`applications/<uuid>.<ext>`) and never appear in list or detail responses. Staff fetch a link one at a time with `GET /applications/{id}/files/cv/` (or `sop`), which answers `{"file": "<url>"}`: on S3 a presigned URL that expires, locally the media URL. Don't store or share these links.

## The inbox

An `Application` is `id`, `kind`, `job_slug`, `job_title`, `full_name`, `email`, `status` (`new`, `reviewed`), `created_at`, `handled_at`, `handled_by`. Newest first. `PATCH {"status": "reviewed"}` records who and when; `{"status": "new"}` reopens it. Every change writes an audit-log row (module `careers`, action `application_status`, target `application:{id}`). Applications can't be edited or deleted over the API.
