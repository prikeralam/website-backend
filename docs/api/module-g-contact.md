# Module G (contact slice): contact messages

The public contact form, and the inbox where staff read what arrives. This is the smallest part of Module G ([PRD](../PRDs/G-forms-surveys-contact-management.md)): one fixed form, not the generic form engine the PRD describes. Newsletter, volunteer and other forms are not built.

## Endpoints

| Endpoint | Access | Filters |
|---|---|---|
| `POST /api/v1/contact/` | Anyone (no token needed; one sent is ignored) | |
| `GET /api/v1/contact-messages/` | Editor, admin | `status`, `category` |
| `GET/PATCH /api/v1/contact-messages/{id}/` | Editor, admin; PATCH changes `status` only | |

## Sending a message

`POST /api/v1/contact/` with `category` (`research`, `media`, `general`), `name`, `email` and `message` (10 to 5,000 characters). Answers `201 {"detail": "Received."}`, `400` with field errors, or `429` when throttled.

- **Honeypot:** `website` is optional and must stay empty. The frontend hides it from people; a filled one gets the same `201` and nothing is stored or sent.
- **Throttling:** 5 an hour per sender address (`contact`), and a ceiling on all messages together (`contact_global`, 200 an hour, `CONTACT_GLOBAL_RATE`). Every message arrives from the frontend's server, so the backend can't limit per visitor IP; the frontend does that.
- **Email:** each message is emailed to `CONTACT_EMAIL` (default `contact@priresearch.in`), whatever its category, with Reply-To set to the sender. The message is saved first; if sending fails, the failure is logged and the message is still in the inbox.

## The inbox

A `ContactMessage` is `id`, `category`, `name`, `email`, `message`, `status` (`new`, `handled`), `created_at`, `handled_at`, `handled_by` (user id). Newest first.

`PATCH {"status": "handled"}` records who handled it and when; `{"status": "new"}` reopens it and clears both. Every status change writes an audit-log row (module `contact`, action `contact_status`, target `contact_message:{id}`, metadata `{from, to}`). Messages can't be edited or deleted over the API.
