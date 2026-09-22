"""Server-side citation export (BibTeX/RIS/APA), generated on request from a
Publication's structured metadata — never stored, so metadata edits immediately
reflect in exports. See docs/api/module-b-publications.md and
docs/PRDs/B-publication-repository-module.md:31.
"""


def _author_names(publication):
    return [author.name for author in publication.authors.all()]


def _cite_key(publication):
    return publication.external_id or publication.slug


def to_bibtex(publication):
    authors = " and ".join(_author_names(publication))
    entry_type = "misc" if publication.format != "report" else "techreport"
    return (
        f"@{entry_type}{{{_cite_key(publication)},\n"
        f"  title = {{{publication.title}}},\n"
        f"  author = {{{authors}}},\n"
        f"  year = {{{publication.date.year}}},\n"
        f"  institution = {{Policy and Research Initiative}},\n"
        f"  note = {{{publication.get_format_display()}}}\n"
        f"}}"
    )


def to_ris(publication):
    lines = ["TY  - RPRT"]
    for name in _author_names(publication):
        lines.append(f"AU  - {name}")
    lines.append(f"TI  - {publication.title}")
    lines.append(f"PY  - {publication.date.year}")
    lines.append("PB  - Policy and Research Initiative")
    if publication.external_id:
        lines.append(f"ID  - {publication.external_id}")
    lines.append("ER  - ")
    return "\n".join(lines)


def to_apa(publication):
    authors = ", ".join(_author_names(publication)) or "Policy and Research Initiative"
    return f"{authors} ({publication.date.year}). {publication.title}. Policy and Research Initiative."


FORMATTERS = {
    "bibtex": to_bibtex,
    "ris": to_ris,
    "apa": to_apa,
}
