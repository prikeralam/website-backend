# Events & Campaigns

Events and campaigns shown on the public Events & Campaigns page and the homepage. Workflowed like the other content types.

## Endpoints

| Endpoint | Access | Filters |
|---|---|---|
| `GET /api/v1/events/`, `GET /api/v1/events/{slug}/` | Public read (published only) | `kind` |
| `POST/PATCH/DELETE /api/v1/events/…`, `POST /api/v1/events/{slug}/transition/` | Contributors draft, editors and admins review and publish | |

## Fields

An `Event` is `slug`, `kind` (`event` or `campaign`), `title`, `summary`, `body`, `start_date`, `end_date` (optional; must not be before the start), `location`, `image_url` and `image` (an uploaded image wins, same rules as other images), `registration_url` (optional, https only; the site links straight to it), plus the workflow fields.

Lists are newest first by `start_date`. Whether an event is upcoming or past is for the client to decide from the dates.
