# Module D (minimal slice): job openings and applications

The careers page's openings, and one application form for fellowships, internships and jobs. This is a deliberately small part of Module D ([PRD](../PRDs/D-fellowship-internship-management-system.md)): no programmes, cohorts, review scoring or applicant accounts. A job opening is either rolling (applications any time) or open until a deadline; there are no rounds to manage.

## Endpoints

| Endpoint | Access | Filters |
|---|---|---|
| `GET /api/v1/jobs/`, `GET /api/v1/jobs/{slug}/` | Public read (published only); workflow like other content | |
| `POST/PATCH/DELETE /api/v1/jobs/…`, `POST /api/v1/jobs/{slug}/transition/` | Contributors draft, editors and admins review and publish | |
| `POST /api/v1/apply/` | Anyone (no token; one sent is ignored), multipart | |
| `GET /api/v1/applications/` | Editor, admin | `status`, `kind` |
| `GET/PATCH /api/v1/applications/{id}/` | Editor, admin; PATCH changes `status` only | |
| `GET /api/v1/applications/{id}/files/{cv\|cover_letter\|writing_sample}/` | Editor, admin | |

## Job openings

A `JobOpening` is `slug`, `title`, `summary`, `description`, `location`, `employment_type`, `rolling` (default `false`), `deadline` (date or null), read-only `is_closed` (the deadline is before today's date in India, `Asia/Kolkata`; never true for a rolling role), `display_order` (lowest first, then oldest), `writing_sample` (`optional`, the default, or `required`: whether applicants for this role must send one), `description_pdf` (optional job description PDF, up to 5 MB, checked to be a real PDF; reads as its URL, presigned on S3; `null` or an empty multipart value removes it), plus the workflow fields. Editors upload the PDF with the opening (multipart `POST`/`PATCH`).

An opening is rolling or has a deadline, never both. A new opening that is not rolling and has no deadline is refused (400 on `deadline`: "Set a deadline, or choose rolling applications."), as is clearing the deadline of one that isn't rolling. A deadline sent with `rolling: true` wins: the opening is saved with `rolling: false`. Sending `rolling: true` without a deadline drops the stored deadline. Edits that send neither field are not checked. A closed opening stays listed (the site shows it as closed) until staff unpublish it.

Migration `careers/0005` makes `rolling` default to `false` and turns it off on every opening that has a deadline (the live Research Associate/Assistant opening had been saved as rolling, which hid its deadline).

Migration `careers/0002` creates the two openings PRI is hiring for, Research Associate and Data Analyst, both rolling and published, owned by the first admin. A database with no users gets none.

## Applying

`POST /api/v1/apply/` as `multipart/form-data`:

- `kind`: `fellowship`, `internship` or `job`.
- `job`: the opening's slug. Required when `kind` is `job`, and must be a published opening; ignored otherwise. A closed opening (deadline passed) is refused with 400 on `job`: "Applications for this role closed on 10 November 2026." The deadline day itself still accepts applications.
- `full_name`, `email`.
- `cv`, `cover_letter`: PDF, DOC or DOCX, at most 5 MB each. The file's first bytes must match its extension, so a renamed file of another kind is refused.
- `writing_sample`: same rules, optional; required (400 "This role asks for a writing sample.") when the job opening's `writing_sample` is `required`.
- `website`: honeypot, must stay empty. A filled one gets `201` and nothing is stored or sent.

Answers `201 {"detail": "Received."}`, `400` with field errors, or `429` when throttled: 3 an hour per applicant address (`application`) and a ceiling on all applications together (`application_global`, 60 an hour, `APPLICATION_GLOBAL_RATE`). As with contact, the frontend limits per visitor IP.

Each application emails `CONTACT_EMAIL` the applicant's name, address and what they applied for, with Reply-To set to the applicant and a link to the dashboard. **The files are not attached.**

## Files are private

CVs, cover letters and writing samples are stored under random names (`applications/<uuid>.<ext>`) and never appear in list or detail responses. Staff fetch a link one at a time with `GET /applications/{id}/files/cv/` (or `cover_letter`, `writing_sample`; `404` when no writing sample was sent), which answers `{"file": "<url>"}`: on S3 a presigned URL that expires, locally the media URL. Don't store or share these links.

## The inbox

An `Application` is `id`, `kind`, `job_slug`, `job_title`, `full_name`, `email`, `has_writing_sample`, `status` (`new`, `reviewed`), `created_at`, `handled_at`, `handled_by`. Newest first. `PATCH {"status": "reviewed"}` records who and when; `{"status": "new"}` reopens it. Every change writes an audit-log row (module `careers`, action `application_status`, target `application:{id}`). Applications can't be edited or deleted over the API.
