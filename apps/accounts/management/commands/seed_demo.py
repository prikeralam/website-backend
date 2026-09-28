"""Seed a development database with demo users and content so a frontend has something to render.

The content mirrors the PRI website prototype (https://pri-website-pink.vercel.app/): its pages, people,
projects, research data stories and dashboards. Wherever the prototype says "to be supplied" or "to be
confirmed" the seed says the same; a few extra draft/private/gated rows exist only to exercise the
visibility rules. Dataset rows use only figures quoted in the prototype's articles.

Idempotent: rerunning updates the same rows (matched by username or slug) instead of duplicating them.
Refuses to run unless ENVIRONMENT=dev, because it creates accounts with a known password.
"""

import io
import json
import zipfile
from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.models import Role
from apps.content.models import ContentBlock, Document, PersonProfile, Testimonial
from apps.datarepo.models import AccessRequest, Dashboard, Dataset
from apps.projects.models import Project
from apps.publications.models import Publication, PublicationVersion
from apps.taxonomy.models import Theme

User = get_user_model()

SITE = "https://pri-website-pink.vercel.app"
UNSPLASH = "https://images.unsplash.com/photo-1521737604893-d14cc237f11d"
PDF_BYTES = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
TBS = "Biography to be supplied."
# The real Annual Report 2025–26 supplied by PRI; older reports stay placeholders.
ANNUAL_REPORT_2025_26 = Path(__file__).parent / "seed_files" / "annual-report-2025-26.pdf"

# The prototype names no sub-themes; these are the minimum needed for its four data stories and dashboards.
SUB_THEMES = {
    "education": ("higher-secondary", "Higher Secondary"),
    "demography": ("religious-composition", "Religious Composition"),
    "health": ("primary-care", "Primary Care"),
    "migration": ("gulf-migration", "Gulf Migration"),
    "public-finance": ("budget-allocation", "Budget Allocation"),
}

# (slug, title, body, status)
CONTENT_BLOCKS = [
    (
        "hero",
        "Data-driven research. Evidence-based policy.",
        "Strategy and collaboration that turn rigorous research into real-world policy impact — "
        "for a more equitable society.",
        "published",
    ),
    (
        "organization-statement",
        "About PRI",
        "A dedicated think tank committed to promoting inclusive development, social justice, and national "
        "integration through data-driven research and evidence-based policy advocacy.",
        "published",
    ),
    (
        "who-we-are",
        "Who we are",
        "PRI brings together researchers, policymakers, community leaders, and civil society representatives to "
        "address socio-economic and political disparities, ensuring equal opportunities and fair representation.",
        "published",
    ),
    (
        "our-vision",
        "Our Vision",
        "To create a society where every individual has equitable access to opportunities and resources. We "
        "envision an empowered society where all people can actively engage in socio-economic and political "
        "processes, fostering a culture of equity, inclusion, and mutual respect.",
        "published",
    ),
    (
        "our-mission",
        "Our Mission",
        "Conduct rigorous, data-driven research to identify and outline systemic inequalities.\n"
        "Develop evidence-based policies and recommendations to address issues and problems.\n"
        "Engage in strategic advocacy efforts with policymakers and key stakeholders.\n"
        "Empower decision-makers and the public through knowledge sharing and capacity building.",
        "published",
    ),
    (
        "contact-details",
        "Contact",
        "West Kodur, Kodur PO, Malappuram Dt, Kerala, India 676504\n"
        "contact@priresearch.in\n+91 96052 21921\n"
        "Reg. No.: MPM/CA/204/202512A; AAOAP9667ME2025180G; AAOAP9667MF20251",
        "published",
    ),
    ("annual-plan-2027", "Annual Plan 2027", "Demo row: awaiting editorial review.", "in_review"),
    ("homepage-banner-draft", "Homepage Banner", "Demo row: a draft nobody but its author should see.", "draft"),
]

# (name, role_title, photo file under /people/team/)
TEAM = [
    ("Dr. Noushad T", "Director of Operations", "noushad.jpg"),
    ("Muhammed Thufail", "Head of Data", "thufail.jpg"),
    ("Dr. Afsal K", "Researcher", "afsal.jpg"),
    ("Sayyid Hashir", "Editor", "hashir.png"),
    ("Badusha", "Content Writer", "badusha.png"),
    ("Muhammed Sinan", "Web Manager", "muhammed-sinan.png"),
    ("Rashiq", "Data Analyst", "rashiq.jpg"),
]
# (name, photo file under /people/patrons/)
PATRONS = [("PK Kunjalikkutty", "pk-kunjalikkutty.jpg"), ("Galfar Mohammed Ali", "galfar-mohammed-ali.jpg")]
# (name, role_title, photo file under /people/executive/, or None where PRI has not supplied one)
EXECUTIVE = [
    ("Sayyid Sadiq Ali Shihab", "Chairman", "sayyid-sadiq-ali-shihab.jpg"),
    ("Ahmad Munavvar Puthiya Maliyekkal", "Vice Chairman", "ahmad-munavvar-puthiya-maliyekkal.jpg"),
    ("Sayyid Rasheed Ali Puthiya Maliyekkal", "Treasurer", "sayyid-rasheed-ali-puthiya-maliyekkal.jpg"),
    ("Abubakr T", "Vice President", None),
    ("Dr. Mohammed Haris KT", "General Secretary", "haris-kt.jpeg"),
    ("Muhammed Nazeel NP", "Executive Member", "naseel.jpeg"),
    ("Sayyid Aseel Ali Shihab Thangal", "Executive Member", "sayyid-aseel-ali-shihab-thangal.jpg"),
    ("Sayyid Rajih Ali Shihab Thangal", "Executive Member", "sayyid-rajih-ali-shihab-thangal.jpg"),
    ("Anwar Naha", "Vice Chairman", None),
    ("C.H Abdul Raheem", "Executive Member", "ch-abdul-raheem.jpeg"),
    ("P.A Abdulla Ibrahim", "Executive Member", "pa-abdulla-ibrahim.jpg"),
    ("Abdul Muhaimin Kakkiya", "Executive Member", None),
    ("Dr. Muneer Kalliyil", "Executive Member", "muneer-kalliyil.jpg"),
]
# (name, description, logo file under /people/partners/)
PARTNERS = [
    ("SAFI Group of Institutions", "Description to be supplied.", "safi.jpg"),
    ("CH Mohammed Koya Chair for Studies on Developing Societies", "University of Calicut.", "ch-chair.jpg"),
    ("HADIA Centre for Social Excellence", "Description to be supplied.", "cse.png"),
    ("Mamburam Thangal Institute", "Description to be supplied.", "mamburam-thangal-institute.jpg"),
]

# (slug, title, blurb, status)
PROJECTS = [
    ("sir-project", "SIR Project", "Full project name and description to be confirmed.", "published"),
    (
        "education",
        "Education",
        "Analysing educational access, quality, and outcomes across different communities and regions.",
        "published",
    ),
    (
        "demography-migration",
        "Demography and Migration",
        "Population studies, migration patterns, and diaspora community analysis.",
        "published",
    ),
    ("upcoming-project", "Upcoming Project", "Demo row: a draft that is not announced yet.", "draft"),
]

# (slug, title, theme, tags, abstract)
DATA_STORIES = [
    (
        "malappuram-classrooms",
        "Malappuram's Plus One classrooms are Kerala's most crowded",
        "education",
        ["Education", "Data Story"],
        "The district of Malappuram has the largest average batch sizes in Kerala's Plus One system at 65 "
        "students per batch, nearly double Pathanamthitta's 36, and offers the fewest science stream options.",
    ),
    (
        "kerala-population-mix",
        "Kerala's religious population mix is shifting slowly",
        "demography",
        ["Demography", "Data Story"],
        "Muslims' population share rose from 26.5% (2011) to 29.9% (2024), while Muslim births declined 27% "
        "over the same period.",
    ),
    (
        "kerala-healthcare-gap",
        "Where Kerala's healthcare capacity runs thin",
        "health",
        ["Health", "Data Story"],
        "Kerala's public health system is usually held up as a national model, but broken down by district the "
        "numbers show large gaps in primary care access, hospital beds and doctor availability.",
    ),
    (
        "kerala-gulf-migration",
        "Kerala's migration economy runs through the Gulf",
        "migration",
        ["Migration", "Data Story"],
        "Muslims comprise 41.9% of Kerala's emigrants despite being 29.3% of the population, with 98.5% of "
        "Muslim emigrants concentrated in Gulf destinations.",
    ),
]


def parquet_bytes():
    buffer = io.BytesIO()
    table = pa.table(
        {
            "group": ["Hindus", "Christians", "Muslims"],
            "share_2011": [54.7, 18.3, 26.5],
            "share_2024": [52.0, 17.6, 29.9],
        }
    )
    pq.write_table(table, buffer)
    return buffer.getvalue()


def zip_bytes():
    buffer = io.BytesIO()
    csv = "group,population_share,emigrant_share\nHindus,53.2,35.2\nMuslims,29.3,41.9\nChristians,16.9,22.3\n"
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("emigrants-by-community.csv", csv)
    return buffer.getvalue()


PLUS_ONE_CSV = b"district,average_batch_size\nMalappuram,65\nPathanamthitta,36\nKerala (average),54\n"
PHC_CSV = b"area,people_per_phc\nMalappuram,47051\nPolicy target,3000\n"
PROJECTION_CSV = b"district,projected_plus_one_students_2033\nMalappuram,86106\n"
GEOJSON_BYTES = json.dumps(
    {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"district": "Malappuram", "average_batch_size": 65},
                "geometry": {"type": "Point", "coordinates": [76.0711, 11.0510]},
            },
            {
                "type": "Feature",
                "properties": {"district": "Pathanamthitta", "average_batch_size": 36},
                "geometry": {"type": "Point", "coordinates": [76.7870, 9.2648]},
            },
        ],
    }
).encode()

# (slug, title, format, visibility, status, theme, year, geography, content)
DATASETS = [
    (
        "plus-one-batch-size",
        "Plus One batch size by district",
        "csv",
        "public",
        "published",
        "education",
        2025,
        "Kerala",
        PLUS_ONE_CSV,
    ),
    (
        "religious-composition",
        "Religious composition of Kerala's population",
        "parquet",
        "public",
        "published",
        "demography",
        2024,
        "Kerala",
        parquet_bytes(),
    ),
    (
        "emigrants-by-community",
        "Emigrants by community",
        "zip",
        "public",
        "published",
        "migration",
        None,
        "Kerala",
        zip_bytes(),
    ),
    (
        "plus-one-batch-size-map",
        "Plus One batch size, selected districts (map)",
        "geojson",
        "public",
        "published",
        "education",
        2025,
        "Kerala",
        GEOJSON_BYTES,
    ),
    (
        "phc-load-by-area",
        "People served per PHC (on request)",
        "csv",
        "on_request",
        "published",
        "health",
        None,
        "Malappuram",
        PHC_CSV,
    ),
    (
        "enrolment-projection",
        "Plus One enrolment projection (internal)",
        "csv",
        "internal_only",
        "published",
        "education",
        2033,
        "Malappuram",
        PROJECTION_CSV,
    ),
    ("dataset-in-progress", "Dataset in progress", "csv", "public", "draft", "education", 2025, "Kerala", PLUS_ONE_CSV),
]

# (slug, title, description, theme, status)
DASHBOARDS = [
    (
        "education-access-dashboard",
        "Education access dashboard",
        "Interactive view of enrolment and infrastructure indicators by district",
        "education",
        "published",
    ),
    (
        "public-finance-dashboard",
        "Public finance dashboard",
        "Budget allocation against expenditure, filterable by department",
        "public-finance",
        "published",
    ),
]


class Command(BaseCommand):
    help = "Create demo users (one per role) and sample content from the PRI website prototype. Dev only."

    def add_arguments(self, parser):
        parser.add_argument("--password", default="demo-pass-123", help="Password for every demo user.")

    def handle(self, *args, **options):
        if settings.ENVIRONMENT != "dev":
            raise CommandError(f"seed_demo only runs with ENVIRONMENT=dev (this is {settings.ENVIRONMENT!r}).")

        self.now = timezone.now()
        self.users = self.seed_users(options["password"])
        self.author = self.users[Role.EDITOR]
        self.themes = self.seed_themes()
        research_team = self.seed_people()
        self.seed_content()
        self.seed_publications(research_team)
        datasets = self.seed_datasets()
        self.seed_dashboards(datasets)

        self.stdout.write(self.style.SUCCESS("Demo data ready."))
        self.stdout.write(f"Log in at POST /api/v1/token/ as demo_<role> with password {options['password']!r}:")
        self.stdout.write("  " + ", ".join(f"demo_{role}" for role in self.users))

    def seed_users(self, password):
        users = {}
        for role in Role.values:
            user, _ = User.objects.get_or_create(username=f"demo_{role}", defaults={"email": f"{role}@demo.example"})
            user.role = role
            user.set_password(password)
            user.save()
            users[role] = user
        return users

    def seed_themes(self):
        themes = {}
        for parent_slug, (slug, name) in SUB_THEMES.items():
            parent = Theme.objects.get(slug=parent_slug)
            themes[parent_slug], _ = Theme.objects.get_or_create(slug=slug, defaults={"name": name, "parent": parent})
        return themes

    def upsert(self, model, slug, status="published", file=None, **fields):
        """Create or update one workflowed object; attach `file` = (name, bytes) only the first time."""
        published_at = self.now if status == "published" else None
        obj, _ = model.objects.update_or_create(
            slug=slug,
            defaults={"status": status, "published_at": published_at, "created_by": self.author, **fields},
        )
        if file and not obj.file:
            obj.file.save(file[0], ContentFile(file[1]))
        return obj

    def person(self, name, role_title, group, bio=TBS, photo_url="", status="published"):
        return self.upsert(
            PersonProfile,
            slugify(name)[:50].strip("-"),  # SlugField max_length is 50
            status,
            name=name,
            role_title=role_title,
            group=group,
            bio=bio,
            photo_url=photo_url,
        )

    def seed_people(self):
        for name, title, photo in TEAM:
            self.person(name, title, "team", photo_url=f"{SITE}/people/team/{photo}")
        for name, photo in PATRONS:
            self.person(name, "Patron", "patron", photo_url=f"{SITE}/people/patrons/{photo}")
        for name, title, photo in EXECUTIVE:
            self.person(name, title, "executive", photo_url=f"{SITE}/people/executive/{photo}" if photo else "")
        for number in range(1, 11):
            self.person(f"Advisory Member {number}", "Advisory Body", "advisory")
        for name, description, logo in PARTNERS:
            self.person(
                name, "Partner institution", "partner", bio=description, photo_url=f"{SITE}/people/partners/{logo}"
            )
        self.person("Draft Profile", "Analyst", "team", bio="Demo row: a draft profile.", status="draft")
        return self.person("PRI Research Team", "Research team", "author", bio="Authors of PRI's data stories.")

    def seed_content(self):
        for slug, title, body, status in CONTENT_BLOCKS:
            self.upsert(ContentBlock, slug, status, title=title, body=body)

        self.upsert(
            Testimonial,
            "testimonial-placeholder",
            quote="Testimonial to be supplied.",
            attribution="Placeholder",
            role="Stakeholder",
        )
        self.upsert(
            Testimonial,
            "testimonial-draft",
            "draft",
            quote="Demo row: not approved yet.",
            attribution="Placeholder",
            role="Stakeholder",
        )

        for slug, title, blurb, status in PROJECTS:
            self.upsert(
                Project,
                slug,
                status,
                title=title,
                blurb=blurb,
                image_url=UNSPLASH,
                cta_label="Explore project",
                cta_href=f"/projects/{slug}",
            )

        for slug, title, year, status, pdf in [
            ("annual-report-2025-26", "Annual Report 2025–26", 2026, "published", ANNUAL_REPORT_2025_26.read_bytes()),
            ("annual-report-2024-25", "Annual Report 2024–25", 2025, "published", PDF_BYTES),
            ("internal-memo", "Internal Memo", 2026, "draft", PDF_BYTES),
        ]:
            self.upsert(
                Document,
                slug,
                status,
                file=(f"{slug}.pdf", pdf),
                title=title,
                document_type="memo" if status == "draft" else "annual-report",
                year=year,
            )

    def seed_publications(self, research_team):
        rows = [
            (slug, title, theme, tags, abstract, "published", "public")
            for slug, title, theme, tags, abstract in DATA_STORIES
        ]
        rows += [
            (
                "partner-briefing",
                "Partner briefing (private demo)",
                "education",
                ["Demo"],
                "Demo row: published but private, visible only to staff and its creator.",
                "published",
                "private",
            ),
            (
                "report-in-progress",
                "Report in progress (draft demo)",
                "education",
                ["Demo"],
                "Demo row: a draft.",
                "draft",
                "public",
            ),
        ]
        for slug, title, theme, tags, abstract, status, visibility in rows:
            publication = self.upsert(
                Publication,
                slug,
                status,
                title=title,
                abstract=abstract,
                format="data_story" if "Data Story" in tags else "report",
                sub_theme=self.themes[theme],
                language="en",
                date=date(2026, 3, 1),  # the prototype says "To be confirmed"
                visibility=visibility,
                tags=tags,
            )
            publication.authors.set([research_team])
            version, created = PublicationVersion.objects.get_or_create(
                publication=publication,
                version_number=1,
                defaults={"uploaded_by": self.author, "is_current": True},
            )
            if created:
                version.file.save(f"{slug}-v1.pdf", ContentFile(PDF_BYTES))

    def seed_datasets(self):
        datasets = {}
        for slug, title, fmt, visibility, status, theme, year, geography, content in DATASETS:
            datasets[slug] = self.upsert(
                Dataset,
                slug,
                status,
                file=(f"{slug}.{fmt}", content),
                title=title,
                description=f"{title}. Figures as quoted in PRI's published data stories.",
                format=fmt,
                sub_theme=self.themes[theme],
                geography=geography,
                year=year,
                source="PRI Research Team",
                visibility=visibility,
            )
        AccessRequest.objects.get_or_create(user=self.users[Role.PUBLIC], dataset=datasets["phc-load-by-area"])
        return datasets

    def seed_dashboards(self, datasets):
        for slug, title, description, theme, status in DASHBOARDS:
            dashboard = self.upsert(
                Dashboard,
                slug,
                status,
                title=title,
                description=description,
                embed_url=f"https://example.org/embed/{slug}",  # placeholder: the prototype embeds nothing yet
                embed_type="datawrapper",
                theme=Theme.objects.get(slug=theme),
                geography="Kerala",
                type="overview",
            )
            dashboard.datasets.set([datasets["plus-one-batch-size"]] if theme == "education" else [])
