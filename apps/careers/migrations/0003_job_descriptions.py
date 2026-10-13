from django.db import migrations

# Short role descriptions for the two rolling openings created by 0002, written at the owner's request (2026-10-13)
# as a starting point for staff to edit in the dashboard. Only an empty description is filled, so anything staff
# have written stays. The frontend renders "## " as a heading, "- " as a bullet and **bold**.
DESCRIPTIONS = {
    "research-associate": """\
## What you'll do
- Design and carry out data-driven studies on Kerala's education, demography, migration, health and governance.
- Work with census, survey and administrative data, from cleaning to analysis.
- Write reports, policy briefs and data stories for PRI's publications and public platforms.
- Support PRI's events, stakeholder consultations and field research.

## What we look for
- A master's degree (or equivalent experience) in economics, public policy, development studies, sociology, statistics or a related field.
- Comfort with quantitative analysis in R, Stata or Python.
- Clear writing in English; Malayalam is an advantage.
- Curiosity about Kerala's social and economic questions.""",
    "data-analyst": """\
## What you'll do
- Collect, clean and harmonise public datasets such as UDISE+, the Census, NFHS and state administrative records.
- Build reproducible analysis pipelines and maintain the datasets in PRI's public data repository.
- Produce charts, maps and dashboards for PRI's research and data stories.
- Document sources, methods and metadata so others can reuse the data.

## What we look for
- A degree in statistics, economics, data science, computer science or a related field.
- Strong skills in Python or R, and SQL; experience with spatial data (GIS) is an advantage.
- Experience with data visualisation tools such as Plotly, D3, Tableau or Datawrapper.
- Care for accuracy and clear documentation.""",
}


def add_descriptions(apps, schema_editor):
    JobOpening = apps.get_model("careers", "JobOpening")
    for slug, description in DESCRIPTIONS.items():
        JobOpening.objects.filter(slug=slug, description="").update(description=description)


class Migration(migrations.Migration):
    dependencies = [("careers", "0002_initial_openings")]

    operations = [migrations.RunPython(add_descriptions, migrations.RunPython.noop)]
