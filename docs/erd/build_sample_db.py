"""
Builds pri_platform_sample.db — a SQLite database with the full PRI platform
schema (all 8 modules) and hand-written sample data, so the ER diagram's
relationships can be browsed in any local SQLite GUI (DB Browser for SQLite,
TablePlus, DataGrip, etc.) instead of just read off the diagram.

This is a design/exploration aid, not a Django migration — SQLite syntax
differs from the Postgres DDL in docs/erd/pri_platform_schema.sql (no JSONB/
TEXT[]/TIMESTAMPTZ types; JSON and tag arrays are stored as TEXT holding a
JSON string). Table names, columns, and foreign keys match that file 1:1.

Run: python docs/erd/build_sample_db.py
Output: docs/erd/pri_platform_sample.db (overwritten each run)
"""

import json
import os
import re
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "pri_platform_sample.db"

SCHEMA = """
PRAGMA foreign_keys = ON;

-- ===================== CORE / MODULE H =====================

CREATE TABLE users_user (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL UNIQUE,
    email           TEXT NOT NULL,
    password        TEXT NOT NULL DEFAULT 'x',
    first_name      TEXT NOT NULL DEFAULT '',
    last_name       TEXT NOT NULL DEFAULT '',
    role            TEXT NOT NULL DEFAULT 'public'
                    CHECK (role IN ('public','researcher','editor','fellow','admin')),
    is_active       BOOLEAN NOT NULL DEFAULT 1,
    is_staff        BOOLEAN NOT NULL DEFAULT 0,
    is_superuser    BOOLEAN NOT NULL DEFAULT 0,
    date_joined     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE accounts_auditlog (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id    INTEGER REFERENCES users_user(id) ON DELETE SET NULL,
    module      TEXT NOT NULL,
    action      TEXT NOT NULL,
    target      TEXT NOT NULL,
    metadata    TEXT NOT NULL DEFAULT '{}',
    "timestamp" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE accounts_apikey (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id               INTEGER NOT NULL REFERENCES users_user(id) ON DELETE CASCADE,
    key                   TEXT NOT NULL UNIQUE,
    created_at            TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_regenerated_at   TEXT,
    revoked_at            TEXT
);

CREATE TABLE accounts_notificationlog (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    recipient_user_id   INTEGER REFERENCES users_user(id) ON DELETE SET NULL,
    recipient_email     TEXT NOT NULL,
    template_key        TEXT NOT NULL,
    related_module      TEXT NOT NULL,
    related_object      TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'queued'
                        CHECK (status IN ('queued','sent','failed')),
    sent_at             TEXT,
    created_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ===================== SHARED TAXONOMY & SITE CONFIG =====================

CREATE TABLE taxonomy_theme (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    slug    TEXT NOT NULL UNIQUE,
    name    TEXT NOT NULL UNIQUE
);

CREATE TABLE core_sitesettings (
    id                    INTEGER PRIMARY KEY CHECK (id = 1),
    org_name              TEXT NOT NULL,
    tagline               TEXT NOT NULL DEFAULT '',
    registration_number   TEXT NOT NULL DEFAULT '',
    cert_12a              TEXT NOT NULL DEFAULT '',
    cert_80g              TEXT NOT NULL DEFAULT '',
    primary_email         TEXT NOT NULL DEFAULT '',
    primary_phone         TEXT NOT NULL DEFAULT '',
    bank_account_name     TEXT NOT NULL DEFAULT '',
    bank_account_number   TEXT NOT NULL DEFAULT '',
    bank_ifsc             TEXT NOT NULL DEFAULT '',
    bank_name_branch      TEXT NOT NULL DEFAULT '',
    social_linkedin       TEXT NOT NULL DEFAULT '',
    social_facebook       TEXT NOT NULL DEFAULT '',
    social_twitter        TEXT NOT NULL DEFAULT '',
    social_instagram      TEXT NOT NULL DEFAULT '',
    updated_at            TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ===================== MODULE A — CMS =====================

CREATE TABLE content_contentblock (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    slug              TEXT NOT NULL UNIQUE,
    title             TEXT NOT NULL,
    body              TEXT NOT NULL,
    seo_title         TEXT NOT NULL DEFAULT '',
    seo_description   TEXT NOT NULL DEFAULT '',
    status            TEXT NOT NULL DEFAULT 'draft'
                      CHECK (status IN ('draft','in_review','approved','published','unpublished')),
    created_by_id     INTEGER NOT NULL REFERENCES users_user(id) ON DELETE RESTRICT,
    reviewed_by_id    INTEGER REFERENCES users_user(id) ON DELETE SET NULL,
    created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE content_testimonial (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    slug              TEXT NOT NULL UNIQUE,
    quote             TEXT NOT NULL,
    attribution       TEXT NOT NULL,
    role              TEXT NOT NULL DEFAULT '',
    status            TEXT NOT NULL DEFAULT 'draft'
                      CHECK (status IN ('draft','in_review','approved','published','unpublished')),
    created_by_id     INTEGER NOT NULL REFERENCES users_user(id) ON DELETE RESTRICT,
    reviewed_by_id    INTEGER REFERENCES users_user(id) ON DELETE SET NULL,
    created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE content_personprofile (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    slug              TEXT NOT NULL UNIQUE,
    name              TEXT NOT NULL,
    role_title        TEXT NOT NULL,
    "group"           TEXT NOT NULL
                      CHECK ("group" IN ('team','patron','advisory','executive','fellow','past-fellow','author','partner')),
    bio               TEXT NOT NULL DEFAULT '',
    photo_url         TEXT NOT NULL DEFAULT '',
    status            TEXT NOT NULL DEFAULT 'draft'
                      CHECK (status IN ('draft','in_review','approved','published','unpublished')),
    created_by_id     INTEGER NOT NULL REFERENCES users_user(id) ON DELETE RESTRICT,
    reviewed_by_id    INTEGER REFERENCES users_user(id) ON DELETE SET NULL,
    created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE content_document (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    slug              TEXT NOT NULL UNIQUE,
    title             TEXT NOT NULL,
    file              TEXT NOT NULL,
    description       TEXT NOT NULL DEFAULT '',
    document_type     TEXT NOT NULL DEFAULT '',
    "year"            INTEGER,
    status            TEXT NOT NULL DEFAULT 'draft'
                      CHECK (status IN ('draft','in_review','approved','published','unpublished')),
    created_by_id     INTEGER NOT NULL REFERENCES users_user(id) ON DELETE RESTRICT,
    reviewed_by_id    INTEGER REFERENCES users_user(id) ON DELETE SET NULL,
    created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE content_event (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    slug                 TEXT NOT NULL UNIQUE,
    title                TEXT NOT NULL,
    description          TEXT NOT NULL DEFAULT '',
    event_type           TEXT NOT NULL
                         CHECK (event_type IN ('webinar','launch','workshop','advocacy_day','roundtable')),
    starts_at            TEXT NOT NULL,
    ends_at              TEXT,
    venue                TEXT NOT NULL DEFAULT '',
    is_virtual           BOOLEAN NOT NULL DEFAULT 0,
    registration_link    TEXT NOT NULL DEFAULT '',
    recording_url        TEXT NOT NULL DEFAULT '',
    report_document_id   INTEGER REFERENCES content_document(id) ON DELETE SET NULL,
    status               TEXT NOT NULL DEFAULT 'draft'
                         CHECK (status IN ('draft','in_review','approved','published','unpublished')),
    created_by_id        INTEGER NOT NULL REFERENCES users_user(id) ON DELETE RESTRICT,
    reviewed_by_id       INTEGER REFERENCES users_user(id) ON DELETE SET NULL,
    created_at           TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at           TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE content_joblisting (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    slug              TEXT NOT NULL UNIQUE,
    title             TEXT NOT NULL,
    description       TEXT NOT NULL DEFAULT '',
    location          TEXT NOT NULL DEFAULT '',
    employment_type   TEXT NOT NULL DEFAULT '',
    application_link  TEXT NOT NULL DEFAULT '',
    closes_at         TEXT,
    status            TEXT NOT NULL DEFAULT 'draft'
                      CHECK (status IN ('draft','in_review','approved','published','unpublished')),
    created_by_id     INTEGER NOT NULL REFERENCES users_user(id) ON DELETE RESTRICT,
    reviewed_by_id    INTEGER REFERENCES users_user(id) ON DELETE SET NULL,
    created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE content_partner (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    slug            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    logo_url        TEXT NOT NULL DEFAULT '',
    description     TEXT NOT NULL DEFAULT '',
    partner_type    TEXT NOT NULL CHECK (partner_type IN ('institutional','consortium')),
    link            TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft','in_review','approved','published','unpublished')),
    created_by_id   INTEGER NOT NULL REFERENCES users_user(id) ON DELETE RESTRICT,
    reviewed_by_id  INTEGER REFERENCES users_user(id) ON DELETE SET NULL,
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE content_namedprogram (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    slug                 TEXT NOT NULL UNIQUE,
    name                 TEXT NOT NULL,
    description          TEXT NOT NULL DEFAULT '',
    funder_credit        TEXT NOT NULL DEFAULT '',
    linked_document_id   INTEGER REFERENCES content_document(id) ON DELETE SET NULL,
    status               TEXT NOT NULL DEFAULT 'draft'
                         CHECK (status IN ('draft','in_review','approved','published','unpublished')),
    created_by_id        INTEGER NOT NULL REFERENCES users_user(id) ON DELETE RESTRICT,
    reviewed_by_id       INTEGER REFERENCES users_user(id) ON DELETE SET NULL,
    created_at           TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at           TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE content_album (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    slug          TEXT NOT NULL UNIQUE,
    title         TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT ''
);

CREATE TABLE content_galleryphoto (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    album_id    INTEGER NOT NULL REFERENCES content_album(id) ON DELETE CASCADE,
    "order"     INTEGER NOT NULL DEFAULT 0,
    image_url   TEXT NOT NULL,
    caption     TEXT NOT NULL DEFAULT ''
);

CREATE TABLE content_office (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    address      TEXT NOT NULL,
    latitude     REAL,
    longitude    REAL,
    phone        TEXT NOT NULL DEFAULT '',
    email        TEXT NOT NULL DEFAULT '',
    is_primary   BOOLEAN NOT NULL DEFAULT 0
);

CREATE TABLE content_department (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    slug          TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    "order"       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE content_departmentarea (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id   INTEGER NOT NULL REFERENCES content_department(id) ON DELETE CASCADE,
    "order"         INTEGER NOT NULL DEFAULT 0,
    name            TEXT NOT NULL
);

-- ===================== PROJECTS =====================

CREATE TABLE projects_project (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    slug              TEXT NOT NULL UNIQUE,
    title             TEXT NOT NULL,
    blurb             TEXT NOT NULL,
    image_url         TEXT NOT NULL DEFAULT '',
    cta_label         TEXT NOT NULL DEFAULT '',
    cta_href          TEXT NOT NULL DEFAULT '',
    status            TEXT NOT NULL DEFAULT 'draft'
                      CHECK (status IN ('draft','in_review','approved','published','unpublished')),
    created_by_id     INTEGER NOT NULL REFERENCES users_user(id) ON DELETE RESTRICT,
    reviewed_by_id    INTEGER REFERENCES users_user(id) ON DELETE SET NULL,
    created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ===================== MODULE B — Publications =====================

CREATE TABLE publications_publication (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    slug              TEXT NOT NULL UNIQUE,
    title             TEXT NOT NULL,
    abstract          TEXT NOT NULL,
    format            TEXT NOT NULL
                      CHECK (format IN ('report','working_paper','data_story','brief','explainer','infographic','video')),
    theme_id          INTEGER NOT NULL REFERENCES taxonomy_theme(id) ON DELETE RESTRICT,
    language          TEXT NOT NULL DEFAULT 'en' CHECK (language IN ('en','ml')),
    "date"            TEXT NOT NULL,
    external_id       TEXT NOT NULL DEFAULT '',
    visibility        TEXT NOT NULL DEFAULT 'public' CHECK (visibility IN ('public','private')),
    tags              TEXT NOT NULL DEFAULT '[]',   -- JSON array, e.g. ["education","policy"]
    views             INTEGER NOT NULL DEFAULT 0,
    cover_url         TEXT NOT NULL DEFAULT '',
    status            TEXT NOT NULL DEFAULT 'draft'
                      CHECK (status IN ('draft','in_review','approved','published','unpublished')),
    created_by_id     INTEGER NOT NULL REFERENCES users_user(id) ON DELETE RESTRICT,
    reviewed_by_id    INTEGER REFERENCES users_user(id) ON DELETE SET NULL,
    created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE publications_publication_authors (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    publication_id      INTEGER NOT NULL REFERENCES publications_publication(id) ON DELETE CASCADE,
    personprofile_id    INTEGER NOT NULL REFERENCES content_personprofile(id) ON DELETE CASCADE,
    UNIQUE (publication_id, personprofile_id)
);

CREATE TABLE publications_publicationversion (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    publication_id    INTEGER NOT NULL REFERENCES publications_publication(id) ON DELETE CASCADE,
    version_number    INTEGER NOT NULL,
    file              TEXT NOT NULL,
    uploaded_by_id    INTEGER NOT NULL REFERENCES users_user(id) ON DELETE RESTRICT,
    is_current        BOOLEAN NOT NULL DEFAULT 1,
    created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (publication_id, version_number)
);

CREATE TABLE publications_publication_block (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    publication_id    INTEGER NOT NULL REFERENCES publications_publication(id) ON DELETE CASCADE,
    "order"           INTEGER NOT NULL DEFAULT 0,
    block_type        TEXT NOT NULL
                      CHECK (block_type IN ('heading','subheading','paragraph','image','quote')),
    text              TEXT,
    image_url         TEXT,
    image_caption     TEXT
);

CREATE TABLE publications_publication_source (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    publication_id    INTEGER NOT NULL REFERENCES publications_publication(id) ON DELETE CASCADE,
    "order"           INTEGER NOT NULL DEFAULT 0,
    citation_text     TEXT NOT NULL,
    url               TEXT
);

CREATE TABLE publications_datastory (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    publication_id    INTEGER NOT NULL UNIQUE REFERENCES publications_publication(id) ON DELETE CASCADE,
    area_label        TEXT NOT NULL DEFAULT '',
    hook_note         TEXT NOT NULL DEFAULT '',
    lede              TEXT NOT NULL DEFAULT '',
    why_it_matters    TEXT NOT NULL DEFAULT ''
);

CREATE TABLE publications_datastory_stat (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    datastory_id   INTEGER NOT NULL REFERENCES publications_datastory(id) ON DELETE CASCADE,
    "order"        INTEGER NOT NULL DEFAULT 0,
    kind           TEXT NOT NULL CHECK (kind IN ('hook','callout')),
    value          TEXT NOT NULL,
    label          TEXT NOT NULL,
    sub            TEXT,
    tone           TEXT
);

CREATE TABLE publications_datastory_chart (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    datastory_id   INTEGER NOT NULL REFERENCES publications_datastory(id) ON DELETE CASCADE,
    "order"        INTEGER NOT NULL DEFAULT 0,
    block_id       INTEGER REFERENCES publications_publication_block(id) ON DELETE SET NULL,
    chart_type     TEXT NOT NULL CHECK (chart_type IN ('bar','scatter','line','map')),
    title          TEXT NOT NULL,
    data           TEXT NOT NULL DEFAULT '{}',
    x_label        TEXT NOT NULL DEFAULT '',
    y_label        TEXT NOT NULL DEFAULT '',
    note           TEXT NOT NULL DEFAULT ''
);

-- ===================== MODULE C — Data Repository =====================

CREATE TABLE datarepo_dataset (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    slug              TEXT NOT NULL UNIQUE,
    title             TEXT NOT NULL,
    description       TEXT NOT NULL DEFAULT '',
    file              TEXT NOT NULL,
    format            TEXT NOT NULL CHECK (format IN ('csv','parquet','zip')),
    theme_id          INTEGER NOT NULL REFERENCES taxonomy_theme(id) ON DELETE RESTRICT,
    geography         TEXT NOT NULL DEFAULT '',
    "year"            INTEGER,
    source            TEXT NOT NULL DEFAULT '',
    update_frequency  TEXT NOT NULL DEFAULT '',
    tags              TEXT NOT NULL DEFAULT '[]',
    coverage          TEXT NOT NULL DEFAULT '',
    last_updated      TEXT,
    file_size         INTEGER,
    download_count    INTEGER NOT NULL DEFAULT 0,
    "type"            TEXT NOT NULL DEFAULT '',
    visibility        TEXT NOT NULL DEFAULT 'internal_only'
                      CHECK (visibility IN ('public','on_request','internal_only')),
    status            TEXT NOT NULL DEFAULT 'draft'
                      CHECK (status IN ('draft','in_review','approved','published','unpublished')),
    created_by_id     INTEGER NOT NULL REFERENCES users_user(id) ON DELETE RESTRICT,
    reviewed_by_id    INTEGER REFERENCES users_user(id) ON DELETE SET NULL,
    created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE datarepo_dashboard (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    slug              TEXT NOT NULL UNIQUE,
    title             TEXT NOT NULL,
    description       TEXT NOT NULL DEFAULT '',
    embed_url         TEXT NOT NULL,
    embed_type        TEXT NOT NULL CHECK (embed_type IN ('datawrapper','tableau','d3')),
    theme_id          INTEGER NOT NULL REFERENCES taxonomy_theme(id) ON DELETE RESTRICT,
    geography         TEXT NOT NULL DEFAULT '',
    "year"            INTEGER,
    "type"            TEXT NOT NULL DEFAULT '',
    status            TEXT NOT NULL DEFAULT 'draft'
                      CHECK (status IN ('draft','in_review','approved','published','unpublished')),
    created_by_id     INTEGER NOT NULL REFERENCES users_user(id) ON DELETE RESTRICT,
    reviewed_by_id    INTEGER REFERENCES users_user(id) ON DELETE SET NULL,
    created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE datarepo_dashboard_datasets (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    dashboard_id  INTEGER NOT NULL REFERENCES datarepo_dashboard(id) ON DELETE CASCADE,
    dataset_id    INTEGER NOT NULL REFERENCES datarepo_dataset(id) ON DELETE CASCADE,
    UNIQUE (dashboard_id, dataset_id)
);

CREATE TABLE datarepo_accessrequest (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER NOT NULL REFERENCES users_user(id) ON DELETE CASCADE,
    dataset_id        INTEGER NOT NULL REFERENCES datarepo_dataset(id) ON DELETE CASCADE,
    status            TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','denied')),
    requested_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_at       TEXT,
    reviewed_by_id    INTEGER REFERENCES users_user(id) ON DELETE SET NULL,
    UNIQUE (user_id, dataset_id)
);

CREATE TABLE datarepo_accessgroup (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    slug          TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE datarepo_accessgroup_member (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id      INTEGER NOT NULL REFERENCES datarepo_accessgroup(id) ON DELETE CASCADE,
    user_id       INTEGER NOT NULL REFERENCES users_user(id) ON DELETE CASCADE,
    added_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    added_by_id   INTEGER REFERENCES users_user(id) ON DELETE SET NULL,
    UNIQUE (group_id, user_id)
);

CREATE TABLE datarepo_accessgroup_grant (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id        INTEGER NOT NULL REFERENCES datarepo_accessgroup(id) ON DELETE CASCADE,
    dataset_id      INTEGER NOT NULL REFERENCES datarepo_dataset(id) ON DELETE CASCADE,
    granted_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    granted_by_id   INTEGER REFERENCES users_user(id) ON DELETE SET NULL,
    expires_at      TEXT,
    UNIQUE (group_id, dataset_id)
);

CREATE TABLE datarepo_downloadlog (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER REFERENCES users_user(id) ON DELETE SET NULL,
    dataset_id      INTEGER NOT NULL REFERENCES datarepo_dataset(id) ON DELETE CASCADE,
    downloaded_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ip              TEXT
);

CREATE TABLE datarepo_favorite (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users_user(id) ON DELETE CASCADE,
    dataset_id    INTEGER NOT NULL REFERENCES datarepo_dataset(id) ON DELETE CASCADE,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, dataset_id)
);

-- ===================== MODULE D — Fellowship =====================

CREATE TABLE fellowship_program (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    slug          TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    start_date    TEXT,
    end_date      TEXT,
    is_active     BOOLEAN NOT NULL DEFAULT 1
);

CREATE TABLE fellowship_programtimelinestage (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id    INTEGER NOT NULL REFERENCES fellowship_program(id) ON DELETE CASCADE,
    "order"       INTEGER NOT NULL DEFAULT 0,
    stage_label   TEXT NOT NULL,
    stage_date    TEXT
);

CREATE TABLE fellowship_applicationform (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id    INTEGER NOT NULL REFERENCES fellowship_program(id) ON DELETE CASCADE,
    field_schema  TEXT NOT NULL,
    "version"     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE fellowship_application (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id             INTEGER NOT NULL REFERENCES fellowship_program(id) ON DELETE RESTRICT,
    applicant_name         TEXT NOT NULL,
    applicant_email        TEXT NOT NULL,
    applicant_phone        TEXT NOT NULL DEFAULT '',
    applicant_user_id      INTEGER REFERENCES users_user(id) ON DELETE SET NULL,
    intake_channel         TEXT
                           CHECK (intake_channel IN ('fellowship_portal','get_involved_form')),
    answers                TEXT NOT NULL DEFAULT '{}',
    status                 TEXT NOT NULL DEFAULT 'submitted'
                           CHECK (status IN ('submitted','under_review','shortlisted','rejected','accepted','onboarded')),
    onboarded_profile_id   INTEGER REFERENCES content_personprofile(id) ON DELETE SET NULL,
    submitted_at           TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at             TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE fellowship_applicationdocument (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id    INTEGER NOT NULL REFERENCES fellowship_application(id) ON DELETE CASCADE,
    label             TEXT NOT NULL,
    file              TEXT NOT NULL,
    uploaded_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE fellowship_review (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id    INTEGER NOT NULL REFERENCES fellowship_application(id) ON DELETE CASCADE,
    reviewer_id       INTEGER NOT NULL REFERENCES users_user(id) ON DELETE RESTRICT,
    score             INTEGER,
    notes             TEXT NOT NULL DEFAULT '',
    created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE fellowship_programreviewer (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users_user(id) ON DELETE CASCADE,
    program_id    INTEGER NOT NULL REFERENCES fellowship_program(id) ON DELETE CASCADE,
    assigned_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, program_id)
);

-- ===================== MODULE E — Media Watch =====================

CREATE TABLE mediawatch_mediacase (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    item_type         TEXT NOT NULL CHECK (item_type IN ('image','text','video')),
    item_file         TEXT NOT NULL DEFAULT '',
    headline_text     TEXT NOT NULL DEFAULT '',
    note              TEXT NOT NULL DEFAULT '',
    classification    TEXT NOT NULL DEFAULT ''
                      CHECK (classification IN ('', 'hate_speech','misinformation','communal_bias','other')),
    theme_id          INTEGER REFERENCES taxonomy_theme(id) ON DELETE SET NULL,
    source            TEXT NOT NULL DEFAULT '',
    status            TEXT NOT NULL DEFAULT 'flagged'
                      CHECK (status IN ('flagged','under_review','confirmed','public')),
    flagged_by_id     INTEGER NOT NULL REFERENCES users_user(id) ON DELETE RESTRICT,
    flagged_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_by_id    INTEGER REFERENCES users_user(id) ON DELETE SET NULL,
    reviewed_at       TEXT
);

CREATE TABLE mediawatch_response (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id           INTEGER NOT NULL REFERENCES mediawatch_mediacase(id) ON DELETE CASCADE,
    "type"            TEXT NOT NULL
                      CHECK ("type" IN ('rebuttal','op_ed','explainer','press_statement','toolkit')),
    body              TEXT NOT NULL DEFAULT '',
    published_by_id   INTEGER NOT NULL REFERENCES users_user(id) ON DELETE RESTRICT,
    published_at      TEXT
);

CREATE TABLE mediawatch_response_attachment (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    response_id   INTEGER NOT NULL REFERENCES mediawatch_response(id) ON DELETE CASCADE,
    file          TEXT NOT NULL,
    label         TEXT NOT NULL DEFAULT ''
);

-- ===================== MODULE F — Donors =====================

CREATE TABLE donors_donor (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL UNIQUE REFERENCES users_user(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    phone         TEXT NOT NULL DEFAULT '',
    address       TEXT NOT NULL DEFAULT ''
);

CREATE TABLE donors_campaign (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    slug          TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    goal_amount   NUMERIC NOT NULL,
    start_date    TEXT,
    end_date      TEXT,
    is_active     BOOLEAN NOT NULL DEFAULT 1
);

CREATE TABLE donors_donationtier (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    label               TEXT NOT NULL,
    suggested_amount    NUMERIC NOT NULL,
    is_active           BOOLEAN NOT NULL DEFAULT 1
);

CREATE TABLE donors_donation (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    donor_id               INTEGER NOT NULL REFERENCES donors_donor(id) ON DELETE RESTRICT,
    campaign_id            INTEGER REFERENCES donors_campaign(id) ON DELETE SET NULL,
    tier_id                INTEGER REFERENCES donors_donationtier(id) ON DELETE SET NULL,
    amount                 NUMERIC NOT NULL,
    currency               TEXT NOT NULL DEFAULT 'INR',
    payment_gateway        TEXT NOT NULL CHECK (payment_gateway IN ('razorpay','instamojo')),
    payment_gateway_ref    TEXT NOT NULL DEFAULT '',
    status                 TEXT NOT NULL DEFAULT 'pending'
                           CHECK (status IN ('pending','succeeded','failed')),
    created_at             TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at             TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE donors_taxreceipt (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    donation_id       INTEGER NOT NULL UNIQUE REFERENCES donors_donation(id) ON DELETE CASCADE,
    receipt_number    TEXT NOT NULL UNIQUE,
    file              TEXT NOT NULL,
    generated_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE donors_webhookevent (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    gateway        TEXT NOT NULL CHECK (gateway IN ('razorpay','instamojo')),
    event_type     TEXT NOT NULL,
    raw_payload    TEXT NOT NULL,
    received_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed_at   TEXT,
    donation_id    INTEGER REFERENCES donors_donation(id) ON DELETE SET NULL,
    result         TEXT NOT NULL DEFAULT ''
);

-- ===================== MODULE G — Forms =====================

CREATE TABLE forms_formdefinition (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    slug                TEXT NOT NULL UNIQUE,
    name                TEXT NOT NULL,
    field_schema        TEXT NOT NULL,
    routing_rule        TEXT NOT NULL DEFAULT '{}',
    crm_sync_enabled    BOOLEAN NOT NULL DEFAULT 0,
    anonymous_allowed   BOOLEAN NOT NULL DEFAULT 0,
    created_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE forms_formsubmission (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    form_id           INTEGER NOT NULL REFERENCES forms_formdefinition(id) ON DELETE CASCADE,
    data              TEXT NOT NULL,
    is_anonymous      BOOLEAN NOT NULL DEFAULT 0,
    submitter_name    TEXT,
    submitter_email   TEXT,
    submitter_ip      TEXT,
    submitted_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def seed(conn: sqlite3.Connection) -> None:
    """
    Sample data grounded in the actual PRI prototype content where it exists
    (app/_content/*.ts in the frontend repo: real team roster, executive
    council, patrons, partners, the "Kerala in Data" publication series, and
    org mission/vision copy) — clearly marked below wherever a row extends
    beyond what the prototype currently has, so this stays legible as sample
    data rather than being mistaken for real PRI records.

    Every enum-constrained column (see the CHECK constraints in SCHEMA above)
    has at least one row covering each of its allowed values — verified by
    check_enum_coverage() in main().
    """
    cur = conn.cursor()

    def insert(table: str, **cols) -> int:
        keys = ", ".join(f'"{k}"' for k in cols)
        placeholders = ", ".join("?" for _ in cols)
        cur.execute(f"INSERT INTO {table} ({keys}) VALUES ({placeholders})", list(cols.values()))
        return cur.lastrowid

    # =================================================================
    # SHARED TAXONOMY — taxonomy_theme (canonical 8 values, confirmed on the live
    # site's Research/Data/submission-form filters)
    # =================================================================
    theme_names = ["Education", "Employment", "Economics", "Public Finance",
                   "Health", "Governance", "Demography", "Migration"]
    theme_id_by_name: dict[str, int] = {}
    for name in theme_names:
        slug = name.lower().replace(" ", "-")
        theme_id_by_name[name] = insert("taxonomy_theme", slug=slug, name=name)

    # =================================================================
    # core_sitesettings — singleton (org profile, from the live site's footer/about page)
    # =================================================================
    insert("core_sitesettings", id=1, org_name="Policy and Research Initiative", tagline="PRI",
           registration_number="MPM/CA/204/2025", cert_12a="AAOAP9667ME20251", cert_80g="AAOAP9667MF20251",
           primary_email="contact@priresearch.in", primary_phone="+91 96052 21921",
           bank_account_name="To be confirmed", bank_account_number="To be confirmed",
           bank_ifsc="To be confirmed", bank_name_branch="To be confirmed",
           social_linkedin="https://www.linkedin.com/company/priresearch", social_facebook="",
           social_twitter="", social_instagram="")

    # =================================================================
    # CORE — users_user (role: public | researcher | editor | fellow | admin)
    # =================================================================
    # Real PRI team members (app/_content/people.ts) mapped onto site roles by
    # job function. Donors are invented — the prototype's donate.ts has no
    # real donor data yet (payment gateway/bank details are still placeholders).
    noushad = insert("users_user", username="noushad.t", email="noushad@priresearch.in", role="admin",
                      first_name="Noushad", last_name="T", is_staff=1, is_superuser=1)
    sinan = insert("users_user", username="muhammed.sinan", email="sinan@priresearch.in", role="admin",
                    first_name="Muhammed", last_name="Sinan", is_staff=1)
    hashir = insert("users_user", username="sayyid.hashir", email="hashir@priresearch.in", role="editor",
                     first_name="Sayyid", last_name="Hashir", is_staff=1)
    badusha = insert("users_user", username="badusha", email="badusha@priresearch.in", role="editor",
                      first_name="Badusha", last_name="", is_staff=1)
    afsal = insert("users_user", username="afsal.k", email="afsal@priresearch.in", role="researcher",
                    first_name="Afsal", last_name="K")
    thufail = insert("users_user", username="muhammed.thufail", email="thufail@priresearch.in", role="researcher",
                      first_name="Muhammed", last_name="Thufail")
    rashiq = insert("users_user", username="rashiq", email="rashiq@priresearch.in", role="researcher",
                     first_name="Rashiq", last_name="")
    fellow_hisham_user = insert("users_user", username="hisham", email="hisham@priresearch.in", role="fellow",
                                 first_name="Hisham", last_name="")
    donor1 = insert("users_user", username="fathima.k", email="fathima.k@example.com", role="public",
                     first_name="Fathima", last_name="K")
    donor2 = insert("users_user", username="arjun.menon", email="arjun.menon@example.com", role="public",
                     first_name="Arjun", last_name="Menon")
    donor3 = insert("users_user", username="sreelakshmi.p", email="sreelakshmi.p@example.com", role="public",
                     first_name="Sreelakshmi", last_name="Pillai")

    # =================================================================
    # MODULE A — content_personprofile
    # (group: team | patron | advisory | executive | fellow | past-fellow | author | partner)
    # =================================================================
    def profile(slug, name, role_title, group, status, created_by, reviewed_by=None, bio=""):
        return insert("content_personprofile", slug=slug, name=name, role_title=role_title, group=group,
                       bio=bio, status=status, created_by_id=created_by, reviewed_by_id=reviewed_by)

    # -- Our Team (7, real, all published — matches the live /people/team page)
    p_noushad = profile("noushad", "Dr. Noushad T", "Director of Operations", "team", "published", hashir, noushad)
    p_thufail = profile("thufail", "Muhammed Thufail", "Head of Data", "team", "published", hashir, noushad)
    p_afsal = profile("afsal", "Dr. Afsal K", "Researcher", "team", "published", hashir, noushad)
    p_hashir = profile("sayyid-hashir", "Sayyid Hashir", "Editor", "team", "published", noushad, noushad)
    p_badusha = profile("badusha", "Badusha", "Content Writer", "team", "published", hashir, noushad)
    p_sinan = profile("muhammed-sinan", "Muhammed Sinan", "Web Manager", "team", "published", hashir, noushad)
    p_rashiq = profile("rashiq", "Rashiq", "Data Analyst", "team", "published", hashir, noushad)

    # -- Patrons (2, real, published)
    profile("pk-kunjalikkutty", "PK Kunjalikkutty", "Patron", "patron", "published", noushad, noushad)
    profile("galfar-mohammed-ali", "Galfar Mohammed Ali", "Patron", "patron", "published", noushad, noushad)

    # -- Advisory Body (2 of 10 real placeholder slots, mid-workflow — the
    # prototype is still waiting on PRI to supply real advisory names)
    profile("advisory-member-1", "Advisory Member 1", "Advisory Body", "advisory", "in_review", badusha)
    profile("advisory-member-2", "Advisory Member 2", "Advisory Body", "advisory", "draft", badusha)

    # -- Executive Council (5 of 13 real members)
    profile("sayyid-sadiq-ali-shihab", "Sayyid Sadiq Ali Shihab", "Chairman", "executive", "published", noushad, noushad)
    profile("ahmad-munavvar-puthiya-maliyekkal", "Ahmad Munavvar Puthiya Maliyekkal", "Vice Chairman", "executive",
            "published", noushad, noushad)
    profile("sayyid-rasheed-ali-puthiya-maliyekkal", "Sayyid Rasheed Ali Puthiya Maliyekkal", "Treasurer",
            "executive", "published", noushad, noushad)
    profile("mohammed-haris-kt", "Dr. Mohammed Haris KT", "General Secretary", "executive", "approved", noushad, noushad)
    # invented status variation: a past officer's profile pending archival, to
    # exercise the "unpublished" end state on a real name
    profile("abubakr-t", "Abubakr T", "Vice President (former)", "executive", "unpublished", noushad, noushad)

    # -- Authors (1, real — the collective research byline)
    p_research_team = profile("pri-research-team", "PRI Research Team", "Research Team", "author", "published",
                               hashir, noushad, bio="The collective byline for research produced across PRI's departments.")

    # -- Fellows (1 real active fellow)
    p_hisham = profile("hisham", "Hisham", "Research Fellow · Governance & Policy Analysis", "fellow", "published",
                        hashir, noushad, bio="Ph.D., Economics, IIT Delhi.")

    # -- Past Fellows (2, real placeholder slots)
    profile("past-fellow-one", "Past Fellow One", "Past Fellow · Demography & Health", "past-fellow", "unpublished", badusha)
    p_past_fellow_two = profile("past-fellow-two", "Past Fellow Two", "Past Fellow · Society Development",
                                 "past-fellow", "published", badusha, noushad)

    # -- Partners (3 real institutions, modeled as PersonProfile rows per the
    # existing `partner` group choice — mid-workflow to show the review pipeline)
    profile("safi-institute", "SAFI Group of Institutions", "Institutional Partner", "partner", "published", hashir, noushad)
    profile("ch-chair", "CH Mohammed Koya Chair for Studies on Developing Societies", "Institutional Partner",
            "partner", "in_review", hashir)
    profile("cse-hadia", "HADIA Centre for Social Excellence", "Institutional Partner", "partner", "draft", hashir)

    # =================================================================
    # content_event (event_type: webinar|launch|workshop|advocacy_day|roundtable)
    # =================================================================
    insert("content_event", slug="policy-roundtable-2026", title="Policy roundtable with stakeholders",
           description="A roundtable convening policymakers and researchers on district education budgets.",
           event_type="roundtable", starts_at="2026-11-10 10:00:00", venue="Kozhikode", status="published",
           created_by_id=badusha, reviewed_by_id=hashir)
    insert("content_event", slug="capacity-building-workshop-2026", title="Capacity-building workshop",
           description="A workshop for district officers on using PRI's education datasets.",
           event_type="workshop", starts_at="2026-11-24 09:30:00", venue="Malappuram", status="published",
           created_by_id=badusha, reviewed_by_id=hashir)
    insert("content_event", slug="kerala-in-data-launch-2026", title="Research launch: Kerala in Data series",
           description="Public launch event for the Kerala in Data publication series.",
           event_type="launch", starts_at="2026-01-15 11:00:00", venue="Thiruvananthapuram", status="approved",
           created_by_id=badusha, reviewed_by_id=noushad)
    insert("content_event", slug="district-budgets-webinar-2026", title="Webinar: Understanding District Education Budgets",
           description="An online session walking through the education-budget working paper.",
           event_type="webinar", starts_at="2026-12-05 16:00:00", is_virtual=1, status="in_review",
           created_by_id=badusha)
    insert("content_event", slug="scheme-accessibility-advocacy-day-2026", title="Advocacy Day: Welfare Scheme Accessibility",
           description="Advocacy day drafted around welfare-scheme uptake findings.",
           event_type="advocacy_day", starts_at="2027-01-20 09:00:00", venue="Kochi", status="draft",
           created_by_id=badusha)
    insert("content_event", slug="fieldwork-debrief-roundtable-2025", title="Fieldwork Debrief Roundtable (2025, archived)",
           description="Internal roundtable debriefing 2025 fieldwork, since archived.",
           event_type="roundtable", starts_at="2025-12-01 10:00:00", ends_at="2025-12-01 13:00:00",
           venue="Malappuram", status="unpublished", created_by_id=badusha, reviewed_by_id=hashir)

    # =================================================================
    # content_joblisting
    # =================================================================
    insert("content_joblisting", slug="research-associate-education-policy",
           title="Research Associate — Education Policy", location="Malappuram, Kerala",
           employment_type="Full-time", status="published", created_by_id=hashir, reviewed_by_id=noushad)
    insert("content_joblisting", slug="communications-intern", title="Communications Intern",
           location="Malappuram, Kerala", employment_type="Internship", status="in_review",
           created_by_id=hashir)
    insert("content_joblisting", slug="data-analyst", title="Data Analyst", location="Remote (Kerala)",
           employment_type="Full-time", status="approved", created_by_id=hashir, reviewed_by_id=noushad)
    insert("content_joblisting", slug="programme-coordinator-fellowship", title="Programme Coordinator, Fellowship",
           location="Malappuram, Kerala", employment_type="Contract", status="draft", created_by_id=hashir)
    insert("content_joblisting", slug="field-research-assistant-2025", title="Field Research Assistant (2025 cohort, closed)",
           location="Malappuram, Kerala", employment_type="Contract", closes_at="2025-12-31", status="unpublished",
           created_by_id=hashir, reviewed_by_id=noushad)

    # =================================================================
    # content_partner (partner_type: institutional|consortium) — organizations,
    # distinct from content_personprofile's individual 'partner' group rows above
    # =================================================================
    insert("content_partner", slug="safi-group", name="SAFI Group of Institutions", partner_type="institutional",
           status="published", created_by_id=hashir, reviewed_by_id=noushad)
    insert("content_partner", slug="ch-chair-org", name="CH Mohammed Koya Chair for Studies on Developing Societies",
           partner_type="institutional", status="in_review", created_by_id=hashir)
    insert("content_partner", slug="hadia-centre", name="HADIA Centre for Social Excellence",
           partner_type="institutional", status="draft", created_by_id=hashir)
    insert("content_partner", slug="kerala-policy-research-consortium", name="Kerala Policy Research Consortium",
           partner_type="consortium", status="approved", created_by_id=hashir, reviewed_by_id=noushad)
    insert("content_partner", slug="malabar-development-alliance", name="Malabar Development Alliance",
           partner_type="consortium", status="unpublished", created_by_id=hashir, reviewed_by_id=noushad)

    # =================================================================
    # content_namedprogram
    # =================================================================
    insert("content_namedprogram", slug="kerala-in-data-fellowship", name="Kerala in Data Fellowship Programme",
           funder_credit="Supported by PRI's core research fund", status="published",
           created_by_id=hashir, reviewed_by_id=noushad)
    insert("content_namedprogram", slug="district-education-budget-tracker", name="District Education Budget Tracker",
           status="in_review", created_by_id=hashir)
    insert("content_namedprogram", slug="migration-diaspora-research-initiative", name="Migration & Diaspora Research Initiative",
           status="approved", created_by_id=hashir, reviewed_by_id=noushad)
    insert("content_namedprogram", slug="community-health-data-corps", name="Community Health Data Corps",
           status="draft", created_by_id=hashir)
    insert("content_namedprogram", slug="legacy-employment-survey-programme", name="Legacy Employment Survey Programme (2019, concluded)",
           status="unpublished", created_by_id=hashir, reviewed_by_id=noushad)

    # =================================================================
    # content_album / content_galleryphoto
    # =================================================================
    album_launch = insert("content_album", slug="research-launch-2026", title="Research Launch Event 2026")
    insert("content_galleryphoto", album_id=album_launch, order=0, image_url="gallery/launch-2026-01.jpg",
           caption="Opening remarks at the Kerala in Data launch.")
    insert("content_galleryphoto", album_id=album_launch, order=1, image_url="gallery/launch-2026-02.jpg",
           caption="Panel discussion with district officials.")
    insert("content_galleryphoto", album_id=album_launch, order=2, image_url="gallery/launch-2026-03.jpg",
           caption="Audience Q&A session.")
    album_fieldwork = insert("content_album", slug="fieldwork-malappuram", title="Fieldwork in Malappuram")
    insert("content_galleryphoto", album_id=album_fieldwork, order=0, image_url="gallery/fieldwork-01.jpg",
           caption="Enumerators conducting a school survey.")
    insert("content_galleryphoto", album_id=album_fieldwork, order=1, image_url="gallery/fieldwork-02.jpg",
           caption="District data collection team.")

    # =================================================================
    # content_office
    # =================================================================
    insert("content_office", name="PRI Head Office",
           address="West Kodur, Kodur PO, Malappuram Dt, Kerala, India 676504",
           phone="+91 96052 21921", email="contact@priresearch.in", is_primary=1)
    insert("content_office", name="PRI Regional Liaison Office, Kochi",
           address="Kochi, Kerala, India", is_primary=0)

    # =================================================================
    # content_department / content_departmentarea — real 5 research wings,
    # verified from the live /about page
    # =================================================================
    def department(slug, name, order, areas):
        dept_id = insert("content_department", slug=slug, name=name, order=order)
        for i, area in enumerate(areas):
            insert("content_departmentarea", department_id=dept_id, order=i, name=area)
        return dept_id

    department("human-capital-development", "Center for Human Capital Development", 1, [
        "Educational Statistics", "Occupational and Employment Patterns",
        "Skill Development and Capacity Building", "Accessibility and Opportunities",
    ])
    department("economic-analysis", "Center for Economic Analysis", 2, [
        "Wealth and Income Distribution", "Market Participation and Ownership Patterns",
        "Budget Allocation and Expenditure", "Agriculture and Industry",
        "Public Infrastructure", "Environment and Resilience",
    ])
    department("society-development", "Department of Society Development", 3, [
        "Organizations and Community Institutions", "Philanthropic and Welfare Activities",
        "Inter-religious Harmony", "Resource Allocation and Optimization",
    ])
    department("governance-policy-analysis", "Center for Governance and Policy Analysis", 4, [
        "Public Policy Analysis", "Political Participation and Legislative Representation",
        "Schemes and Programmes",
    ])
    department("demography-health-research", "Demography & Health Research Unit", 5, [
        "Demography and Population Studies", "Migration and Remittances",
        "Healthcare Accessibility and Delivery",
    ])

    # =================================================================
    # accounts_auditlog — spans every module, several actors
    # =================================================================
    def audit(actor, module, action, target, **meta):
        insert("accounts_auditlog", actor_id=actor, module=module, action=action, target=target,
               metadata=json.dumps(meta) if meta else "{}")

    audit(noushad, "content", "status_transition", "ContentBlock:homepage-hero", **{"from": "in_review", "to": "published"})
    audit(hashir, "content", "status_transition", "PersonProfile:mohammed-haris-kt", **{"from": "in_review", "to": "approved"})
    audit(noushad, "content", "status_transition", "PersonProfile:abubakr-t", **{"from": "published", "to": "unpublished"})
    audit(hashir, "publications", "status_transition", "Publication:education-budget-working-paper",
          **{"from": "draft", "to": "in_review"})
    audit(noushad, "datarepo", "status_transition", "AccessRequest:1", decision="approved")
    audit(noushad, "datarepo", "status_transition", "AccessRequest:3", decision="denied")
    audit(hashir, "fellowship", "status_transition", "Application:2", **{"from": "submitted", "to": "under_review"})
    audit(noushad, "fellowship", "status_transition", "Application:1", **{"from": "accepted", "to": "onboarded"})
    audit(hashir, "mediawatch", "status_transition", "MediaCase:2", **{"from": "under_review", "to": "confirmed"})
    audit(hashir, "mediawatch", "status_transition", "MediaCase:1", **{"from": "confirmed", "to": "public"})
    audit(None, "donors", "webhook_received", "Donation:1", gateway="razorpay", result="succeeded")
    audit(None, "donors", "webhook_received", "Donation:3", gateway="razorpay", result="failed")
    audit(noushad, "accounts", "role_grant", "User:muhammed.sinan", **{"from": "editor", "to": "admin"})
    audit(hashir, "forms", "crm_sync", "FormSubmission:1", crm="airtable", result="ok")

    # =================================================================
    # accounts_apikey / accounts_notificationlog
    # =================================================================
    insert("accounts_apikey", user_id=afsal, key="pri_live_afsal000000000000000000000000")
    insert("accounts_apikey", user_id=thufail, key="pri_live_thufail0000000000000000000000",
           last_regenerated_at="2026-08-01 09:00:00")
    insert("accounts_apikey", user_id=donor1, key="pri_live_revoked000000000000000000000",
           revoked_at="2026-07-15 12:00:00")

    insert("accounts_notificationlog", recipient_user_id=None, recipient_email="aisha.rahman@example.com",
           template_key="fellowship_status_change", related_module="fellowship", related_object="Application:2",
           status="queued")
    insert("accounts_notificationlog", recipient_user_id=donor1, recipient_email="fathima.k@example.com",
           template_key="donation_receipt", related_module="donors", related_object="Donation:1",
           status="sent", sent_at="2026-04-01 10:05:00")
    insert("accounts_notificationlog", recipient_user_id=hashir, recipient_email="hashir@priresearch.in",
           template_key="mediacase_status_alert", related_module="mediawatch", related_object="MediaCase:2",
           status="failed")

    # =================================================================
    # MODULE A — content_contentblock / testimonial / document
    # (status: draft | in_review | approved | published | unpublished)
    # =================================================================
    insert("content_contentblock", slug="homepage-hero", title="Driving Inclusive Development",
           body="A dedicated think tank committed to promoting inclusive development, social justice, and "
                "national integration through data-driven research and evidence-based policy advocacy.",
           status="published", created_by_id=hashir, reviewed_by_id=noushad)
    insert("content_contentblock", slug="homepage-intro", title="Who we bring together",
           body="PRI brings together researchers, policymakers, community leaders, and civil society "
                "representatives to address socio-economic and political disparities, ensuring equal "
                "opportunities and fair representation.",
           status="published", created_by_id=hashir, reviewed_by_id=noushad)
    insert("content_contentblock", slug="directors-note", title="Director's Note",
           body="Good policy begins with an honest look at the data — including when it complicates the "
                "story we would rather tell. Protecting that discipline is what PRI exists to do.",
           status="draft", created_by_id=hashir, reviewed_by_id=None)  # placeholder in the live site pending a named Director
    insert("content_contentblock", slug="mission-points", title="Our Mission",
           body="Conduct rigorous, data-driven research to identify systemic inequalities; develop "
                "evidence-based policy recommendations; engage in strategic advocacy; empower decision-makers "
                "and the public through knowledge sharing and capacity building.",
           status="in_review", created_by_id=badusha, reviewed_by_id=None)
    insert("content_contentblock", slug="vision-statement", title="Our Vision",
           body="To create a society where every individual has equitable access to opportunities and "
                "resources — an empowered society engaging actively in socio-economic and political processes.",
           status="approved", created_by_id=badusha, reviewed_by_id=hashir)
    insert("content_contentblock", slug="covid-operations-notice-2021", title="COVID-19 Operational Notice",
           body="Archived notice on modified office hours during the pandemic period.",
           status="unpublished", created_by_id=hashir, reviewed_by_id=noushad)

    # Testimonials — three are the site's real placeholder quotes (status kept
    # low in the workflow to mirror their "placeholder" flag in testimonials
    # ts); two are invented to cover the remaining published/unpublished states.
    insert("content_testimonial", slug="testimonial-editor-partner",
           quote="PRI's district-level evidence has become the first stop for our editorial team.",
           attribution="Name Surname", role="Editor, partner publication", status="draft",
           created_by_id=badusha, reviewed_by_id=None)
    insert("content_testimonial", slug="testimonial-former-fellow",
           quote="Working alongside PRI's research team taught me what it means to let the evidence lead.",
           attribution="Name Surname", role="Former Research Fellow", status="in_review",
           created_by_id=badusha, reviewed_by_id=None)
    insert("content_testimonial", slug="testimonial-ngo-director",
           quote="Few institutes make it this easy to trace a policy from the budget line to the ground.",
           attribution="Name Surname", role="Programme Director, partner NGO", status="approved",
           created_by_id=badusha, reviewed_by_id=hashir)
    insert("content_testimonial", slug="testimonial-education-officer",
           quote="PRI's data work shaped our district's education policy this year.",
           attribution="District Education Officer", role="Govt. Partner", status="published",
           created_by_id=badusha, reviewed_by_id=hashir)
    insert("content_testimonial", slug="testimonial-archived-2022",
           quote="An early supporter's quote, since retired from the homepage rotation.",
           attribution="Name Surname", role="Former Partner", status="unpublished",
           created_by_id=badusha, reviewed_by_id=hashir)

    # Documents — annual-report-2025-26 is the one real, published document
    # (app/_content/people.ts `reports`); the rest extend it across the
    # workflow and add document_type/year variety.
    doc_annual_report = insert("content_document", slug="annual-report-2025-26", title="Annual Report 2025–26",
           file="documents/annual-report-2025-26.pdf", description="PRI's annual report for FY 2025–26.",
           document_type="Annual Report", year=2026, status="published", created_by_id=hashir, reviewed_by_id=noushad)
    cur.execute("UPDATE content_event SET report_document_id = ? WHERE slug = ?",
                (doc_annual_report, "kerala-in-data-launch-2026"))
    cur.execute("UPDATE content_namedprogram SET linked_document_id = ? WHERE slug = ?",
                (doc_annual_report, "kerala-in-data-fellowship"))
    insert("content_document", slug="strategic-plan-2024-2028", title="Strategic Plan 2024–2028",
           file="documents/strategic-plan-2024-2028.pdf", description="PRI's four-year strategic plan.",
           document_type="Strategic Plan", year=2024, status="draft", created_by_id=hashir, reviewed_by_id=None)
    insert("content_document", slug="annual-report-2024-25", title="Annual Report 2024–25",
           file="documents/annual-report-2024-25.pdf", description="PRI's annual report for FY 2024–25.",
           document_type="Annual Report", year=2025, status="in_review", created_by_id=hashir, reviewed_by_id=None)
    insert("content_document", slug="annual-report-2023-24", title="Annual Report 2023–24",
           file="documents/annual-report-2023-24.pdf", description="PRI's annual report for FY 2023–24.",
           document_type="Annual Report", year=2024, status="approved", created_by_id=hashir, reviewed_by_id=noushad)
    insert("content_document", slug="financial-disclosure-2022", title="Financial Disclosure 2022",
           file="documents/financial-disclosure-2022.pdf", description="Superseded financial disclosure.",
           document_type="Financial Disclosure", year=2022, status="unpublished", created_by_id=hashir, reviewed_by_id=noushad)

    # =================================================================
    # PROJECTS — projects_project (from app/_content/projects.ts)
    # =================================================================
    insert("projects_project", slug="sir-project", title="SIR Project",
           blurb="Full project name and description to be confirmed.", status="draft",
           created_by_id=badusha, reviewed_by_id=None)
    insert("projects_project", slug="education", title="Education",
           blurb="Analysing educational access, quality, and outcomes across different communities and regions.",
           status="published", created_by_id=badusha, reviewed_by_id=hashir,
           cta_label="Explore project", cta_href="/projects/education")
    insert("projects_project", slug="demography-migration", title="Demography and Migration",
           blurb="Population studies, migration patterns, and diaspora community analysis.",
           status="published", created_by_id=badusha, reviewed_by_id=hashir,
           cta_label="Explore project", cta_href="/projects/demography-migration")
    insert("projects_project", slug="economic-analysis", title="Economic Analysis",
           blurb="Wealth and income distribution, market participation, and budget allocation research.",
           status="in_review", created_by_id=afsal, reviewed_by_id=None)
    insert("projects_project", slug="governance-policy", title="Governance and Policy",
           blurb="Public policy analysis, political participation, and legislative representation studies.",
           status="approved", created_by_id=afsal, reviewed_by_id=hashir)
    insert("projects_project", slug="pilot-project-2022", title="Community Infrastructure Pilot (2022)",
           blurb="An early pilot study, since superseded by the current project slate.", status="unpublished",
           created_by_id=afsal, reviewed_by_id=hashir)

    # =================================================================
    # MODULE B — publications
    # (format: report|working_paper|data_story|brief|explainer|infographic|video,
    #  language: en|ml, visibility: public|private)
    # =================================================================
    def publication(slug, title, abstract, fmt, theme, language, date, visibility, status,
                     authors, views=0, external_id="", reviewed_by=None):
        pub_id = insert("publications_publication", slug=slug, title=title, abstract=abstract, format=fmt,
                         theme_id=theme_id_by_name[theme], language=language, date=date, external_id=external_id or slug,
                         visibility=visibility, tags=json.dumps([theme.lower()]), views=views, status=status,
                         created_by_id=afsal, reviewed_by_id=reviewed_by)
        for author_id in authors:
            insert("publications_publication_authors", publication_id=pub_id, personprofile_id=author_id)
        return pub_id

    # -- Real "Kerala in Data" series (app/_content/publications.ts), all Data Story / English / public
    pub_malappuram = publication(
        "malappuram-classrooms", "Malappuram's Plus One classrooms are Kerala's most crowded",
        "The district enrolls more first-year higher-secondary students than anywhere else in the state — "
        "packed into the largest batches, with the least room in the science stream.",
        "data_story", "Education", "en", "2026-01-10", "public", "published", [p_research_team], views=1240,
        reviewed_by=hashir)
    pub_population = publication(
        "kerala-population-mix", "Kerala's religious population mix is shifting slowly",
        "Muslims' share of Kerala's population rose gradually between the 2011 Census and 2024 estimates, "
        "while births to Muslim families fell by more than a quarter over the same decade.",
        "data_story", "Demography", "en", "2026-01-24", "public", "published", [p_research_team], views=980,
        reviewed_by=hashir)
    pub_healthcare = publication(
        "kerala-healthcare-gap", "Where Kerala's healthcare capacity runs thin",
        "On primary care, hospital beds and doctors, Malappuram and Kozhikode carry close to double the "
        "load of the state average — and the gap shows up the same way on all three measures.",
        "data_story", "Health", "en", "2026-02-05", "public", "published", [p_research_team], views=860,
        reviewed_by=hashir)
    pub_migration = publication(
        "kerala-gulf-migration", "Kerala's migration economy runs through the Gulf",
        "Muslims make up under a third of Kerala's population but nearly 42% of its emigrants, and almost "
        "all of that emigration — 98.5% — goes to the Gulf.",
        "data_story", "Migration", "en", "2026-02-18", "public", "published", [p_research_team], views=640,
        reviewed_by=hashir)

    # -- Extensions beyond the prototype's current content, covering the
    # remaining formats/languages/visibility/status the PRD (Module B) specifies
    publication(
        "education-budget-working-paper", "District Education Budgets: A Working Paper",
        "Early findings on how district-level education budgets track enrolment growth.",
        "working_paper", "Education", "en", "2026-03-01", "public", "in_review", [p_afsal, p_research_team])
    publication(
        "malayalam-health-brief", "ആരോഗ്യ സഞ്ചിക ബ്രീഫ്",
        "A Malayalam-language brief summarizing the healthcare-capacity data story for a general readership.",
        "brief", "Health", "ml", "2026-02-20", "public", "approved", [p_thufail], reviewed_by=hashir)
    publication(
        "governance-schemes-explainer", "How Kerala's Welfare Schemes Actually Reach People",
        "An internal-review explainer draft on scheme uptake, not yet cleared for public release.",
        "explainer", "Governance", "en", "2026-03-10", "private", "draft", [p_research_team])
    publication(
        "public-finance-infographic-2026", "Kerala's Budget, Visualized",
        "A one-page infographic breaking down state budget allocation by department.",
        "infographic", "Public Finance", "en", "2026-01-30", "public", "published", [p_rashiq, p_research_team],
        views=410, reviewed_by=hashir)
    publication(
        "fieldwork-video-diaries", "Fieldwork Video Diaries: Season 1",
        "Early video diaries from PRI's district fieldwork, since superseded by newer footage.",
        "video", "Employment", "en", "2025-11-01", "private", "unpublished", [p_badusha], reviewed_by=hashir)
    pub_economic_report = publication(
        "economic-analysis-report-2025", "Wealth and Income Distribution in Kerala: 2025 Report",
        "A full-length report from the Center for Economic Analysis on wealth and income distribution.",
        "report", "Economics", "en", "2025-12-01", "public", "published", [p_afsal, p_thufail], views=305,
        external_id="10.5281/zenodo.987654", reviewed_by=hashir)

    # Versions — most publications have exactly one; a couple show real
    # version history to exercise `is_current`.
    for pub_id, n in [(pub_malappuram, 1), (pub_population, 1), (pub_migration, 1)]:
        insert("publications_publicationversion", publication_id=pub_id, version_number=1,
               file=f"publications/{pub_id}-v1.pdf", uploaded_by_id=afsal, is_current=1)
    insert("publications_publicationversion", publication_id=pub_economic_report, version_number=1,
           file="publications/economic-analysis-report-2025-v1.pdf", uploaded_by_id=afsal, is_current=0)
    insert("publications_publicationversion", publication_id=pub_economic_report, version_number=2,
           file="publications/economic-analysis-report-2025-v2.pdf", uploaded_by_id=thufail, is_current=0)
    insert("publications_publicationversion", publication_id=pub_economic_report, version_number=3,
           file="publications/economic-analysis-report-2025-v3-final.pdf", uploaded_by_id=thufail, is_current=1)

    # =================================================================
    # publications_publication_block / publication_source — generic body content
    # (block_type: heading|subheading|paragraph|image|quote), for ANY publication format.
    #
    # The 4 real "Kerala in Data" data stories below are transcribed directly from the live
    # site (pri-website-pink.vercel.app/research/<slug>) — headings, paragraphs, chart data
    # points, and source citations are the actual published content, not placeholders, so this
    # demonstrates exactly how a real data story maps onto publication_block/datastory_*.
    # =================================================================

    # ---- Malappuram's Plus One classrooms (pub_malappuram) ----
    blk_malappuram_h1 = insert("publications_publication_block", publication_id=pub_malappuram, order=0,
           block_type="heading", text="The most crowded classrooms in the state")
    insert("publications_publication_block", publication_id=pub_malappuram, order=1, block_type="paragraph",
           text="Malappuram enrolled 70,472 Plus One students across 1,080 batches in 2025 — an average of "
                "65 students per batch, the highest of any district and 11 above the all-Kerala average of 54. "
                "Wayanad (60) and Kasargode (60) are the next most crowded. Pathanamthitta (36), Idukki (43) "
                "and Kottayam (43) run the smallest batches in the state.")
    blk_malappuram_h2 = insert("publications_publication_block", publication_id=pub_malappuram, order=2,
           block_type="heading", text="Fewer options in the science stream")
    insert("publications_publication_block", publication_id=pub_malappuram, order=3, block_type="paragraph",
           text="Only 42% of Malappuram's Plus One batches are science batches — tied for the lowest share in "
                "Kerala with Kasargode (40%), against a statewide average of 51%. Kottayam has the most science "
                "capacity, at 63% of its batches, followed by Pathanamthitta at 58%.")
    insert("publications_publication_block", publication_id=pub_malappuram, order=4, block_type="heading",
           text="Why it's happening: crowding and stream access move together")
    insert("publications_publication_block", publication_id=pub_malappuram, order=5, block_type="paragraph",
           text="Plotting batch size against science-stream share across all 14 districts shows a clear pattern: "
                "the districts with the largest average batches — Malappuram, Wayanad, Kasargode — are also the "
                "districts with the smallest share of science batches. Districts with smaller, less-crowded "
                "batches, like Pathanamthitta and Kottayam, tend to offer proportionally more science seats.")
    insert("publications_publication_block", publication_id=pub_malappuram, order=6, block_type="quote",
           text="Districts with smaller, less-crowded batches, like Pathanamthitta and Kottayam, tend to offer "
                "proportionally more science seats — consistent with a simple capacity story: where the "
                "district hasn't been able to open enough batches to match demand, existing seats get "
                "stretched thinner and skew toward the lower-cost humanities and commerce streams.")
    blk_malappuram_h4 = insert("publications_publication_block", publication_id=pub_malappuram, order=7,
           block_type="heading", text="Where it's headed: Malappuram's seat demand, 2027–2036")
    insert("publications_publication_block", publication_id=pub_malappuram, order=8, block_type="paragraph",
           text="Using 2012–2027 birth records for the district, the projected number of Plus One aspirants in "
                "Malappuram is expected to ease only slightly over the coming decade — from 84,265 in 2027 to "
                "77,442 in 2036, an 8.1% decline. But the path isn't a straight line down: demand is projected "
                "to rise through the early 2030s, peaking at 86,106 in 2033, before falling toward 2036.")

    insert("publications_publication_source", publication_id=pub_malappuram, order=0,
           citation_text="Plus One seat and batch distribution by district, 2025 — batches, enrollment, share of "
                          "science batches, and students per batch. Kerala Economic Review 2025 (source PDF, p.21).")
    insert("publications_publication_source", publication_id=pub_malappuram, order=1,
           citation_text="Plus One seat requirement forecast for Malappuram, 2027–2036, based on 2012–2027 yearly "
                          "birth records for the district (source PDF, p.22). The source text describes the "
                          "projected range as \"between 84,000 and 77,000,\" though the year-by-year figures show "
                          "a peak of 86,106 in 2033 that exceeds the stated upper bound; both the stated range and "
                          "the full year-by-year series are shown here for transparency.")

    # ---- Kerala's religious population mix (pub_population) ----
    insert("publications_publication_block", publication_id=pub_population, order=0, block_type="heading",
           text="The share shift since 2011")
    insert("publications_publication_block", publication_id=pub_population, order=1, block_type="paragraph",
           text="The rise in Muslims' population share was mirrored mainly by a decline in Hindus' share "
                "(−2.7 percentage points) and, to a smaller extent, Christians' (−0.7 points). The 2024 figures "
                "are projections ahead of India's next Census, due in 2027; the 2011 figures are the last full "
                "Census count.")
    insert("publications_publication_block", publication_id=pub_population, order=2, block_type="heading",
           text="Why the share is still moving: age structure, not just recent growth")
    insert("publications_publication_block", publication_id=pub_population, order=3, block_type="paragraph",
           text="Population share doesn't just reflect this year's births — it reflects decades of past births "
                "working their way through the age pyramid. Kerala's 2024 age breakdown shows why the Muslim "
                "share has been rising even as recent births slow: Muslims make up 40.3% of Kerala's under-18 "
                "population but only 22.6% of its over-40 population. Hindus show the reverse pattern.")
    insert("publications_publication_block", publication_id=pub_population, order=4, block_type="heading",
           text="The leading indicator: births are falling fast")
    insert("publications_publication_block", publication_id=pub_population, order=5, block_type="paragraph",
           text="The number of births to Muslim families in Kerala fell from 218,437 in 2014 to 159,088 in "
                "2024 — a drop of 59,349 births, or 27%, in a decade. The source data attributes this to later "
                "marriage ages driving down fertility.")

    insert("publications_publication_source", publication_id=pub_population, order=0,
           citation_text="Share of Muslims, Hindus and Christians in Kerala's total population, 2011 (Census) and "
                          "2024 (estimated), including absolute Muslim population counts. Source PDF, p.9.")
    insert("publications_publication_source", publication_id=pub_population, order=1,
           citation_text="Share of each age bracket (under 18, 18–40, 40+) accounted for by each religious group, "
                          "Kerala, 2024. Source PDF, p.10.")
    insert("publications_publication_source", publication_id=pub_population, order=2,
           citation_text="Annual births to Kerala Muslim families, 2014 and 2024. Sources: Annual Vital Statistics "
                          "2006–2024, Census 2011, Voters List LSGD 2025. Source PDF, p.11.")
    insert("publications_publication_source", publication_id=pub_population, order=3,
           citation_text="\"Representation\" chart is a calculated difference between each group's age-bracket "
                          "share (p.10) and that same group's overall 2024 population share (p.9) — not a figure "
                          "stated directly in the source.")

    # ---- Where Kerala's healthcare capacity runs thin (pub_healthcare) ----
    insert("publications_publication_block", publication_id=pub_healthcare, order=0, block_type="heading",
           text="The clinic gap")
    insert("publications_publication_block", publication_id=pub_healthcare, order=1, block_type="paragraph",
           text="The Government of Kerala's own health policy sets a benchmark of one Primary Health Centre for "
                "every 3,000 people. Statewide, the actual figure is 36,303 people per PHC — over twelve times "
                "that target. Malappuram, the most populous district, is worst off at 47,051 per PHC; Kozhikode "
                "follows at 44,171. Pathanamthitta (23,046) and Idukki (23,654) carry roughly half the load.")
    insert("publications_publication_block", publication_id=pub_healthcare, order=2, block_type="heading",
           text="It's not just clinics")
    insert("publications_publication_block", publication_id=pub_healthcare, order=3, block_type="paragraph",
           text="Across Kerala, government hospitals average 928 people per bed. Malappuram again ranks worst, "
                "at 1,861 people per bed — almost exactly double the state average. Kozhikode is next at 1,204. "
                "Pathanamthitta has the lightest load in the state at 589 per bed, followed by Alappuzha at 632.")
    insert("publications_publication_block", publication_id=pub_healthcare, order=4, block_type="heading",
           text="And the same two districts fall behind on doctors, too")
    insert("publications_publication_block", publication_id=pub_healthcare, order=5, block_type="paragraph",
           text="Malappuram has the highest population-per-doctor ratio in the state at 7,437, with Kozhikode "
                "close behind at 7,245. Pathanamthitta has the lowest at 3,754 and Wayanad the second-lowest "
                "at 3,930.")
    insert("publications_publication_block", publication_id=pub_healthcare, order=6, block_type="heading",
           text="A structural gap, not a one-off")
    insert("publications_publication_block", publication_id=pub_healthcare, order=7, block_type="paragraph",
           text="Malappuram is the worst-performing district on all three measures; Pathanamthitta is the best "
                "or near-best on all three. That consistency across independently reported indicators suggests a "
                "structural shortfall in health infrastructure in the northern districts.")

    insert("publications_publication_source", publication_id=pub_healthcare, order=0,
           citation_text="Population per Primary Health Centre by district, 2024. Health at a Glance 2024; CAG "
                          "Report on Public Health 2024; List of Modern Medical Institutions 2024–25 (source PDF, p.17).")
    insert("publications_publication_source", publication_id=pub_healthcare, order=1,
           citation_text="Population per bed in government hospitals by district. Same sources (source PDF, p.18).")
    insert("publications_publication_source", publication_id=pub_healthcare, order=2,
           citation_text="Population per doctor in government hospitals by district. Same sources (source PDF, p.19).")
    insert("publications_publication_source", publication_id=pub_healthcare, order=3,
           citation_text="Government of Kerala health policy norm of 3,000 population per PHC, as cited in the "
                          "source PDF, p.17.")

    # ---- Kerala's migration economy runs through the Gulf (pub_migration) ----
    insert("publications_publication_block", publication_id=pub_migration, order=0, block_type="heading",
           text="Emigration skews away from Kerala's population mix")
    insert("publications_publication_block", publication_id=pub_migration, order=1, block_type="paragraph",
           text="Hindus make up 53.2% of Kerala's population but only 35.2% of its emigrants — the largest gap "
                "of any group. Muslims and Christians both emigrate at higher rates than their population share "
                "would suggest: Muslims are 29.3% of the population but 41.9% of emigrants, and Christians are "
                "16.9% of the population but 22.3% of emigrants.")
    insert("publications_publication_block", publication_id=pub_migration, order=2, block_type="heading",
           text="For Muslims, that migration means almost exclusively the Gulf")
    insert("publications_publication_block", publication_id=pub_migration, order=3, block_type="paragraph",
           text="Kerala's overall dependence on Gulf destinations for emigration is high — 89.2% of the state's "
                "emigrants go to the Gulf. But that average hides a real gap by community: 98.5% of Muslim "
                "emigrants go to the Gulf, compared with 86.8% of Hindu emigrants and 76.3% of Christian emigrants.")
    insert("publications_publication_block", publication_id=pub_migration, order=4, block_type="heading",
           text="What Muslim migrants do once they're there")
    insert("publications_publication_block", publication_id=pub_migration, order=5, block_type="paragraph",
           text="Occupational data on Muslim migrants shows a workforce concentrated in service and manual-labour "
                "roles: salesman is the single largest category at 23.9%, followed by driver (15%), "
                "cashier/peon/office staff (8%), construction labourer (7.1%), hotel staff (6.7%) and "
                "storekeeper (6.2%). Together, these six categories account for 66% of Muslim migrants' occupations.")

    insert("publications_publication_source", publication_id=pub_migration, order=0,
           citation_text="Emigrant population and total population share by religion, Kerala, 2023. Kerala "
                          "Migration Survey 2023. Source PDF, p.13.")
    insert("publications_publication_source", publication_id=pub_migration, order=1,
           citation_text="Dependence on Gulf regions by religious group (share of each group's emigrants who go "
                          "to the Gulf). Kerala Migration Survey 2018. Source PDF, p.14.")
    insert("publications_publication_source", publication_id=pub_migration, order=2,
           citation_text="Major occupational categories among Muslim migrants. Kerala Migration Survey 2018. "
                          "Source PDF, p.15. The six listed categories sum to 66% of the total; the source does "
                          "not break out the remaining 34%.")

    # ---- pub_economic_report (non-data-story format, to show blocks work on any publication) ----
    insert("publications_publication_block", publication_id=pub_economic_report, order=0, block_type="subheading",
           text="Wealth concentration by district")
    insert("publications_publication_block", publication_id=pub_economic_report, order=1, block_type="paragraph",
           text="Findings from the Center for Economic Analysis on wealth and income distribution across "
                "Kerala's 14 districts, drawing on the 2025 household survey round.")
    insert("publications_publication_block", publication_id=pub_economic_report, order=2, block_type="image",
           image_url="publications/economic-analysis-report-2025-fig1.jpg",
           image_caption="District-wise wealth distribution, illustrative figure from the report.")
    insert("publications_publication_source", publication_id=pub_economic_report, order=0,
           citation_text="Kerala Economic Review 2025", url="")
    insert("publications_publication_source", publication_id=pub_economic_report, order=1,
           citation_text="PRI Household Income & Expenditure Survey (2025)", url="")

    # =================================================================
    # publications_datastory / datastory_stat / datastory_chart — Data-Story-only
    # enrichment, 1:1 with the 4 real "Kerala in Data" publications. Hook/callout stats and
    # chart data points below are the real numbers published on each story's live page.
    # =================================================================
    def datastory(pub_id, area_label, hook_note, lede, why_it_matters):
        return insert("publications_datastory", publication_id=pub_id, area_label=area_label,
                       hook_note=hook_note, lede=lede, why_it_matters=why_it_matters)

    ds_story_malappuram = datastory(
        pub_malappuram, "Education",
        "That's the average Plus One batch size in Malappuram in 2025 — nearly double the 36 students per "
        "batch in Pathanamthitta, Kerala's smallest, and well above the statewide average of 54.",
        "Kerala added 3.87 lakh Plus One seats across 7,223 batches in 2025. But that capacity isn't spread "
        "evenly, and district-level enrollment data shows the same district — Malappuram — carrying both the "
        "heaviest classroom load and the thinnest access to the science stream in the state.",
        "Malappuram's Plus One pressure isn't a temporary bulge that will resolve itself in the next year or "
        "two — the source data projects demand staying near or above 82,000 students annually through 2035, "
        "only easing meaningfully by 2036. That points to a specific, addressable gap: more science batches, "
        "not just more batches, in the district that needs them most.")
    ds_story_population = datastory(
        pub_population, "Demography",
        "Both numbers come from the same underlying community. Read together, they describe a population "
        "whose share of the state has grown gradually over more than a decade, but whose birth rate has been "
        "falling sharply and recently.",
        "Kerala publishes religion-wise population estimates only once a decade, at the Census. Between the "
        "2011 Census and 2024 projections, the state's religious composition moved modestly: Hindus' share "
        "fell from 54.7% to 52.0%, Christians' share fell from 18.3% to 17.6%, and Muslims' share rose from "
        "26.5% to 29.9%.",
        "Kerala's population mix has shifted gradually over more than a decade, and the age-structure data "
        "shows that shift largely reflects past fertility patterns still working through the population, not "
        "a trend that is speeding up. The clearest forward-looking signal is the births chart: a 27% drop in "
        "a single decade points toward convergence with the rest of the state's fertility pattern.")
    ds_story_healthcare = datastory(
        pub_healthcare, "Health",
        "That's how many people a single Primary Health Centre serves, on average, in Malappuram — nearly "
        "sixteen times the state's own policy target of 3,000 people per PHC, and more than double the figure "
        "in Pathanamthitta, Kerala's best-served district.",
        "Kerala's public health system is usually held up as a national model. But that reputation is built "
        "on statewide averages, and averages hide a lot. Broken down by district, the numbers show a "
        "consistent pattern: Malappuram and Kozhikode fall furthest behind on primary care access, hospital "
        "beds and doctor availability, while Pathanamthitta and Wayanad consistently sit ahead.",
        "Kerala's health infrastructure gap is concentrated, not diffuse — which is, in one sense, good news: "
        "it means targeted investment in a small number of districts could close most of the disparity, "
        "rather than requiring an across-the-board expansion.")
    ds_story_migration = datastory(
        pub_migration, "Migration",
        "Both figures point the same way: Muslims are over-represented among Kerala's emigrants relative to "
        "their share of the population, and that emigration is concentrated more narrowly on the Gulf than "
        "any other community's.",
        "Migration has shaped Kerala's economy for half a century, and the Kerala Migration Survey has "
        "tracked it since the 1990s. The most recent rounds show that emigration isn't spread across "
        "religious groups in proportion to population — and that Muslim emigrants in particular are "
        "concentrated in a narrow band of Gulf-based, service-sector jobs.",
        "Kerala's own migration data connects Gulf economic downturns to job losses and return migration, and "
        "this data shows why that risk isn't evenly spread: Muslim migrants combine the highest Gulf-dependence "
        "of any group (98.5%) with concentration in occupational categories that are typically among the first "
        "affected when Gulf economies tighten.")

    insert("publications_datastory_stat", datastory_id=ds_story_malappuram, order=0, kind="hook",
           value="65", label="students a batch")
    insert("publications_datastory_stat", datastory_id=ds_story_malappuram, order=1, kind="callout",
           value="86,106", label="Peak projected demand", sub="expected students, 2033", tone="warning")
    insert("publications_datastory_stat", datastory_id=ds_story_malappuram, order=2, kind="callout",
           value="77,442", label="Lowest projected demand", sub="expected students, 2036", tone="neutral")

    insert("publications_datastory_stat", datastory_id=ds_story_population, order=0, kind="hook",
           value="29.9%", label="Muslim share of Kerala's population, 2024 (est.)", sub="up from 26.5% in 2011")
    insert("publications_datastory_stat", datastory_id=ds_story_population, order=1, kind="hook",
           value="-27%", label="Decline in annual Muslim births in Kerala, 2014 → 2024")
    insert("publications_datastory_stat", datastory_id=ds_story_population, order=2, kind="callout",
           value="52.0%", label="Hindu, 2024")
    insert("publications_datastory_stat", datastory_id=ds_story_population, order=3, kind="callout",
           value="29.9%", label="Muslim, 2024")
    insert("publications_datastory_stat", datastory_id=ds_story_population, order=4, kind="callout",
           value="17.6%", label="Christian, 2024")

    insert("publications_datastory_stat", datastory_id=ds_story_healthcare, order=0, kind="hook",
           value="47,051 people", label="served per Primary Health Centre in Malappuram")
    insert("publications_datastory_stat", datastory_id=ds_story_healthcare, order=1, kind="callout",
           value="≈1.3–2.0×", label="Malappuram vs. Kerala average",
           sub="higher population load across PHCs, beds and doctors", tone="warning")
    insert("publications_datastory_stat", datastory_id=ds_story_healthcare, order=2, kind="callout",
           value="≈0.5–0.6×", label="Pathanamthitta vs. Kerala average",
           sub="lower population load across the same three measures", tone="positive")

    insert("publications_datastory_stat", datastory_id=ds_story_migration, order=0, kind="hook",
           value="41.9%", label="of Kerala's emigrants are Muslim", sub="vs. 29.3% of its total population")
    insert("publications_datastory_stat", datastory_id=ds_story_migration, order=1, kind="hook",
           value="98.5%", label="of Muslim emigrants go specifically to the Gulf")
    insert("publications_datastory_stat", datastory_id=ds_story_migration, order=2, kind="callout",
           value="66%", label="Top 6 job categories", sub="share of Muslim migrants' occupations")
    insert("publications_datastory_stat", datastory_id=ds_story_migration, order=3, kind="callout",
           value="Salesman, 23.9%", label="Largest single occupational category")

    insert("publications_datastory_chart", datastory_id=ds_story_malappuram, order=0,
           block_id=blk_malappuram_h1, chart_type="bar",
           title="Students per Plus One batch by district",
           data=json.dumps({"unit": "students/batch", "rows": [
               {"district": "Malappuram", "value": 65}, {"district": "Wayanad", "value": 60},
               {"district": "Kasargode", "value": 60}, {"district": "Idukki", "value": 43},
               {"district": "Kottayam", "value": 43}, {"district": "Pathanamthitta", "value": 36},
           ]}), x_label="District", y_label="Students per batch", note="All-Kerala avg: 54")
    insert("publications_datastory_chart", datastory_id=ds_story_malappuram, order=1,
           block_id=blk_malappuram_h2, chart_type="bar",
           title="Share of batches that are Science stream, by district",
           data=json.dumps({"unit": "% of batches", "rows": [
               {"district": "Kasargode", "value": 40}, {"district": "Malappuram", "value": 42},
               {"district": "Pathanamthitta", "value": 58}, {"district": "Kottayam", "value": 63},
           ]}), x_label="District", y_label="Share of batches that are Science stream (%)",
           note="All-Kerala avg: 51%")
    insert("publications_datastory_chart", datastory_id=ds_story_malappuram, order=2,
           block_id=blk_malappuram_h4, chart_type="line",
           title="Malappuram's projected Plus One aspirants, 2027–2036",
           data=json.dumps({"unit": "expected students", "rows": [
               {"year": 2027, "value": 84265}, {"year": 2033, "value": 86106}, {"year": 2036, "value": 77442},
           ]}), x_label="Year", y_label="Expected Plus One aspirants, Malappuram",
           note="Peak: 86,106 in 2033. Source describes the range as \"between 84,000 and 77,000\"; "
                "the year-by-year series shows a higher 2033 peak.")
    insert("publications_datastory_chart", datastory_id=ds_story_malappuram, order=3,
           chart_type="scatter", title="Batch size vs. science-stream share, by district",
           data=json.dumps({"unit": "students/batch vs. % science", "rows": [
               {"district": "Malappuram", "batch_size": 65, "science_share": 42},
               {"district": "Kasargode", "batch_size": 60, "science_share": 40},
               {"district": "Kottayam", "batch_size": 43, "science_share": 63},
               {"district": "Pathanamthitta", "batch_size": 36, "science_share": 58},
           ]}), x_label="Students per batch", y_label="Science batches (%)",
           note="Larger average batch size tracks with a smaller share of science batches.")

    insert("publications_datastory_chart", datastory_id=ds_story_population, order=0,
           chart_type="bar", title="Religious population share, 2011 vs. 2024",
           data=json.dumps({"unit": "% of population", "rows": [
               {"religion": "Hindu", "2011": 54.7, "2024": 52.0},
               {"religion": "Muslim", "2011": 26.5, "2024": 29.9},
               {"religion": "Christian", "2011": 18.3, "2024": 17.6},
           ]}), x_label="Year", y_label="Share of Kerala population (%)")
    insert("publications_datastory_chart", datastory_id=ds_story_population, order=1,
           chart_type="bar", title="Population share by age bracket and religion, 2024",
           data=json.dumps({"unit": "% of age bracket", "rows": [
               {"religion": "Hindu", "under_18": 42.6, "over_40": 57.4},
               {"religion": "Muslim", "under_18": 40.3, "over_40": 22.6},
               {"religion": "Christian", "under_18": 15.7, "over_40": 19.8},
           ]}), x_label="Age bracket", y_label="Share of age bracket (%)")
    insert("publications_datastory_chart", datastory_id=ds_story_population, order=2,
           chart_type="line", title="Annual births to Kerala Muslim families, 2014 vs. 2024",
           data=json.dumps({"unit": "births", "rows": [
               {"year": 2014, "value": 218437}, {"year": 2024, "value": 159088},
           ]}), x_label="Year", y_label="Annual births", note="27% decline over the decade")

    insert("publications_datastory_chart", datastory_id=ds_story_healthcare, order=0,
           chart_type="bar", title="People per Primary Health Centre by district",
           data=json.dumps({"unit": "people/PHC", "rows": [
               {"district": "Pathanamthitta", "value": 23046}, {"district": "Idukki", "value": 23654},
               {"district": "Kozhikode", "value": 44171}, {"district": "Malappuram", "value": 47051},
           ]}), x_label="District", y_label="People per Primary Health Centre",
           note="Kerala avg: 36,303. GOK policy target: 3,000")
    insert("publications_datastory_chart", datastory_id=ds_story_healthcare, order=1,
           chart_type="bar", title="People per government-hospital bed by district",
           data=json.dumps({"unit": "people/bed", "rows": [
               {"district": "Pathanamthitta", "value": 589}, {"district": "Alappuzha", "value": 632},
               {"district": "Kozhikode", "value": 1204}, {"district": "Malappuram", "value": 1861},
           ]}), x_label="District", y_label="People per government-hospital bed", note="Kerala average: 928")
    insert("publications_datastory_chart", datastory_id=ds_story_healthcare, order=2,
           chart_type="bar", title="People per government-hospital doctor by district",
           data=json.dumps({"unit": "people/doctor", "rows": [
               {"district": "Pathanamthitta", "value": 3754}, {"district": "Wayanad", "value": 3930},
               {"district": "Kozhikode", "value": 7245}, {"district": "Malappuram", "value": 7437},
           ]}), x_label="District", y_label="People per government-hospital doctor")
    # Illustrative — the live page renders this comparison as a grouped bar chart (see above),
    # not a map; included here only to demonstrate the 'map' chart_type, which none of the 4
    # real data stories currently use (their charts are all bar/line/scatter).
    insert("publications_datastory_chart", datastory_id=ds_story_healthcare, order=3,
           chart_type="map", title="District-level healthcare capacity load (illustrative choropleth)",
           data=json.dumps({"unit": "index vs. state avg", "rows": [
               {"district": "Malappuram", "value": 1.9}, {"district": "Kozhikode", "value": 1.7},
               {"district": "Pathanamthitta", "value": 0.55}, {"district": "Wayanad", "value": 0.6},
           ]}), note="Index: 1.0 = Kerala average across PHCs, beds, and doctors combined.")

    insert("publications_datastory_chart", datastory_id=ds_story_migration, order=0,
           chart_type="bar", title="Population share vs. emigrant share by religion",
           data=json.dumps({"unit": "%", "rows": [
               {"religion": "Hindu", "population_share": 53.2, "emigrant_share": 35.2},
               {"religion": "Muslim", "population_share": 29.3, "emigrant_share": 41.9},
               {"religion": "Christian", "population_share": 16.9, "emigrant_share": 22.3},
           ]}), x_label="Religion", y_label="Share (%)")
    insert("publications_datastory_chart", datastory_id=ds_story_migration, order=1,
           chart_type="bar", title="Share of emigrants going to the Gulf, by religion",
           data=json.dumps({"unit": "%", "rows": [
               {"religion": "Christian", "value": 76.3}, {"religion": "Hindu", "value": 86.8},
               {"religion": "Kerala (all)", "value": 89.2}, {"religion": "Muslim", "value": 98.5},
           ]}), x_label="Religion", y_label="Share of emigrants going to the Gulf (%)")
    insert("publications_datastory_chart", datastory_id=ds_story_migration, order=2,
           chart_type="bar", title="Occupational categories among Muslim migrants",
           data=json.dumps({"unit": "% of Muslim migrants", "rows": [
               {"occupation": "Salesman", "value": 23.9}, {"occupation": "Driver", "value": 15.0},
               {"occupation": "Cashier/peon/office staff", "value": 8.0},
               {"occupation": "Construction labourer", "value": 7.1},
               {"occupation": "Hotel staff", "value": 6.7}, {"occupation": "Storekeeper", "value": 6.2},
           ]}), x_label="Occupation", y_label="Share of Muslim migrants (%)",
           note="Top 6 categories sum to 66%; remaining 34% not broken out in the source.")

    # =================================================================
    # MODULE C — datarepo (native Django, not CKAN)
    # (format: csv|parquet|zip, visibility: public|on_request|internal_only)
    # =================================================================
    def dataset(slug, title, fmt, theme, geography, year, visibility, status, reviewed_by=None,
                tags=None, coverage="", last_updated=None, file_size=None, download_count=0, dtype=""):
        return insert("datarepo_dataset", slug=slug, title=title, description=f"{title} — sample dataset.",
                       file=f"datasets/{slug}.{fmt}", format=fmt, theme_id=theme_id_by_name[theme],
                       geography=geography, year=year, source="PRI field research", update_frequency="annual",
                       tags=json.dumps(tags or [theme.lower()]), coverage=coverage, last_updated=last_updated,
                       file_size=file_size, download_count=download_count, type=dtype,
                       visibility=visibility, status=status, created_by_id=thufail, reviewed_by_id=reviewed_by)

    ds_education = dataset("education-enrolment-district-2026", "Education Enrolment by District (2026)",
                            "csv", "Education", "District-level", 2026, "public", "published", hashir,
                            tags=["education", "enrolment", "district"],
                            coverage="District-level enrolment figures across all 14 Kerala districts.",
                            last_updated="2026-09-01", file_size=482000, download_count=134, dtype="Administrative")
    ds_health = dataset("health-facility-capacity-2025", "Health Facility Capacity (2025)",
                         "parquet", "Health", "District-level", 2025, "public", "published", hashir,
                         tags=["health", "facilities", "capacity"],
                         coverage="Primary and secondary health facility capacity by district.",
                         last_updated="2025-11-15", file_size=915000, download_count=58, dtype="Administrative")
    ds_finance = dataset("public-finance-budget-2026", "Public Finance Budget Allocation (2026)",
                         "csv", "Public Finance", "National", 2026, "on_request", "published", hashir,
                         tags=["public-finance", "budget"],
                         coverage="State-level budget allocation and expenditure by department.",
                         last_updated="2026-08-20", file_size=210000, download_count=12, dtype="Administrative")
    ds_employment = dataset("employment-survey-microdata-2025", "Employment Survey Microdata (2025)",
                             "zip", "Employment", "Kerala", 2025, "internal_only", "approved", hashir,
                             tags=["employment", "survey", "microdata"],
                             coverage="Household-level employment survey microdata, statewide sample.",
                             last_updated="2025-12-01", file_size=15400000, download_count=0, dtype="Survey")
    ds_demography = dataset("demography-migration-panchayat-2024", "Demography & Migration by Panchayat (2024)",
                             "zip", "Demography", "Panchayat-level", 2024, "public", "in_review",
                             tags=["demography", "migration", "panchayat"],
                             coverage="Panchayat-level demographic and migration indicators.",
                             last_updated="2024-06-01", file_size=3200000, download_count=0, dtype="Panel")
    ds_governance = dataset("governance-scheme-uptake-2026", "Welfare Scheme Uptake (2026, internal)",
                             "csv", "Governance", "Kerala", 2026, "internal_only", "draft",
                             tags=["governance", "welfare-schemes"],
                             coverage="Scheme-wise uptake figures, internal monitoring only.",
                             last_updated="2026-09-10", file_size=64000, download_count=0, dtype="Administrative")
    ds_archived = dataset("archived-employment-survey-2019", "Employment Survey (Archived, 2019)",
                           "parquet", "Employment", "Kerala", 2019, "on_request", "unpublished", hashir,
                           tags=["employment", "survey", "archived"],
                           coverage="Superseded by the 2025 employment survey microdata.",
                           last_updated="2019-12-01", file_size=8100000, download_count=41, dtype="Survey")
    ds_economics = dataset("household-income-expenditure-2025", "Household Income & Expenditure Survey (2025)",
                            "csv", "Economics", "Kerala", 2025, "public", "published", hashir,
                            tags=["economics", "income", "expenditure"],
                            coverage="Statewide household income and expenditure survey sample.",
                            last_updated="2025-10-05", file_size=1250000, download_count=27, dtype="Survey")

    def dashboard(slug, title, embed_type, theme, status, reviewed_by=None):
        return insert("datarepo_dashboard", slug=slug, title=title, description=f"{title} — embedded dashboard.",
                       embed_url=f"https://example.com/embeds/{slug}", embed_type=embed_type,
                       theme_id=theme_id_by_name[theme], geography="Kerala", year=2026, type="dashboard",
                       status=status, created_by_id=hashir, reviewed_by_id=reviewed_by)

    dash_education = dashboard("education-access-dashboard", "Education access dashboard", "datawrapper",
                                "Education", "published", noushad)
    dash_finance = dashboard("public-finance-dashboard", "Public finance dashboard", "tableau",
                              "Public Finance", "in_review")
    dash_demography = dashboard("demography-migration-map", "Demography & migration map", "d3",
                                 "Demography", "approved", noushad)
    dash_health = dashboard("health-capacity-dashboard", "Health capacity dashboard (draft)", "datawrapper",
                             "Health", "draft")
    dash_employment_old = dashboard("employment-dashboard-2022", "Employment dashboard (2022, archived)", "tableau",
                                     "Employment", "unpublished", noushad)
    dash_governance = dashboard("governance-transparency-dashboard", "Governance transparency dashboard", "d3",
                                 "Governance", "published", noushad)

    insert("datarepo_dashboard_datasets", dashboard_id=dash_education, dataset_id=ds_education)
    insert("datarepo_dashboard_datasets", dashboard_id=dash_finance, dataset_id=ds_finance)
    insert("datarepo_dashboard_datasets", dashboard_id=dash_finance, dataset_id=ds_employment)
    insert("datarepo_dashboard_datasets", dashboard_id=dash_demography, dataset_id=ds_demography)
    insert("datarepo_dashboard_datasets", dashboard_id=dash_health, dataset_id=ds_health)
    insert("datarepo_dashboard_datasets", dashboard_id=dash_employment_old, dataset_id=ds_archived)
    insert("datarepo_dashboard_datasets", dashboard_id=dash_governance, dataset_id=ds_governance)

    # =================================================================
    # datarepo_accessgroup / member / grant — group-based dataset access
    # =================================================================
    group_mlas = insert("datarepo_accessgroup", slug="kerala-mlas-2026", name="Kerala MLAs 2026",
                         description="Sitting MLAs granted blanket access to select public-interest datasets.")
    group_partners = insert("datarepo_accessgroup", slug="partner-university-researchers",
                             name="Partner University Researchers",
                             description="Researchers at partner institutions with standing dataset access.")

    insert("datarepo_accessgroup_member", group_id=group_mlas, user_id=donor2, added_by_id=noushad)
    insert("datarepo_accessgroup_member", group_id=group_mlas, user_id=donor3, added_by_id=noushad)
    insert("datarepo_accessgroup_member", group_id=group_partners, user_id=fellow_hisham_user, added_by_id=hashir)

    insert("datarepo_accessgroup_grant", group_id=group_mlas, dataset_id=ds_finance, granted_by_id=noushad,
           expires_at="2027-01-01 00:00:00")
    insert("datarepo_accessgroup_grant", group_id=group_mlas, dataset_id=ds_archived, granted_by_id=noushad)
    insert("datarepo_accessgroup_grant", group_id=group_partners, dataset_id=ds_employment, granted_by_id=hashir)

    # =================================================================
    # datarepo_downloadlog / favorite
    # =================================================================
    insert("datarepo_downloadlog", user_id=donor1, dataset_id=ds_education, ip="203.0.113.5")
    insert("datarepo_downloadlog", user_id=None, dataset_id=ds_education, ip="203.0.113.99")
    insert("datarepo_downloadlog", user_id=fellow_hisham_user, dataset_id=ds_health, ip="203.0.113.12")
    insert("datarepo_downloadlog", user_id=None, dataset_id=ds_economics, ip="203.0.113.44")

    insert("datarepo_favorite", user_id=donor1, dataset_id=ds_education)
    insert("datarepo_favorite", user_id=donor2, dataset_id=ds_finance)
    insert("datarepo_favorite", user_id=fellow_hisham_user, dataset_id=ds_health)

    # AccessRequest (status: pending|approved|denied) — only against
    # `on_request` datasets; `internal_only` has no request path (staff-only).
    insert("datarepo_accessrequest", user_id=donor1, dataset_id=ds_finance, status="approved",
           reviewed_at="2026-04-02 10:00:00", reviewed_by_id=hashir)
    insert("datarepo_accessrequest", user_id=donor2, dataset_id=ds_finance, status="pending")
    insert("datarepo_accessrequest", user_id=donor3, dataset_id=ds_archived, status="denied",
           reviewed_at="2026-04-05 09:00:00", reviewed_by_id=hashir)
    insert("datarepo_accessrequest", user_id=fellow_hisham_user, dataset_id=ds_archived, status="pending")
    insert("datarepo_accessrequest", user_id=donor1, dataset_id=ds_archived, status="approved",
           reviewed_at="2026-04-06 09:00:00", reviewed_by_id=hashir)

    # =================================================================
    # MODULE D — fellowship
    # (application status: submitted|under_review|shortlisted|rejected|accepted|onboarded)
    # =================================================================
    program_2026 = insert("fellowship_program", slug="fellowship-2026", name="2026 Research Fellowship",
                           description="Programme to train the next generation of researchers and policymakers.",
                           start_date="2026-06-01", end_date="2026-12-01", is_active=1)
    program_internship = insert("fellowship_program", slug="internship-2026", name="Internship Programme",
                                 description="Short-term placements across PRI's five research departments.",
                                 start_date="2026-06-01", end_date="2026-09-01", is_active=1)
    program_2024_archived = insert("fellowship_program", slug="fellowship-2024", name="2024 Research Fellowship",
                                    description="Prior fellowship cohort, now concluded.",
                                    start_date="2024-06-01", end_date="2024-12-01", is_active=0)

    def timeline(program_id, stages):
        for i, (label, date) in enumerate(stages):
            insert("fellowship_programtimelinestage", program_id=program_id, order=i,
                   stage_label=label, stage_date=date)

    timeline(program_2026, [
        ("Applications open", "2026-04-01"), ("Application deadline", "2026-05-15"),
        ("Shortlisting & interviews", "2026-05-25"), ("Programme begins", "2026-06-01"),
    ])
    timeline(program_internship, [
        ("Applications open", "2026-04-01"), ("Application deadline", "2026-05-15"),
        ("Shortlisting & interviews", "2026-05-25"), ("Programme begins", "2026-06-01"),
    ])

    field_schema = json.dumps({"fields": [{"name": "cv", "type": "file", "required": True},
                                           {"name": "writing_sample", "type": "file", "required": True},
                                           {"name": "statement", "type": "text", "required": True}]})
    form_2026 = insert("fellowship_applicationform", program_id=program_2026, field_schema=field_schema, version=1)
    form_internship = insert("fellowship_applicationform", program_id=program_internship, field_schema=field_schema, version=1)
    insert("fellowship_applicationform", program_id=program_2024_archived, field_schema=field_schema, version=1)

    def application(program, name, email, status, applicant_user=None, onboarded_profile=None,
                     intake_channel="fellowship_portal"):
        return insert("fellowship_application", program_id=program, applicant_name=name, applicant_email=email,
                      applicant_phone="+91-9000000000", applicant_user_id=applicant_user,
                      intake_channel=intake_channel,
                      answers=json.dumps({"statement": f"Application statement for {name}."}),
                      status=status, onboarded_profile_id=onboarded_profile)

    app_hisham = application(program_2026, "Hisham", "hisham@priresearch.in", "onboarded",
                              applicant_user=fellow_hisham_user, onboarded_profile=p_hisham)
    app_aisha = application(program_2026, "Aisha Rahman", "aisha.rahman@example.com", "under_review")
    app_farhan = application(program_internship, "Farhan Sheikh", "farhan.sheikh@example.com", "submitted",
                              intake_channel="get_involved_form")
    app_nithya = application(program_internship, "Nithya Krishnan", "nithya.krishnan@example.com", "shortlisted")
    application(program_2026, "Vishnu Prasad", "vishnu.prasad@example.com", "rejected")
    application(program_2024_archived, "Fatima Zahra", "fatima.zahra@example.com", "accepted",
                intake_channel=None)   # legacy application predates the intake-channel distinction
    application(program_2024_archived, "Past Fellow Two", "past.fellow.two@example.com", "onboarded",
                onboarded_profile=p_past_fellow_two)

    insert("fellowship_applicationdocument", application_id=app_hisham, label="CV", file="applications/hisham-cv.pdf")
    insert("fellowship_applicationdocument", application_id=app_hisham, label="Writing Sample",
           file="applications/hisham-writing.pdf")
    insert("fellowship_applicationdocument", application_id=app_aisha, label="CV", file="applications/aisha-cv.pdf")
    insert("fellowship_applicationdocument", application_id=app_farhan, label="CV", file="applications/farhan-cv.pdf")
    insert("fellowship_applicationdocument", application_id=app_nithya, label="Writing Sample",
           file="applications/nithya-writing.pdf")

    insert("fellowship_review", application_id=app_hisham, reviewer_id=hashir, score=9,
           notes="Strong candidate, recommend acceptance.")
    insert("fellowship_review", application_id=app_aisha, reviewer_id=hashir, score=7, notes="Promising, needs a second read.")
    insert("fellowship_review", application_id=app_aisha, reviewer_id=noushad, score=8, notes="Agree — advance to shortlist.")
    insert("fellowship_review", application_id=app_nithya, reviewer_id=hashir, score=8, notes="Strong writing sample.")

    insert("fellowship_programreviewer", user_id=hashir, program_id=program_2026)
    insert("fellowship_programreviewer", user_id=noushad, program_id=program_internship)
    insert("fellowship_programreviewer", user_id=badusha, program_id=program_2026)

    # =================================================================
    # MODULE E — media watch
    # (item_type: image|text|video, classification: ''|hate_speech|misinformation|communal_bias|other,
    #  status: flagged|under_review|confirmed|public)
    # =================================================================
    case_migration = insert("mediawatch_mediacase", item_type="text",
                             headline_text="Viral post misrepresents PRI's Gulf-migration data story",
                             note="Flagged by a researcher monitoring social media reactions to the migration data story.",
                             classification="misinformation", theme_id=theme_id_by_name["Migration"],
                             source="Twitter/X", status="public",
                             flagged_by_id=afsal, reviewed_by_id=hashir, reviewed_at="2026-03-10 09:00:00")
    case_mosque = insert("mediawatch_mediacase", item_type="image",
                          headline_text="Circulated photo mischaracterizes a local inter-religious event",
                          note="Confirmed as communal-bias framing; response drafted, pending publication.",
                          classification="communal_bias", source="WhatsApp forward", status="confirmed",
                          flagged_by_id=thufail, reviewed_by_id=hashir, reviewed_at="2026-03-12 11:00:00")
    case_unverified = insert("mediawatch_mediacase", item_type="video",
                              headline_text="Unverified video clip circulating with no clear source",
                              note="Awaiting classification.", classification="", source="Telegram channel",
                              status="flagged", flagged_by_id=rashiq)
    case_health_forward = insert("mediawatch_mediacase", item_type="text",
                                  headline_text="WhatsApp forward misquotes the healthcare-capacity data story",
                                  note="Under review by the editorial desk.", classification="misinformation",
                                  theme_id=theme_id_by_name["Health"],
                                  source="WhatsApp forward", status="under_review", flagged_by_id=afsal)
    case_editorial = insert("mediawatch_mediacase", item_type="text",
                             headline_text="Opinion column mischaracterizes PRI's budget infographic",
                             note="Flagged for one-sided framing of the public-finance infographic.",
                             classification="other", theme_id=theme_id_by_name["Public Finance"],
                             source="Regional newspaper op-ed", status="public",
                             flagged_by_id=badusha, reviewed_by_id=noushad, reviewed_at="2026-02-02 10:00:00")
    case_caption = insert("mediawatch_mediacase", item_type="image",
                           headline_text="Misleading caption paired with an unrelated PRI event photo",
                           note="Under review — classification pending committee discussion.",
                           classification="hate_speech", source="Facebook page", status="under_review",
                           flagged_by_id=thufail)

    resp_migration = insert("mediawatch_response", case_id=case_migration, type="rebuttal",
           body="PRI's original data does not support the claims in this post; see our full rebuttal and methodology note.",
           published_by_id=hashir, published_at="2026-03-11 12:00:00")
    resp_editorial = insert("mediawatch_response", case_id=case_editorial, type="press_statement",
           body="PRI's public statement clarifying the budget infographic's methodology and sourcing.",
           published_by_id=noushad, published_at="2026-02-03 09:00:00")
    insert("mediawatch_response", case_id=case_mosque, type="op_ed",
           body="Drafted op-ed response, awaiting final sign-off before publication.", published_by_id=hashir,
           published_at=None)
    insert("mediawatch_response", case_id=case_health_forward, type="explainer",
           body="Drafted explainer distinguishing the original data story from the misquoted forward.",
           published_by_id=hashir, published_at=None)
    resp_caption = insert("mediawatch_response", case_id=case_caption, type="toolkit",
           body="Drafted media-literacy toolkit assets for this case, pending committee review.",
           published_by_id=hashir, published_at=None)

    insert("mediawatch_response_attachment", response_id=resp_migration,
           file="mediawatch/migration-rebuttal-methodology-note.pdf", label="Methodology Note")
    insert("mediawatch_response_attachment", response_id=resp_editorial,
           file="mediawatch/editorial-press-statement.pdf", label="Press Statement PDF")
    insert("mediawatch_response_attachment", response_id=resp_caption,
           file="mediawatch/caption-toolkit-assets.zip", label="Toolkit Assets (zip)")
    insert("mediawatch_response_attachment", response_id=resp_caption,
           file="mediawatch/caption-media-literacy-flyer.pdf", label="Flyer PDF")

    # =================================================================
    # MODULE F — donors
    # (payment_gateway: razorpay|instamojo, status: pending|succeeded|failed)
    # =================================================================
    donor_row1 = insert("donors_donor", user_id=donor1, name="Fathima K", phone="+91-9000000101",
                         address="Kozhikode, Kerala")
    donor_row2 = insert("donors_donor", user_id=donor2, name="Arjun Menon", phone="+91-9000000102",
                         address="Kochi, Kerala")
    donor_row3 = insert("donors_donor", user_id=donor3, name="Sreelakshmi Pillai", phone="+91-9000000103",
                         address="Thiruvananthapuram, Kerala")

    campaign_education = insert("donors_campaign", slug="education-for-all-2026", name="Education for All 2026",
                                 description="Fundraising in support of the district education-access research.",
                                 goal_amount=500000, start_date="2026-01-01", end_date="2026-12-31", is_active=1)
    campaign_health = insert("donors_campaign", slug="health-equity-fund", name="Health Equity Fund",
                              description="Supporting the healthcare-capacity data programme.", goal_amount=300000,
                              start_date="2026-02-01", end_date="2026-12-31", is_active=1)
    campaign_archived = insert("donors_campaign", slug="relief-fund-2023", name="Community Relief Fund (2023)",
                                description="A concluded emergency relief campaign.", goal_amount=150000,
                                start_date="2023-06-01", end_date="2023-12-31", is_active=0)

    tier_supporter = insert("donors_donationtier", label="Supporter", suggested_amount=1000, is_active=1)
    tier_patron = insert("donors_donationtier", label="Patron", suggested_amount=10000, is_active=1)
    tier_legacy = insert("donors_donationtier", label="Legacy Circle", suggested_amount=50000, is_active=0)

    donation1 = insert("donors_donation", donor_id=donor_row1, campaign_id=campaign_education, tier_id=tier_supporter,
                        amount=1000, currency="INR", payment_gateway="razorpay", payment_gateway_ref="pay_ABC101",
                        status="succeeded")
    insert("donors_donation", donor_id=donor_row1, campaign_id=campaign_health, tier_id=tier_patron,
           amount=10000, currency="INR", payment_gateway="instamojo", payment_gateway_ref="pay_ABC102",
           status="pending")
    insert("donors_donation", donor_id=donor_row2, campaign_id=campaign_education, tier_id=tier_supporter,
           amount=1000, currency="INR", payment_gateway="razorpay", payment_gateway_ref="pay_ABC103",
           status="failed")
    donation4 = insert("donors_donation", donor_id=donor_row2, campaign_id=campaign_archived, tier_id=tier_legacy,
                        amount=50000, currency="INR", payment_gateway="instamojo", payment_gateway_ref="pay_ABC104",
                        status="succeeded")
    insert("donors_donation", donor_id=donor_row3, campaign_id=campaign_health, tier_id=tier_supporter,
           amount=1000, currency="INR", payment_gateway="razorpay", payment_gateway_ref="pay_ABC105",
           status="pending")
    donation_instamojo_failed = insert("donors_donation", donor_id=donor_row3, campaign_id=campaign_education,
           tier_id=tier_patron, amount=10000, currency="INR", payment_gateway="instamojo",
           payment_gateway_ref="pay_ABC106", status="failed")

    insert("donors_taxreceipt", donation_id=donation1, receipt_number="PRI-2026-00001",
           file="receipts/PRI-2026-00001.pdf")
    insert("donors_taxreceipt", donation_id=donation4, receipt_number="PRI-2023-00047",
           file="receipts/PRI-2023-00047.pdf")

    # =================================================================
    # donors_webhookevent — raw gateway events, for reconciliation against donors_donation
    # =================================================================
    insert("donors_webhookevent", gateway="razorpay", event_type="payment.captured",
           raw_payload=json.dumps({"id": "pay_ABC101", "status": "captured"}), donation_id=donation1,
           processed_at="2026-01-05 10:01:00", result="matched")
    insert("donors_webhookevent", gateway="instamojo", event_type="payment.failed",
           raw_payload=json.dumps({"id": "pay_ABC106", "status": "failed"}), donation_id=donation_instamojo_failed,
           processed_at="2026-01-06 11:00:00", result="matched")
    insert("donors_webhookevent", gateway="razorpay", event_type="payment.captured",
           raw_payload=json.dumps({"id": "pay_XYZ999", "status": "captured"}), donation_id=None,
           result="unmatched")   # illustrates the reconciliation-gap scenario the PRD calls out

    # =================================================================
    # MODULE G — forms
    # (anonymous_allowed / crm_sync_enabled booleans — every combo covered
    # except anon=1 + crm=1, which the PRD forbids: anonymous submissions
    # must never sync to a CRM.)
    # =================================================================
    form_newsletter = insert("forms_formdefinition", slug="newsletter-signup", name="Newsletter Signup",
                              field_schema=json.dumps({"fields": [{"name": "email", "type": "email", "required": True},
                                                                   {"name": "segment", "type": "select", "required": True}]}),
                              routing_rule=json.dumps({"destination": "comms@priresearch.in"}),
                              crm_sync_enabled=1, anonymous_allowed=0)
    form_whistleblower = insert("forms_formdefinition", slug="whistleblower", name="Whistleblower Report",
                                 field_schema=json.dumps({"fields": [{"name": "report", "type": "text", "required": True}]}),
                                 routing_rule=json.dumps({"destination": "ethics@priresearch.in"}),
                                 crm_sync_enabled=0, anonymous_allowed=1)
    form_contact = insert("forms_formdefinition", slug="contact-form-research", name="Contact — Research Inquiries",
                           field_schema=json.dumps({"fields": [{"name": "message", "type": "text", "required": True},
                                                                {"name": "category", "type": "select", "required": True}]}),
                           routing_rule=json.dumps({"field": "category", "routes": {"research": "research@priresearch.in",
                                                                                     "media": "media@priresearch.in"}}),
                           crm_sync_enabled=1, anonymous_allowed=0)
    form_volunteer = insert("forms_formdefinition", slug="volunteer-signup", name="Volunteer Signup",
                             field_schema=json.dumps({"fields": [{"name": "skills", "type": "text", "required": False}]}),
                             routing_rule=json.dumps({"destination": "volunteers@priresearch.in"}),
                             crm_sync_enabled=0, anonymous_allowed=0)
    form_event = insert("forms_formdefinition", slug="event-registration-policy-roundtable",
                         name="Event Registration — Policy Roundtable",
                         field_schema=json.dumps({"fields": [{"name": "event_id", "type": "hidden", "required": True}]}),
                         routing_rule=json.dumps({"destination": "events@priresearch.in"}),
                         crm_sync_enabled=0, anonymous_allowed=0)

    insert("forms_formsubmission", form_id=form_newsletter, data=json.dumps({"email": "fathima.k@example.com", "segment": "general"}),
           is_anonymous=0, submitter_name="Fathima K", submitter_email="fathima.k@example.com", submitter_ip="203.0.113.5")
    insert("forms_formsubmission", form_id=form_newsletter, data=json.dumps({"email": "arjun.menon@example.com", "segment": "donor"}),
           is_anonymous=0, submitter_name="Arjun Menon", submitter_email="arjun.menon@example.com", submitter_ip="203.0.113.9")
    insert("forms_formsubmission", form_id=form_whistleblower,
           data=json.dumps({"report": "Reporting a possible conflict of interest in vendor selection."}),
           is_anonymous=1, submitter_name=None, submitter_email=None, submitter_ip=None)
    insert("forms_formsubmission", form_id=form_whistleblower,
           data=json.dumps({"report": "Concern about data-handling practices on a recent survey."}),
           is_anonymous=1, submitter_name=None, submitter_email=None, submitter_ip=None)
    insert("forms_formsubmission", form_id=form_contact,
           data=json.dumps({"message": "Requesting the microdata behind the healthcare data story.", "category": "research"}),
           is_anonymous=0, submitter_name="Dr. Ken Ito", submitter_email="ken.ito@university.example", submitter_ip="203.0.113.20")
    insert("forms_formsubmission", form_id=form_contact,
           data=json.dumps({"message": "Press inquiry about the Gulf-migration data story.", "category": "media"}),
           is_anonymous=0, submitter_name="Priya Warrier", submitter_email="priya.warrier@newsdesk.example",
           submitter_ip="203.0.113.21")
    insert("forms_formsubmission", form_id=form_volunteer, data=json.dumps({"skills": "GIS mapping, survey design"}),
           is_anonymous=0, submitter_name="Devika Nair", submitter_email="devika.nair@example.com", submitter_ip="203.0.113.30")
    insert("forms_formsubmission", form_id=form_event, data=json.dumps({"event_id": "policy-roundtable-2026"}),
           is_anonymous=0, submitter_name="Sam Visitor", submitter_email="sam.visitor@example.com", submitter_ip="203.0.113.40")

    conn.commit()


CHECK_PATTERN = re.compile(r'CHECK\s*\(\s*"?(\w+)"?\s+IN\s*\(([^)]+)\)\)')
TABLE_PATTERN = re.compile(r"CREATE TABLE (\w+)")


def check_enum_coverage(conn: sqlite3.Connection) -> list[str]:
    """
    Parses every `CHECK (col IN (...))` constraint out of SCHEMA and verifies
    the sample data contains at least one row for each allowed value.
    Returns a list of human-readable gaps (empty if full coverage).
    """
    gaps = []
    table_starts = [(m.start(), m.group(1)) for m in TABLE_PATTERN.finditer(SCHEMA)]
    for i, (start, table) in enumerate(table_starts):
        end = table_starts[i + 1][0] if i + 1 < len(table_starts) else len(SCHEMA)
        block = SCHEMA[start:end]
        for col, values_raw in CHECK_PATTERN.findall(block):
            expected = {v.strip().strip("'") for v in values_raw.split(",")}
            actual = {row[0] for row in conn.execute(f'SELECT DISTINCT "{col}" FROM {table}').fetchall()}
            missing = expected - actual
            if missing:
                gaps.append(f"{table}.{col} missing values: {sorted(missing)}")
    return gaps


def main() -> None:
    # Build into a scratch file first — if DB_PATH is open in a SQLite GUI
    # (DB Browser for SQLite, etc.) it may be locked for writing, so build
    # somewhere safe and only then try to swap it into place.
    build_path = DB_PATH.with_name(DB_PATH.stem + ".rebuild.db")
    if build_path.exists():
        build_path.unlink()

    conn = sqlite3.connect(build_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(SCHEMA)
    seed(conn)

    bad_fks = conn.execute("PRAGMA foreign_key_check;").fetchall()
    if bad_fks:
        raise SystemExit(f"Foreign key violations found: {bad_fks}")

    gaps = check_enum_coverage(conn)
    if gaps:
        print("Enum coverage gaps found:")
        for g in gaps:
            print(f"  MISSING: {g}")
        raise SystemExit(1)

    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;"
    )]
    total = 0
    counts = []
    for t in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        total += count
        counts.append((t, count))
    conn.close()

    try:
        os.replace(build_path, DB_PATH)
        final_path = DB_PATH
    except PermissionError:
        final_path = build_path
        print(f"NOTE: {DB_PATH.name} is locked (likely open in a SQLite GUI viewer).")
        print(f"      Close it there, then rename {build_path.name} -> {DB_PATH.name}.")

    print(f"Built {final_path} with {len(tables)} tables (full enum coverage verified):")
    for t, count in counts:
        print(f"  {t:38s} {count:3d} rows")
    print(f"  {'TOTAL':38s} {total:3d} rows")


if __name__ == "__main__":
    main()
