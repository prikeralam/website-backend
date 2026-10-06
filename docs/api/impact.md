# Impact: "Cited in" and recognition

Two workflowed content types (Draft → Review → Approve → Publish, like Module A) that show PRI's reach on the public site. Both are in the `impact` app and addressed by slug.

## Endpoints

| Endpoint | Access | Filters |
|---|---|---|
| `GET/POST /api/v1/mentions/` | Public read (published only); write: contributor role | `kind` |
| `GET/PATCH/DELETE /api/v1/mentions/{slug}/`, `POST …/transition/` | As Module A | |
| `GET/POST /api/v1/recognition/` | Public read (published only); write: contributor role | |
| `GET/PATCH/DELETE /api/v1/recognition/{slug}/`, `POST …/transition/` | As Module A | |

## Mention

Somewhere PRI's research or data was cited or covered. Newest `date` first.

- `title`, `publisher`, `url` (https only, since the site links to it directly), `kind` (`news`, `research`, `report`, `legislature`, `other`), `date`, `summary` (optional).
- `publisher_logo`: optional image upload (JPG, PNG, WebP, 5 MB; `null` removes it), same rules as person photos.
- `publication` and `dataset`: optional slugs of the PRI work that was cited.

## Recognition

An award, grant or membership PRI has received. Newest `year` first.

- `title`, `awarded_by`, `year`, `description` (optional), `url` (optional, https only), `image` (optional upload, as above).
