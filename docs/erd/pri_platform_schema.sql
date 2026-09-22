-- PRI Platform — full-project ER schema (Modules A–H)
--
-- Postgres-flavored DDL, generated as a design artifact (not a Django migration) to be
-- imported into Lucidchart via: File -> Import Data -> Import from SQL.
--
-- Ground truth vs. spec: Modules A (partial), B (partial), and the accounts/workflow core
-- reflect what is actually implemented in apps/*/models.py as of 2026-09-17. Modules C
-- (now native Django, not CKAN — see docs/erd/README.md), D, E, F, G, and the rest of H
-- are modeled from their PRDs in the frontend repo's docs/PRDs/backend/ and do not exist
-- as code yet — treat those CREATE TABLE statements as provisional until built.

-- =====================================================================================
-- CORE / CROSS-CUTTING — Module H (User Access & Roles) + shared workflow
-- =====================================================================================

CREATE TABLE users_user (
    id              BIGSERIAL PRIMARY KEY,
    username        VARCHAR(150) NOT NULL UNIQUE,
    email           VARCHAR(254) NOT NULL,
    password        VARCHAR(128) NOT NULL,
    first_name      VARCHAR(150) NOT NULL DEFAULT '',
    last_name       VARCHAR(150) NOT NULL DEFAULT '',
    role            VARCHAR(20)  NOT NULL DEFAULT 'public'
                    CHECK (role IN ('public', 'researcher', 'editor', 'fellow', 'admin')),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    is_staff        BOOLEAN NOT NULL DEFAULT FALSE,
    is_superuser    BOOLEAN NOT NULL DEFAULT FALSE,
    date_joined     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE accounts_auditlog (
    id          BIGSERIAL PRIMARY KEY,
    actor_id    BIGINT REFERENCES users_user(id) ON DELETE SET NULL,
    module      VARCHAR(50)  NOT NULL,
    action      VARCHAR(100) NOT NULL,
    target      VARCHAR(200) NOT NULL,
    metadata    JSONB NOT NULL DEFAULT '{}',
    "timestamp" TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_auditlog_timestamp ON accounts_auditlog ("timestamp" DESC);

-- Recommended addition (not named in any PRD, but confirmed built in the live prototype's
-- account dashboard) — per-user API keys for programmatic dataset access.
CREATE TABLE accounts_apikey (
    id                    BIGSERIAL PRIMARY KEY,
    user_id               BIGINT NOT NULL REFERENCES users_user(id) ON DELETE CASCADE,
    key                   VARCHAR(64) NOT NULL UNIQUE,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_regenerated_at   TIMESTAMPTZ,
    revoked_at            TIMESTAMPTZ
);

-- Recommended addition — Modules D/F/G each independently require reliable
-- auto-email-on-status-change with no PRD-named backing table for it.
CREATE TABLE accounts_notificationlog (
    id                  BIGSERIAL PRIMARY KEY,
    recipient_user_id   BIGINT REFERENCES users_user(id) ON DELETE SET NULL,
    recipient_email     VARCHAR(254) NOT NULL,
    template_key        VARCHAR(100) NOT NULL,   -- e.g. "fellowship_status_change", "donation_receipt"
    related_module      VARCHAR(50) NOT NULL,    -- e.g. "fellowship", "donors", "forms"
    related_object      VARCHAR(200) NOT NULL,   -- "Model:id" style, matches accounts_auditlog.target
    status              VARCHAR(10) NOT NULL DEFAULT 'queued'
                        CHECK (status IN ('queued','sent','failed')),
    sent_at             TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Shared workflow_status values reused as a CHECK constraint on every WorkflowMixin table:
--   'draft' -> 'in_review' -> 'approved' -> 'published' -> 'unpublished'

-- =====================================================================================
-- SHARED TAXONOMY & SITE CONFIG — cross-cutting reference data used by Modules A/B/C/E
-- =====================================================================================

-- PRD-confirmed: Modules A/B/C/E each independently describe theme as a controlled
-- vocabulary shared across the platform's filter UIs, not per-table free text.
CREATE TABLE taxonomy_theme (
    id      BIGSERIAL PRIMARY KEY,
    slug    VARCHAR(30) NOT NULL UNIQUE,
    name    VARCHAR(50) NOT NULL UNIQUE
);
-- Canonical 8 values (confirmed on the live site's Research/Data/submission-form filters):
-- Education, Employment, Economics, Public Finance, Health, Governance, Demography, Migration.
-- projects_project deliberately left theme-free — no PRD evidence it needs one.

CREATE TABLE core_sitesettings (
    id                    BIGSERIAL PRIMARY KEY CHECK (id = 1),   -- singleton: exactly one row
    org_name              VARCHAR(200) NOT NULL,
    tagline               VARCHAR(300) NOT NULL DEFAULT '',
    registration_number   VARCHAR(100) NOT NULL DEFAULT '',
    cert_12a              VARCHAR(100) NOT NULL DEFAULT '',
    cert_80g              VARCHAR(100) NOT NULL DEFAULT '',
    primary_email         VARCHAR(254) NOT NULL DEFAULT '',
    primary_phone         VARCHAR(30) NOT NULL DEFAULT '',
    bank_account_name     VARCHAR(200) NOT NULL DEFAULT '',   -- SENSITIVE
    bank_account_number   VARCHAR(50) NOT NULL DEFAULT '',    -- SENSITIVE
    bank_ifsc             VARCHAR(20) NOT NULL DEFAULT '',    -- SENSITIVE
    bank_name_branch      VARCHAR(200) NOT NULL DEFAULT '',   -- SENSITIVE
    social_linkedin       VARCHAR(300) NOT NULL DEFAULT '',
    social_facebook       VARCHAR(300) NOT NULL DEFAULT '',
    social_twitter        VARCHAR(300) NOT NULL DEFAULT '',
    social_instagram      VARCHAR(300) NOT NULL DEFAULT '',
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- bank_* fields are sensitive — a real Django implementation needs field-level access
-- control (e.g. admin-only serializer fields), not just object-level row permissions.

-- =====================================================================================
-- MODULE A — Content Management System
-- =====================================================================================

CREATE TABLE content_contentblock (
    id                BIGSERIAL PRIMARY KEY,
    slug              VARCHAR(50) NOT NULL UNIQUE,
    title             VARCHAR(200) NOT NULL,
    body              TEXT NOT NULL,
    seo_title         VARCHAR(200) NOT NULL DEFAULT '',
    seo_description   VARCHAR(300) NOT NULL DEFAULT '',
    status            VARCHAR(20) NOT NULL DEFAULT 'draft'
                      CHECK (status IN ('draft','in_review','approved','published','unpublished')),
    created_by_id     BIGINT NOT NULL REFERENCES users_user(id) ON DELETE RESTRICT,
    reviewed_by_id    BIGINT REFERENCES users_user(id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE content_testimonial (
    id                BIGSERIAL PRIMARY KEY,
    slug              VARCHAR(50) NOT NULL UNIQUE,
    quote             TEXT NOT NULL,
    attribution       VARCHAR(200) NOT NULL,
    role              VARCHAR(200) NOT NULL DEFAULT '',
    status            VARCHAR(20) NOT NULL DEFAULT 'draft'
                      CHECK (status IN ('draft','in_review','approved','published','unpublished')),
    created_by_id     BIGINT NOT NULL REFERENCES users_user(id) ON DELETE RESTRICT,
    reviewed_by_id    BIGINT REFERENCES users_user(id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE content_personprofile (
    id                BIGSERIAL PRIMARY KEY,
    slug              VARCHAR(50) NOT NULL UNIQUE,
    name              VARCHAR(200) NOT NULL,
    role_title        VARCHAR(200) NOT NULL,
    "group"           VARCHAR(20) NOT NULL
                      CHECK ("group" IN ('team','patron','advisory','executive','fellow','past-fellow','author','partner')),
    bio               TEXT NOT NULL DEFAULT '',
    photo_url         VARCHAR(200) NOT NULL DEFAULT '',
    status            VARCHAR(20) NOT NULL DEFAULT 'draft'
                      CHECK (status IN ('draft','in_review','approved','published','unpublished')),
    created_by_id     BIGINT NOT NULL REFERENCES users_user(id) ON DELETE RESTRICT,
    reviewed_by_id    BIGINT REFERENCES users_user(id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE content_document (
    id                BIGSERIAL PRIMARY KEY,
    slug              VARCHAR(50) NOT NULL UNIQUE,
    title             VARCHAR(200) NOT NULL,
    file              VARCHAR(300) NOT NULL,
    description       TEXT NOT NULL DEFAULT '',
    document_type     VARCHAR(50) NOT NULL DEFAULT '',   -- e.g. "Annual Report", "Strategic Plan" — added for PRD A/F filtering, not yet in code
    year              INTEGER,                            -- added for PRD A/F filtering, not yet in code
    status            VARCHAR(20) NOT NULL DEFAULT 'draft'
                      CHECK (status IN ('draft','in_review','approved','published','unpublished')),
    created_by_id     BIGINT NOT NULL REFERENCES users_user(id) ON DELETE RESTRICT,
    reviewed_by_id    BIGINT REFERENCES users_user(id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Provisional: PRD-confirmed first-class entities, not yet implemented in apps/content/models.py.

CREATE TABLE content_event (
    id                   BIGSERIAL PRIMARY KEY,
    slug                 VARCHAR(50) NOT NULL UNIQUE,
    title                VARCHAR(200) NOT NULL,
    description          TEXT NOT NULL DEFAULT '',
    event_type           VARCHAR(20) NOT NULL
                         CHECK (event_type IN ('webinar','launch','workshop','advocacy_day','roundtable')),
    starts_at            TIMESTAMPTZ NOT NULL,
    ends_at              TIMESTAMPTZ,
    venue                VARCHAR(200) NOT NULL DEFAULT '',
    is_virtual           BOOLEAN NOT NULL DEFAULT FALSE,
    registration_link    VARCHAR(300) NOT NULL DEFAULT '',
    recording_url        VARCHAR(300) NOT NULL DEFAULT '',
    report_document_id   BIGINT REFERENCES content_document(id) ON DELETE SET NULL,
    status               VARCHAR(20) NOT NULL DEFAULT 'draft'
                         CHECK (status IN ('draft','in_review','approved','published','unpublished')),
    created_by_id        BIGINT NOT NULL REFERENCES users_user(id) ON DELETE RESTRICT,
    reviewed_by_id       BIGINT REFERENCES users_user(id) ON DELETE SET NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE content_joblisting (
    id                BIGSERIAL PRIMARY KEY,
    slug              VARCHAR(50) NOT NULL UNIQUE,
    title             VARCHAR(200) NOT NULL,
    description       TEXT NOT NULL DEFAULT '',
    location          VARCHAR(200) NOT NULL DEFAULT '',
    employment_type   VARCHAR(50) NOT NULL DEFAULT '',   -- e.g. "Full-time", "Contract", "Internship"
    application_link  VARCHAR(300) NOT NULL DEFAULT '',
    closes_at         DATE,
    status            VARCHAR(20) NOT NULL DEFAULT 'draft'
                      CHECK (status IN ('draft','in_review','approved','published','unpublished')),
    created_by_id     BIGINT NOT NULL REFERENCES users_user(id) ON DELETE RESTRICT,
    reviewed_by_id    BIGINT REFERENCES users_user(id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Distinct from content_personprofile's existing 'partner' group value (kept for individual
-- movement leaders); this table models partner *organizations*, per explicit PRD guidance
-- that PersonProfile is insufficient for org-type partners.
CREATE TABLE content_partner (
    id              BIGSERIAL PRIMARY KEY,
    slug            VARCHAR(50) NOT NULL UNIQUE,
    name            VARCHAR(200) NOT NULL,
    logo_url        VARCHAR(300) NOT NULL DEFAULT '',
    description     TEXT NOT NULL DEFAULT '',
    partner_type    VARCHAR(20) NOT NULL CHECK (partner_type IN ('institutional','consortium')),
    link            VARCHAR(300) NOT NULL DEFAULT '',
    status          VARCHAR(20) NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft','in_review','approved','published','unpublished')),
    created_by_id   BIGINT NOT NULL REFERENCES users_user(id) ON DELETE RESTRICT,
    reviewed_by_id  BIGINT REFERENCES users_user(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE content_namedprogram (
    id                   BIGSERIAL PRIMARY KEY,
    slug                 VARCHAR(50) NOT NULL UNIQUE,
    name                 VARCHAR(200) NOT NULL,
    description          TEXT NOT NULL DEFAULT '',
    funder_credit        VARCHAR(200) NOT NULL DEFAULT '',
    linked_document_id   BIGINT REFERENCES content_document(id) ON DELETE SET NULL,
    status               VARCHAR(20) NOT NULL DEFAULT 'draft'
                         CHECK (status IN ('draft','in_review','approved','published','unpublished')),
    created_by_id        BIGINT NOT NULL REFERENCES users_user(id) ON DELETE RESTRICT,
    reviewed_by_id       BIGINT REFERENCES users_user(id) ON DELETE SET NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE content_album (
    id            BIGSERIAL PRIMARY KEY,
    slug          VARCHAR(50) NOT NULL UNIQUE,
    title         VARCHAR(200) NOT NULL,
    description   TEXT NOT NULL DEFAULT ''
);

CREATE TABLE content_galleryphoto (
    id          BIGSERIAL PRIMARY KEY,
    album_id    BIGINT NOT NULL REFERENCES content_album(id) ON DELETE CASCADE,
    "order"     INTEGER NOT NULL DEFAULT 0,
    image_url   VARCHAR(300) NOT NULL,
    caption     VARCHAR(300) NOT NULL DEFAULT ''
);

CREATE TABLE content_office (
    id           BIGSERIAL PRIMARY KEY,
    name         VARCHAR(200) NOT NULL,
    address      TEXT NOT NULL,
    latitude     NUMERIC(9,6),
    longitude    NUMERIC(9,6),
    phone        VARCHAR(30) NOT NULL DEFAULT '',
    email        VARCHAR(254) NOT NULL DEFAULT '',
    is_primary   BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE content_department (
    id            BIGSERIAL PRIMARY KEY,
    slug          VARCHAR(50) NOT NULL UNIQUE,
    name          VARCHAR(200) NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    "order"       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE content_departmentarea (
    id              BIGSERIAL PRIMARY KEY,
    department_id   BIGINT NOT NULL REFERENCES content_department(id) ON DELETE CASCADE,
    "order"         INTEGER NOT NULL DEFAULT 0,
    name            VARCHAR(200) NOT NULL
);
-- Real 5 research wings, verified from the live /about page (not placeholders):
--   1. Center for Human Capital Development — Educational Statistics; Occupational and
--      Employment Patterns; Skill Development and Capacity Building; Accessibility and Opportunities
--   2. Center for Economic Analysis — Wealth and Income Distribution; Market Participation and
--      Ownership Patterns; Budget Allocation and Expenditure; Agriculture and Industry;
--      Public Infrastructure; Environment and Resilience
--   3. Department of Society Development — Organizations and Community Institutions;
--      Philanthropic and Welfare Activities; Inter-religious Harmony; Resource Allocation and Optimization
--   4. Center for Governance and Policy Analysis — Public Policy Analysis; Political Participation
--      and Legislative Representation; Schemes and Programmes
--   5. Demography & Health Research Unit — Demography and Population Studies; Migration and
--      Remittances; Healthcare Accessibility and Delivery
-- These deliberately do not map 1:1 onto taxonomy_theme's 8 values (e.g. Department of Society
-- Development has no matching theme) — Department and Theme are separate, unrelated lookups.

-- =====================================================================================
-- PROJECTS (existing app, feeds Homepage — not a lettered PRD module)
-- =====================================================================================

CREATE TABLE projects_project (
    id                BIGSERIAL PRIMARY KEY,
    slug              VARCHAR(50) NOT NULL UNIQUE,
    title             VARCHAR(200) NOT NULL,
    blurb             TEXT NOT NULL,
    image_url         VARCHAR(200) NOT NULL DEFAULT '',
    cta_label         VARCHAR(100) NOT NULL DEFAULT '',
    cta_href          VARCHAR(300) NOT NULL DEFAULT '',
    status            VARCHAR(20) NOT NULL DEFAULT 'draft'
                      CHECK (status IN ('draft','in_review','approved','published','unpublished')),
    created_by_id     BIGINT NOT NULL REFERENCES users_user(id) ON DELETE RESTRICT,
    reviewed_by_id    BIGINT REFERENCES users_user(id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =====================================================================================
-- MODULE B — Publication Repository
-- =====================================================================================

CREATE TABLE publications_publication (
    id                BIGSERIAL PRIMARY KEY,
    slug              VARCHAR(50) NOT NULL UNIQUE,
    title             VARCHAR(200) NOT NULL,
    abstract          TEXT NOT NULL,
    format            VARCHAR(20) NOT NULL
                      CHECK (format IN ('report','working_paper','data_story','brief','explainer','infographic','video')),
    theme_id          BIGINT NOT NULL REFERENCES taxonomy_theme(id) ON DELETE RESTRICT,
    language          VARCHAR(5) NOT NULL DEFAULT 'en' CHECK (language IN ('en','ml')),
    "date"            DATE NOT NULL,
    external_id       VARCHAR(100) NOT NULL DEFAULT '',   -- DOI if issued, else internal slug — see PRD B
    visibility        VARCHAR(10) NOT NULL DEFAULT 'public' CHECK (visibility IN ('public','private')),
    tags              TEXT[] NOT NULL DEFAULT '{}',
    views             INTEGER NOT NULL DEFAULT 0,
    cover_url         VARCHAR(200) NOT NULL DEFAULT '',
    status            VARCHAR(20) NOT NULL DEFAULT 'draft'
                      CHECK (status IN ('draft','in_review','approved','published','unpublished')),
    created_by_id     BIGINT NOT NULL REFERENCES users_user(id) ON DELETE RESTRICT,
    reviewed_by_id    BIGINT REFERENCES users_user(id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- M2M: a publication has many authors; a person profile can author many publications
CREATE TABLE publications_publication_authors (
    id                  BIGSERIAL PRIMARY KEY,
    publication_id      BIGINT NOT NULL REFERENCES publications_publication(id) ON DELETE CASCADE,
    personprofile_id    BIGINT NOT NULL REFERENCES content_personprofile(id) ON DELETE CASCADE,
    UNIQUE (publication_id, personprofile_id)
);

CREATE TABLE publications_publicationversion (
    id                BIGSERIAL PRIMARY KEY,
    publication_id    BIGINT NOT NULL REFERENCES publications_publication(id) ON DELETE CASCADE,
    version_number    INTEGER NOT NULL,
    file              VARCHAR(300) NOT NULL,
    uploaded_by_id    BIGINT NOT NULL REFERENCES users_user(id) ON DELETE RESTRICT,
    is_current        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (publication_id, version_number)
);

CREATE TABLE publications_publication_block (
    id                BIGSERIAL PRIMARY KEY,
    publication_id    BIGINT NOT NULL REFERENCES publications_publication(id) ON DELETE CASCADE,
    "order"           INTEGER NOT NULL DEFAULT 0,
    block_type        VARCHAR(20) NOT NULL
                      CHECK (block_type IN ('heading','subheading','paragraph','image','quote')),
    text              TEXT,
    image_url         VARCHAR(300),
    image_caption     VARCHAR(300)
);
-- Generic ordered body content for ANY publication format (report/working_paper/data_story/
-- brief/explainer/infographic/video) — headings, subtitles, paragraphs, and photos all live
-- here regardless of format. Publication.title stays on the parent row.

CREATE TABLE publications_publication_source (
    id                BIGSERIAL PRIMARY KEY,
    publication_id    BIGINT NOT NULL REFERENCES publications_publication(id) ON DELETE CASCADE,
    "order"           INTEGER NOT NULL DEFAULT 0,
    citation_text     TEXT NOT NULL,
    url               VARCHAR(300)
);
-- Generic bibliography/"Sources & Notes" list for any publication, not just Data Stories.

-- 1:1 with publications_publication where format='data_story'; enforced at the application
-- layer, not by a DB constraint. Everything below is Data-Story-only enrichment.
CREATE TABLE publications_datastory (
    id                BIGSERIAL PRIMARY KEY,
    publication_id    BIGINT NOT NULL UNIQUE REFERENCES publications_publication(id) ON DELETE CASCADE,
    area_label        VARCHAR(100) NOT NULL DEFAULT '',
    hook_note         VARCHAR(300) NOT NULL DEFAULT '',
    lede              TEXT NOT NULL DEFAULT '',
    why_it_matters    TEXT NOT NULL DEFAULT ''
);

CREATE TABLE publications_datastory_stat (
    id             BIGSERIAL PRIMARY KEY,
    datastory_id   BIGINT NOT NULL REFERENCES publications_datastory(id) ON DELETE CASCADE,
    "order"        INTEGER NOT NULL DEFAULT 0,
    kind           VARCHAR(10) NOT NULL CHECK (kind IN ('hook','callout')),
    value          VARCHAR(50) NOT NULL,
    label          VARCHAR(200) NOT NULL,
    sub            VARCHAR(200),
    tone           VARCHAR(20)
);

CREATE TABLE publications_datastory_chart (
    id             BIGSERIAL PRIMARY KEY,
    datastory_id   BIGINT NOT NULL REFERENCES publications_datastory(id) ON DELETE CASCADE,
    "order"        INTEGER NOT NULL DEFAULT 0,
    block_id       BIGINT REFERENCES publications_publication_block(id) ON DELETE SET NULL,
    chart_type     VARCHAR(10) NOT NULL CHECK (chart_type IN ('bar','scatter','line','map')),
    title          VARCHAR(200) NOT NULL,
    data           JSONB NOT NULL DEFAULT '{}',
    x_label        VARCHAR(100) NOT NULL DEFAULT '',
    y_label        VARCHAR(100) NOT NULL DEFAULT '',
    note           VARCHAR(300) NOT NULL DEFAULT ''
);

-- =====================================================================================
-- MODULE C — Data Repository & Dashboards (native Django — see docs/erd/README.md)
-- =====================================================================================

CREATE TABLE datarepo_dataset (
    id                BIGSERIAL PRIMARY KEY,
    slug              VARCHAR(50) NOT NULL UNIQUE,
    title             VARCHAR(200) NOT NULL,
    description       TEXT NOT NULL DEFAULT '',
    file              VARCHAR(300) NOT NULL,              -- object-storage key (S3 / DO Spaces), not stored in DB
    format            VARCHAR(20) NOT NULL CHECK (format IN ('csv','parquet','zip')),   -- fixed to match the live site; was csv/xlsx/geojson/spss
    theme_id          BIGINT NOT NULL REFERENCES taxonomy_theme(id) ON DELETE RESTRICT,
    geography         VARCHAR(100) NOT NULL DEFAULT '',
    "year"            INTEGER,
    source            VARCHAR(200) NOT NULL DEFAULT '',
    update_frequency  VARCHAR(50) NOT NULL DEFAULT '',
    tags              TEXT[] NOT NULL DEFAULT '{}',
    coverage          TEXT NOT NULL DEFAULT '',          -- narrative scope, distinct from `geography`
    last_updated      DATE,                              -- data-freshness date, distinct from row `updated_at`
    file_size         BIGINT,                            -- bytes; app layer formats for display
    download_count    INTEGER NOT NULL DEFAULT 0,
    "type"            VARCHAR(50) NOT NULL DEFAULT '',   -- e.g. "Administrative"/"Panel"/"Survey" — free text, open-ended
    visibility        VARCHAR(15) NOT NULL DEFAULT 'internal_only'
                      CHECK (visibility IN ('public','on_request','internal_only')),
    status            VARCHAR(20) NOT NULL DEFAULT 'draft'
                      CHECK (status IN ('draft','in_review','approved','published','unpublished')),
    created_by_id     BIGINT NOT NULL REFERENCES users_user(id) ON DELETE RESTRICT,
    reviewed_by_id    BIGINT REFERENCES users_user(id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE datarepo_dashboard (
    id                BIGSERIAL PRIMARY KEY,
    slug              VARCHAR(50) NOT NULL UNIQUE,
    title             VARCHAR(200) NOT NULL,
    description       TEXT NOT NULL DEFAULT '',
    embed_url         VARCHAR(500) NOT NULL,
    embed_type        VARCHAR(20) NOT NULL CHECK (embed_type IN ('datawrapper','tableau','d3')),
    theme_id          BIGINT NOT NULL REFERENCES taxonomy_theme(id) ON DELETE RESTRICT,
    geography         VARCHAR(100) NOT NULL DEFAULT '',
    "year"            INTEGER,
    "type"            VARCHAR(50) NOT NULL DEFAULT '',
    status            VARCHAR(20) NOT NULL DEFAULT 'draft'
                      CHECK (status IN ('draft','in_review','approved','published','unpublished')),
    created_by_id     BIGINT NOT NULL REFERENCES users_user(id) ON DELETE RESTRICT,
    reviewed_by_id    BIGINT REFERENCES users_user(id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- M2M: a dashboard can reference multiple datasets; a dataset can feed multiple dashboards
CREATE TABLE datarepo_dashboard_datasets (
    id            BIGSERIAL PRIMARY KEY,
    dashboard_id  BIGINT NOT NULL REFERENCES datarepo_dashboard(id) ON DELETE CASCADE,
    dataset_id    BIGINT NOT NULL REFERENCES datarepo_dataset(id) ON DELETE CASCADE,
    UNIQUE (dashboard_id, dataset_id)
);

CREATE TABLE datarepo_accessrequest (
    id                BIGSERIAL PRIMARY KEY,
    user_id           BIGINT NOT NULL REFERENCES users_user(id) ON DELETE CASCADE,
    dataset_id        BIGINT NOT NULL REFERENCES datarepo_dataset(id) ON DELETE CASCADE,
    status            VARCHAR(10) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','denied')),
    requested_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at       TIMESTAMPTZ,
    reviewed_by_id    BIGINT REFERENCES users_user(id) ON DELETE SET NULL,
    UNIQUE (user_id, dataset_id)
);

CREATE TABLE datarepo_accessgroup (
    id            BIGSERIAL PRIMARY KEY,
    slug          VARCHAR(50) NOT NULL UNIQUE,
    name          VARCHAR(200) NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE datarepo_accessgroup_member (
    id            BIGSERIAL PRIMARY KEY,
    group_id      BIGINT NOT NULL REFERENCES datarepo_accessgroup(id) ON DELETE CASCADE,
    user_id       BIGINT NOT NULL REFERENCES users_user(id) ON DELETE CASCADE,
    added_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    added_by_id   BIGINT REFERENCES users_user(id) ON DELETE SET NULL,
    UNIQUE (group_id, user_id)
);

CREATE TABLE datarepo_accessgroup_grant (
    id              BIGSERIAL PRIMARY KEY,
    group_id        BIGINT NOT NULL REFERENCES datarepo_accessgroup(id) ON DELETE CASCADE,
    dataset_id      BIGINT NOT NULL REFERENCES datarepo_dataset(id) ON DELETE CASCADE,
    granted_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    granted_by_id   BIGINT REFERENCES users_user(id) ON DELETE SET NULL,
    expires_at      TIMESTAMPTZ,
    UNIQUE (group_id, dataset_id)
);
-- Effective access to an on_request dataset = approved individual AccessRequest OR member of
-- a group with an active (non-expired) grant. internal_only stays staff-only regardless.
-- e.g. grant every member of "Kerala MLAs 2026" access to a set of datasets in one action,
-- instead of bulk-approving individual AccessRequests.

CREATE TABLE datarepo_downloadlog (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT REFERENCES users_user(id) ON DELETE SET NULL,   -- nullable: anonymous public downloads
    dataset_id      BIGINT NOT NULL REFERENCES datarepo_dataset(id) ON DELETE CASCADE,
    downloaded_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    ip              VARCHAR(45)
);

CREATE TABLE datarepo_favorite (
    id            BIGSERIAL PRIMARY KEY,
    user_id       BIGINT NOT NULL REFERENCES users_user(id) ON DELETE CASCADE,
    dataset_id    BIGINT NOT NULL REFERENCES datarepo_dataset(id) ON DELETE CASCADE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, dataset_id)
);

-- =====================================================================================
-- MODULE D — Fellowship / Internship Management (spec-only, not yet built)
-- =====================================================================================

CREATE TABLE fellowship_program (
    id            BIGSERIAL PRIMARY KEY,
    slug          VARCHAR(50) NOT NULL UNIQUE,
    name          VARCHAR(200) NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    start_date    DATE,
    end_date      DATE,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE fellowship_programtimelinestage (
    id            BIGSERIAL PRIMARY KEY,
    program_id    BIGINT NOT NULL REFERENCES fellowship_program(id) ON DELETE CASCADE,
    "order"       INTEGER NOT NULL DEFAULT 0,
    stage_label   VARCHAR(200) NOT NULL,   -- e.g. "Applications open", "Application deadline"
    stage_date    DATE
);

CREATE TABLE fellowship_applicationform (
    id            BIGSERIAL PRIMARY KEY,
    program_id    BIGINT NOT NULL REFERENCES fellowship_program(id) ON DELETE CASCADE,
    field_schema  JSONB NOT NULL,          -- form-builder-defined fields + required-document flags
    "version"     INTEGER NOT NULL DEFAULT 1,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE fellowship_application (
    id                     BIGSERIAL PRIMARY KEY,
    program_id             BIGINT NOT NULL REFERENCES fellowship_program(id) ON DELETE RESTRICT,
    applicant_name         VARCHAR(200) NOT NULL,
    applicant_email        VARCHAR(254) NOT NULL,
    applicant_phone        VARCHAR(30) NOT NULL DEFAULT '',
    applicant_user_id      BIGINT REFERENCES users_user(id) ON DELETE SET NULL,
    intake_channel         VARCHAR(30)
                           CHECK (intake_channel IN ('fellowship_portal','get_involved_form')),
                           -- nullable; hedges an explicitly unresolved PRD question on whether
                           -- Get Involved's lightweight intern form shares this intake pipeline
    answers                JSONB NOT NULL DEFAULT '{}',   -- keyed to the ApplicationForm.field_schema in effect at submission time
    status                 VARCHAR(20) NOT NULL DEFAULT 'submitted'
                           CHECK (status IN ('submitted','under_review','shortlisted','rejected','accepted','onboarded')),
    onboarded_profile_id   BIGINT REFERENCES content_personprofile(id) ON DELETE SET NULL,
    submitted_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE fellowship_applicationdocument (
    id                BIGSERIAL PRIMARY KEY,
    application_id    BIGINT NOT NULL REFERENCES fellowship_application(id) ON DELETE CASCADE,
    label             VARCHAR(100) NOT NULL,   -- e.g. "CV", "Writing Sample"
    file              VARCHAR(300) NOT NULL,
    uploaded_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE fellowship_review (
    id                BIGSERIAL PRIMARY KEY,
    application_id    BIGINT NOT NULL REFERENCES fellowship_application(id) ON DELETE CASCADE,
    reviewer_id       BIGINT NOT NULL REFERENCES users_user(id) ON DELETE RESTRICT,
    score             INTEGER,
    notes             TEXT NOT NULL DEFAULT '',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Implements Module H's "sub-role as annotation on the 5 base roles" pattern for Module D's Reviewer
CREATE TABLE fellowship_programreviewer (
    id            BIGSERIAL PRIMARY KEY,
    user_id       BIGINT NOT NULL REFERENCES users_user(id) ON DELETE CASCADE,
    program_id    BIGINT NOT NULL REFERENCES fellowship_program(id) ON DELETE CASCADE,
    assigned_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, program_id)
);

-- =====================================================================================
-- MODULE E — Media Watch & Rapid Response (spec-only, not yet built)
-- =====================================================================================

CREATE TABLE mediawatch_mediacase (
    id                BIGSERIAL PRIMARY KEY,
    item_type         VARCHAR(10) NOT NULL CHECK (item_type IN ('image','text','video')),
    item_file         VARCHAR(300) NOT NULL DEFAULT '',
    headline_text     TEXT NOT NULL DEFAULT '',
    note              TEXT NOT NULL DEFAULT '',   -- why it was flagged
    classification    VARCHAR(30) NOT NULL DEFAULT ''
                      CHECK (classification IN ('', 'hate_speech','misinformation','communal_bias','other')),
    theme_id          BIGINT REFERENCES taxonomy_theme(id) ON DELETE SET NULL,   -- nullable: not every case maps to a research theme
    source            VARCHAR(200) NOT NULL DEFAULT '',
    status            VARCHAR(15) NOT NULL DEFAULT 'flagged'
                      CHECK (status IN ('flagged','under_review','confirmed','public')),
    flagged_by_id     BIGINT NOT NULL REFERENCES users_user(id) ON DELETE RESTRICT,
    flagged_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_by_id    BIGINT REFERENCES users_user(id) ON DELETE SET NULL,
    reviewed_at       TIMESTAMPTZ
);

CREATE TABLE mediawatch_response (
    id                BIGSERIAL PRIMARY KEY,
    case_id           BIGINT NOT NULL REFERENCES mediawatch_mediacase(id) ON DELETE CASCADE,
    "type"            VARCHAR(20) NOT NULL
                      CHECK ("type" IN ('rebuttal','op_ed','explainer','press_statement','toolkit')),
    body              TEXT NOT NULL DEFAULT '',
    published_by_id   BIGINT NOT NULL REFERENCES users_user(id) ON DELETE RESTRICT,
    published_at      TIMESTAMPTZ
);

-- Replaces the old single `file` column on mediawatch_response — PRD confirms a response can
-- carry multiple files (e.g. a toolkit's zip of assets alongside a press-statement PDF).
CREATE TABLE mediawatch_response_attachment (
    id            BIGSERIAL PRIMARY KEY,
    response_id   BIGINT NOT NULL REFERENCES mediawatch_response(id) ON DELETE CASCADE,
    file          VARCHAR(300) NOT NULL,
    label         VARCHAR(100) NOT NULL DEFAULT ''   -- e.g. "Press statement PDF", "Toolkit assets zip"
);

-- =====================================================================================
-- MODULE F — Donor & Fundraising (spec-only, not yet built)
-- =====================================================================================

CREATE TABLE donors_donor (
    id            BIGSERIAL PRIMARY KEY,
    user_id       BIGINT NOT NULL UNIQUE REFERENCES users_user(id) ON DELETE CASCADE,
    name          VARCHAR(200) NOT NULL,
    phone         VARCHAR(30) NOT NULL DEFAULT '',
    address       TEXT NOT NULL DEFAULT ''
);

CREATE TABLE donors_campaign (
    id            BIGSERIAL PRIMARY KEY,
    slug          VARCHAR(50) NOT NULL UNIQUE,
    name          VARCHAR(200) NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    goal_amount   NUMERIC(12,2) NOT NULL,
    start_date    DATE,
    end_date      DATE,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE donors_donationtier (
    id                  BIGSERIAL PRIMARY KEY,
    label               VARCHAR(100) NOT NULL,
    suggested_amount    NUMERIC(12,2) NOT NULL,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE donors_donation (
    id                     BIGSERIAL PRIMARY KEY,
    donor_id               BIGINT NOT NULL REFERENCES donors_donor(id) ON DELETE RESTRICT,
    campaign_id            BIGINT REFERENCES donors_campaign(id) ON DELETE SET NULL,
    tier_id                BIGINT REFERENCES donors_donationtier(id) ON DELETE SET NULL,
    amount                 NUMERIC(12,2) NOT NULL,
    currency               VARCHAR(3) NOT NULL DEFAULT 'INR',
    payment_gateway        VARCHAR(20) NOT NULL CHECK (payment_gateway IN ('razorpay','instamojo')),
    payment_gateway_ref    VARCHAR(200) NOT NULL DEFAULT '',
    status                 VARCHAR(10) NOT NULL DEFAULT 'pending'
                           CHECK (status IN ('pending','succeeded','failed')),
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE donors_taxreceipt (
    id                BIGSERIAL PRIMARY KEY,
    donation_id       BIGINT NOT NULL UNIQUE REFERENCES donors_donation(id) ON DELETE CASCADE,
    receipt_number    VARCHAR(50) NOT NULL UNIQUE,
    file              VARCHAR(300) NOT NULL,
    generated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- PRD explicitly requires reconciling donation records against gateway transactions — a
-- status-only field on donors_donation can't support that; this is the raw event log.
CREATE TABLE donors_webhookevent (
    id             BIGSERIAL PRIMARY KEY,
    gateway        VARCHAR(20) NOT NULL CHECK (gateway IN ('razorpay','instamojo')),
    event_type     VARCHAR(50) NOT NULL,     -- e.g. "payment.captured", "payment.failed"
    raw_payload    JSONB NOT NULL,
    received_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at   TIMESTAMPTZ,
    donation_id    BIGINT REFERENCES donors_donation(id) ON DELETE SET NULL,
    result         VARCHAR(20) NOT NULL DEFAULT ''   -- e.g. "matched"/"unmatched"/"error" — free text
);

-- =====================================================================================
-- MODULE G — Forms, Surveys & Contact Management (spec-only, not yet built)
-- =====================================================================================

CREATE TABLE forms_formdefinition (
    id                  BIGSERIAL PRIMARY KEY,
    slug                VARCHAR(50) NOT NULL UNIQUE,
    name                VARCHAR(200) NOT NULL,
    field_schema        JSONB NOT NULL,
    routing_rule        JSONB NOT NULL DEFAULT '{}',   -- fixed destination, or field-keyed rule (e.g. contact-form category)
    crm_sync_enabled    BOOLEAN NOT NULL DEFAULT FALSE,
    anonymous_allowed   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE forms_formsubmission (
    id                BIGSERIAL PRIMARY KEY,
    form_id           BIGINT NOT NULL REFERENCES forms_formdefinition(id) ON DELETE CASCADE,
    data              JSONB NOT NULL,
    is_anonymous      BOOLEAN NOT NULL DEFAULT FALSE,
    submitter_name    VARCHAR(200),   -- NULL when is_anonymous=true, enforced at the application layer, never merely hidden
    submitter_email   VARCHAR(254),   -- NULL when is_anonymous=true
    submitter_ip      VARCHAR(45),    -- NULL when is_anonymous=true
    submitted_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =====================================================================================
-- End of schema — 55 tables across core, shared taxonomy, and Modules A, B, C, D, E, F, G, H
-- =====================================================================================
