import datetime

from django.db import migrations
from django.utils import timezone

# PRI's events as supplied by the owner (2026-10-12), loaded once so production gets them in full. Two of them were
# already entered by hand with the details pasted into `summary`, garbled quotes, and one date read as MM/DD (the
# Androth lecture was on 4 December 2025, not 12 April); those rows are updated in place and keep their images.
# Staff edit everything afterwards in the dashboard.
EVENTS = [
    {
        "slug": "sir-update-today-decide-tomorrow-2025",
        "title": "SIR: “Update Today, Decide Tomorrow”",
        "summary": (
            "A session for students at MES Mampad College on the Special Intensive Revision (SIR) of electoral "
            "rolls, with the Electoral Literacy Club and the Aikhya Students’ Union."
        ),
        "start_date": datetime.date(2025, 11, 2),
        "start_time": datetime.time(11, 0),
        "end_time": None,
        "date_note": "",
        "location": "MES Mampad College",
        "mode": "in_person",
        "collaborators": ["Electoral Literacy Club", "Aikhya Students’ Union"],
        "speakers": ["Lead speaker: Muhammed Thufail"],
        "focus_areas": [
            "Understanding the Special Intensive Revision (SIR) of electoral rolls",
            "The legal framework governing voter enrollment and statutory procedures",
            "The role of youth and student communities in democratic processes",
            "Empowering students to engage actively and responsibly with democratic institutions",
        ],
    },
    {
        "slug": "political-data-intelligence-in-the-digit",
        "title": "Political Data Intelligence in the Digital Age",
        "summary": (
            "An online lecture for the Department of Political Science, Government College of Arts & Science, "
            "Androth, on how data and digital tools can strengthen governance and public policy."
        ),
        "start_date": datetime.date(2025, 12, 4),
        "start_time": datetime.time(10, 30),
        "end_time": None,
        "date_note": "",
        "location": "Department of Political Science, Government College of Arts & Science, Androth, Lakshadweep",
        "mode": "online",
        "collaborators": [
            "Department of Political Science, Government College of Arts & Science, Androth",
        ],
        "speakers": ["Speaker: Muhammed Thufail", "Presided by: Dr. Anees Vavad"],
        "focus_areas": [
            "Digital transformation in governance and institutional accountability",
            "Big data analytics for public policy, demographic and socioeconomic research",
            "Strengthening democratic institutions through accessible technological tools",
            "Ethical data systems, algorithmic transparency and citizen empowerment",
        ],
    },
    {
        "slug": "kerala-demographic-conclave-2026",
        "title": "Kerala Demographic Conclave: Navigating Population Transition and Policy Realities",
        "summary": (
            "A one-day conclave in Thiruvananthapuram on Kerala’s population transition and what it means for "
            "policy, bringing together demographers, economists, sociologists, public finance specialists and "
            "municipal administrators."
        ),
        # The exact day isn't fixed yet; this keeps it ordered and upcoming, and the note is what visitors see.
        "start_date": datetime.date(2026, 12, 14),
        "start_time": datetime.time(9, 30),
        "end_time": datetime.time(17, 0),
        "date_note": "December 2026 (3rd or 4th week)",
        "location": "Thiruvananthapuram",
        "mode": "hybrid",
        "collaborators": ["State planning bodies", "University departments", "Research institutions"],
        "speakers": [
            "Key participants: Demographers, development economists, sociologists, public finance specialists "
            "and municipal administrators",
        ],
        "focus_areas": [
            "Demographic transition: Fertility declines across communities, and longitudinal trends in Census, "
            "SRS and CRS registries",
            "Dual-pressure age structure: Policies for youth human capital development alongside social security, "
            "pensions and elder-care infrastructure",
            "Population sensitivity in fiscal planning: Equitable municipal allocation models that account for age "
            "structures, dependency ratios and migration",
            "Long-term population projections: Cohort-component projections through 2045 to inform future "
            "investment in education, health and urban infrastructure",
            "Evidence-based public discourse: Countering demographic misinformation with empirical, open-access "
            "population datasets",
        ],
    },
    {
        "slug": "legislative-leadership-forum-2026",
        "title": "Legislative Leadership Forum: Good Governance & Constituency Development",
        "summary": (
            "A forum for the IUML Legislative Party at SAFI College, Vazhayur, on good governance and constituency "
            "development, with full technical and analytical support from PRI."
        ),
        "start_date": datetime.date(2026, 10, 3),
        "start_time": datetime.time(8, 0),
        "end_time": datetime.time(14, 0),
        "date_note": "",
        "location": "SAFI College, Vazhayur",
        "mode": "in_person",
        "collaborators": ["IUML Legislative Party", "SAFI Institutions"],
        "speakers": [
            "Opening remarks: Dr. P. Mohammed Ali Galfar (Chairman Emeritus, SAFI)",
            "Lead presentation: P.M. Riyas",
            "Technical session: PRI Research Team",
            "Closing remarks: P.K. Kunhalikutty (Minister for Industries & AI, Kerala State)",
            "Future plan & follow-up: Sayyid Sadiqali Shihab Thangal (President, IUML Kerala State)",
        ],
        "focus_areas": [
            "Data-driven governance: PRI’s analytical presentation, “Good Governance: Current Dynamics & "
            "Future Prospects – A Data-Based Analysis”",
            "Constituency development blueprints: Turning legislative commitments into measurable local "
            "development roadmaps (“From Promises to Blueprint”)",
            "Evidence-based policy interventions: Equipping legislators and executive leadership with empirical "
            "data tools, regional analytics and governance metrics",
            "Strategic follow-up framework: Actionable legislative priorities, technology adoption and "
            "administrative follow-up mechanisms",
        ],
    },
]


def load_events(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    Event = apps.get_model("events", "Event")
    owner = User.objects.filter(role="admin").order_by("id").first() or User.objects.order_by("id").first()
    now = timezone.now()
    for fields in EVENTS:
        slug = fields["slug"]
        values = {key: value for key, value in fields.items() if key != "slug"}
        existing = Event.objects.filter(slug=slug).first()
        if existing is not None:
            # Update the details only: the image, owner and workflow state stay as staff left them.
            for key, value in values.items():
                setattr(existing, key, value)
            existing.save()
        elif owner is not None:
            # A fresh database without users (tests, a new environment) gets no events; staff add them later.
            Event.objects.create(
                slug=slug, kind="event", status="published", published_at=now, created_by=owner, **values
            )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("events", "0002_event_details_and_gallery"),
    ]

    operations = [migrations.RunPython(load_events, migrations.RunPython.noop)]
