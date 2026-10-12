# Events & Campaigns

Events and campaigns shown on the public Events & Campaigns page and the homepage. Workflowed like the other content types.

## Endpoints

| Endpoint | Access | Filters |
|---|---|---|
| `GET /api/v1/events/`, `GET /api/v1/events/{slug}/` | Public read (published only) | `kind` |
| `POST/PATCH/DELETE /api/v1/events/…`, `POST /api/v1/events/{slug}/transition/` | Contributors draft, editors and admins review and publish | |
| `POST /api/v1/events/{slug}/images/` (multipart: `image`, optional `caption`), `DELETE /api/v1/events/{slug}/images/{id}/` | Same as editing the event: its contributor creator while it is a draft, editors and admins always | |

## Fields

An `Event` is `slug`, `kind` (`event` or `campaign`), `title`, `summary`, `body`, `start_date`, `end_date` (optional; must not be before the start), `location`, `image_url` and `image` (an uploaded image wins, same rules as other images), `registration_url` (optional, https only; the site links straight to it), plus the workflow fields.

Details, all optional:
- `mode`: `in_person`, `online` or `hybrid`.
- `start_time`, `end_time`: local (India) times. On a one-day event the end can't come before the start.
- `date_note`: text shown instead of the exact date while it isn't fixed ("December 2026 (3rd or 4th week)"). `start_date` still orders events and decides whether one is upcoming.
- `collaborators`, `speakers`, `focus_areas`: lists of strings, at most 30 each, trimmed, no blank items. A speaker reads "Role: Name (detail)". A focus area may start with "Heading: ". The frontend splits both on the first ": ".
- `images` (read only): the photo gallery, `[{id, image, caption}]`, in the order they were added. `image` is the URL, presigned on S3. Up to 20 photos, same file rules as other images. The event's own `image` stays its cover on cards.

Migration `events/0003_october_events` loads PRI's four events of 2025-2026 once (updating the two entered by hand, which keep their images; creating the others only when a user exists to own them).

Lists are newest first by `start_date`. Whether an event is upcoming or past is for the client to decide from the dates.
