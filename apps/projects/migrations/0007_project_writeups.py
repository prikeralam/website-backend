from django.db import migrations

# PRI's three project write-ups as supplied by the owner (2026-10-12), loaded once so production gets them in full.
# The projects already exist (seeded with placeholder titles and blurbs), so they are updated in place by slug and keep
# their images; a missing one is skipped. Edits from the source: "Policy Research Institute" corrected to "Policy and
# Research Initiative", em dashes rewritten (ranges use a hyphen), and section numbers dropped since the page numbers
# them. Staff edit everything afterwards in the dashboard. The format of `details` is described on Project.details.
PROJECTS = {
    "sir-project": {
        "title": "Special Intensive Revision (SIR) Initiative",
        "blurb": (
            "SIR Watch Kerala: a statewide civic initiative, coordinated by PRI, that safeguarded electoral rights "
            "during the Election Commission's Special Intensive Revision of electoral rolls."
        ),
        "stage": "completed",
        "facts": [
            "Project duration: November 2025 - February 2026",
            "Coordinating platform: SIR Watch Kerala",
            "Executive steering: Syed Rasheed Ali Shihab Thangal (Chairman), C.H. Abdul Rahim (Convenor)",
        ],
        "details": """\
Following a resolution adopted at the Policy and Research Initiative (PRI) Executive Committee meeting on 29 October 2025, a statewide civic coordination initiative was launched to safeguard electoral rights during the Election Commission’s Special Intensive Revision (SIR) process. Acting on recommendations from the expert Empower Committee chaired by Gulfaar Muhammed Ali, a consultative assembly of prominent civil society figures, community leaders, and social organizations convened on 15 November 2025 in Kozhikode under the chairmanship of Panakkad Syed Sadiqali Shihab Thangal.

The conference resolved to form a unified civic monitoring initiative titled “SIR Watch Kerala.” PRI was designated as the primary technical, monitoring, and administrative coordinating body. The initiative focused on voter verification, grassroots capacity building, non-resident citizen (NRI) voter facilitation, legal safeguards, and public grievance redressal across Kerala and overseas diasporic communities.

## Governance & Grassroots Coordination

- **Leadership & Strategy:** A high-level sub-committee led by Chairman Syed Rasheed Ali Shihab Thangal and Convenor C.H. Abdul Rahim was constituted to steer field activities.
- **Weekly Review Rhythm:** The sub-committee convened weekly online evaluation sessions every Friday through January 2026 to track performance and adapt field strategies.
- **District & Constituency Network:** Multi-organizational coordination units were formed across all 14 revenue districts. Action frameworks were distributed to district coordinators to manage booth-level monitoring, voter verification, and data collation.
- **Review Conferences:** A structured progress review was conducted on 18 November 2025 at MSS Hall, Kozhikode, followed by comprehensive state-level evaluation sessions on 12 December and 15 December 2025 at Panakkad Hadiya Centre, where progress notes were presented by Dr. Haris K.T. and operational roadmaps were ratified.

## Central War Room & Citizen Help Line

- **State Secretariat:** A dedicated three-month administrative office and central War Room were set up at Palayam, Kozhikode. The space was furnished and outfitted with high-speed internet, computing terminals, and dedicated workstations.
- **Multi-Line Citizen Help Desk:** A centralized multi-channel telephonic Help Line, capable of routing incoming calls to three operators simultaneously, was established to clarify procedures and resolve registration grievances.
- **Operational Staffing:** A team of trained interns and volunteer coordinators was recruited through structured interviews to manage daily desk operations and public queries.

## Technical Support, Research & Legal Cell

- **Legal Cell:** A dedicated legal advisory wing headed by High Court advocate Adv. Muhammad Shah was constituted to evaluate statutory frameworks, protect franchise rights, and draft formal representations.
- **Election Commission Interventions:** The technical wing formulated comprehensive briefing papers and technical notes for civil representation during statutory discussions with Election Commission authorities.
- **Overseas Voter Relief:** Sustained representations and technical advocacy played a key role in addressing critical NRI documentation bottlenecks, successfully prompting the Election Commission to facilitate streamlined online submissions for overseas voters.
- **ASD Scrutiny:** Field teams carried out systematic, booth-level audits of Absent, Shifted, and Dead (ASD) voter lists to prevent wrongful disenfranchisement.

## Public Awareness & Civic Outreach

- **Information Collateral:** Designed and distributed over 40 structured infographics, instructional flyers, and educational videos across digital platforms explaining form-filling steps and resolving voter verification ambiguities.
- **Civic Mobilization:** Drafted informational circulars, analytical press releases, civic guidance notes, and awareness materials for dissemination via grassroots community channels and Friday congregational addresses.
- **Specialized Expatriate Outreach:** Coordinated outreach channels across GCC countries through partner diaspora associations. The inaugural Gulf-region plenary was hosted in Kuwait, alongside specialized virtual coordination clinics across the UAE, ensuring seamless registration for non-resident citizens.

## Capacity Building, Training & People’s Voter List Campaign

- **Field Training Workshops:** Between December 2025 and January 2026, PRI’s resource team conducted over 20 hands-on training workshops for civic volunteers and regional functionaries across Kannur, Malappuram, Palakkad, Mannarkkad, Pulpatta, Guruvayur, Manjeri, and Kozhikode.
- **Curriculum Focus:** Modules covered voter enrollment procedures, statutory form verification, ASD list audits, overseas voter facilitation, and legal remediation.
- **People’s Voter List Drive:** An action plan formulated in late December 2025 and finalized on 5 January 2026 culminated in a synchronized statewide field campaign on 10 January 2026 across municipalities and grama panchayaths. Technical data processing was supported by Spine Code Technologies, while district teams completed constituency-wide reconciliations by mid-January 2026.

## Project Outcomes

Through this institutionalized multi-tier intervention, the SIR Watch Kerala initiative ensured:

- Systematic protection of eligible voters against arbitrary exclusions in the revised electoral rolls.
- Direct resolution of thousands of public queries through the central Kozhikode War Room and Help Line.
- Expanded digital participation for non-resident Keralite citizens through timely policy representations.
- An informed, active grassroots civic network across the state capable of safeguarding electoral democracy.
""",
    },
    "education": {
        "title": "Education Data & Research Initiative",
        "blurb": (
            "A research programme that joins Kerala's public education datasets into one pipeline and turns them "
            "into evidence for policy, from Plus One seat allocation to higher education demand."
        ),
        "stage": "ongoing",
        "facts": [
            "Initiative lead: Policy and Research Initiative (PRI)",
            "Core domain: Education Policy, Empirical Analytics, and Regional Development",
        ],
        "details": """\
The Education Data Initiative is an ongoing research program aimed at strengthening evidence-based policy formulation in Kerala’s education ecosystem. By establishing a unified data pipeline that bridges administrative and school-level databases, the initiative translates disparate public educational datasets into actionable policy analytics.

The project operates across two complementary tracks: foundational data architecture development and targeted empirical policy investigations addressing structural bottlenecks in secondary and higher education.

## Foundational Architecture & Infrastructure

### Research Capacity & Human Resources

To drive rigorous statistical governance, econometric modeling, and automated data architecture, a dedicated empirical research track was instituted in 2025-2026.

- **Head Consultant:** Dr. Muneer Kalliyil (Indian Institute of Management Bangalore) steers the research methodology, econometric framework, and strategic policy translations for the observatory.
- **Quantitative Data Fellow / Intern:** Muhammed Sinan (Delhi School of Economics) leads the engineering workflow, managing automated data ingestion, cleaning pipelines, spatial dataset harmonizations, and statistical modeling.

### Multi-Source Data Ingestion & Harmonization

Data has been systematically extracted, cleaned, standardized, and merged across two core public repositories:

- **Unified District Information System for Education Plus (UDISE+):** National indicators capturing school category, management type, basic physical infrastructure, lab accessibility, pupil-teacher ratios (PTR), and social demographic profiles.
- **KITE Sametham (Kerala School Data Bank):** State-level administrative figures providing granular school-by-school batch compositions, stream allotments, and real-time student enrollment data.

Cross-database identifiers were harmonized into a standardized panel covering three core dimensions: enrollment trends, physical and digital infrastructure, and learning/academic performance metrics.

### State Education Analytics Dashboard

An interactive public policy and research dashboard is currently under active technical development to present:

- **School & District Profiles:** Standardized metric cards displaying cohort sizes, physical facilities, classroom capacity, and stream distributions.
- **Longitudinal Trend Analytics:** Multi-year tracking of pass percentages, retention patterns, and transition ratios from lower secondary to higher secondary levels.
- **Comparative Disparity Metrics:** Spatial mapping highlighting intra-district and inter-district imbalances in student-classroom ratios and seat availability.
- **Policy Visualization Engine:** Data layers built for researchers, administrative bodies, and civic stakeholders to model demographic shifts and evaluate capacity requirements.

## Targeted Empirical Studies & Implementation Roadmaps

Alongside core data infrastructure, PRI has launched three priority research projects targeting regional disparities and educational transitions.

### Project I: District-Wise Higher Secondary Enrollment Trends & Malabar Seat Allocation Framework

- **Problem Statement:** Significant disparities persist between Class 10 qualification rates and sanctioned Plus One higher secondary seats, particularly across northern Kerala districts (Malappuram, Kozhikode, Palakkad, Kannur, Wayanad, and Kasaragod), resulting in localized seat crunches and oversized batches.
- **Objective:** Conduct granular demographic and enrollment modeling to provide statutory authorities with actionable, data-backed seat and batch reallocation frameworks.

### Project II: “Where Do Our Boys Go?” Post-Secondary Male Attrition Study

- **Problem Statement:** Secondary completion figures indicate a noticeable gender divergence in higher education transitions, characterized by higher dropout rates or non-enrollment among young men moving from higher secondary schooling to conventional degree programs.
- **Objective:** In coordination with the Malappuram District Panchayath, evaluate the socio-economic and structural drivers of post-10+2 male attrition and map alternative trajectory pathways (e.g., informal migration, gig economy, unaccredited vocational training).

### Project III: Supply-Demand Dynamics in Kerala Higher Education (UG & PG Programs)

- **Problem Statement:** Higher education institutions in Kerala frequently experience seat vacancies in legacy degree programs alongside severe application surpluses in emerging interdisciplinary fields, reflecting a structural mismatch between university offerings and contemporary workforce realities.
- **Objective:** Build an empirical demand-supply diagnostic of undergraduate and postgraduate seats across state universities to align academic capacity with demographic trends and evolving student demand.

## Expected Policy Outputs & Deliverables

- **State Education Analytics Dashboard:** A live, publicly accessible visualization portal for educational data discovery and research.
- **Policy Brief on Regional Secondary Education Parity:** Evidence-based proposals for higher secondary seat reallocation and batch creation in northern districts.
- **District Action Plan on Post-Secondary Retention:** A targeted strategy memo designed for local self-government institutions to mitigate male dropouts.
- **Higher Education Demand-Supply Index:** A systemic roadmap for university administrators to optimize undergraduate and postgraduate course allocations based on actual student demand.
""",
    },
    "demography-migration": {
        "title": "Kerala Demographic Observatory & Applied Population Research Initiative",
        "blurb": (
            "An ongoing research programme on Kerala's population transition: fertility, ageing, migration and "
            "spatial change, studied from census, survey and ward-level data to inform public planning."
        ),
        "stage": "ongoing",
        "facts": [
            "Initiative lead: Policy and Research Initiative (PRI)",
            "Core domain: Applied Demography, Spatial Analytics, and Public Policy Planning",
        ],
        "details": """\
Kerala is undergoing a profound demographic transition marked by sub-replacement fertility rates, rapid population aging, significant youth out-migration, and emerging regional variances in age-dependency ratios. When public discourse on demographic change becomes detached from empirical data, speculative narratives often emerge, skewing social policy and budget priorities.

The Kerala Demographic Observatory is an ongoing, data-intensive research program established to examine these population dynamics through rigorous, scientific methodology. By integrating national survey archives, longitudinal administrative registries, and micro-level municipal datasets, the initiative provides municipal authorities, state planning bodies, and researchers with objective demographic intelligence to support equitable public investments, social security design, and urban governance.

## Data Repositories & Analytical Infrastructure

The initiative maintains an integrated data architecture that synthesizes large-scale public registries, national survey rounds, and localized micro-data.

### Micro-Data Engineering

To study spatial concentration and local access to civic infrastructure, an empirical baseline was compiled using anonymized, ward-level records covering 28.2 million residents across all local self-government institutions in Kerala.

### Algorithmic Classification Framework

Using an in-house machine learning classification model developed to evaluate demographic compositions from anthroponymic (naming) structures and auxiliary spatial indicators, the team mapped baseline population characteristics across wards with high statistical consistency.

### Harmonized Secondary Survey Archives

Datasets have been cross-tabulated across multiple longitudinal sources, including:

- Decennial Census records for historical population pyramids and labor-force metrics.
- The Sample Registration System (SRS) from 1971 onward for fertility and mortality trajectories.
- The Civil Registration System (CRS) for real-time tracking of annual births and deaths.
- National Family Health Survey (NFHS) rounds I through V.
- The Longitudinal Ageing Study in India (LASI) for geriatric health and economic dependence.
- National Sample Survey Office (NSSO) socioeconomic series.

## Core Research Verticals

### Vertical I: Demographic Transition & Empirical Population Projections

- **Universal Fertility Trajectories:** Documenting longitudinal fertility transitions to demonstrate that declining fertility and birth rates reflect state-wide socioeconomic advancement, higher educational attainment, and healthcare access across all social groups and regions, rather than the isolated behavior of any single community.
- **Cohort-Component Projections:** Generating district-level, age-cohort projections through 2045 to anticipate shifts in school-age cohorts, prospective labor-force entrants, and elderly dependency metrics.
- **Family Demography:** Tracking structural changes in household composition, age at marriage, inter-community unions, and widowhood survivorship.

### Vertical II: Age-Structure Bifurcation & The Care Economy

- **The Dual-Pressure Matrix:** Addressing the simultaneous policy demands of a shrinking young/school-age cohort alongside an accelerating elderly cohort (60+ years).
- **Geriatric Infrastructure Planning:** Mapping district-wise deficits in long-term elder-care facilities, palliative care networks, public pensions, and age-friendly civic infrastructure.
- **Youth Human Capital & Retention:** Assessing district-level variances in youth unemployment, underemployment, and skill matching to formulate policy recommendations that retain skilled talent within the state.

### Vertical III: Spatial Demography, Urbanization & Delimitation Studies

- **Boundary Delimitation Analysis:** Examining the demographic and spatial effects of local body and administrative ward delimitations on civic equity, urban governance, and fair democratic representation.
- **Urban Density & Resource Allocation:** Investigating whether rapid peri-urbanization, shifting municipal borders, and high-density settlements (such as urban informal settlements and marginalized clusters) experience structural under-representation or public expenditure deficits.
- **Population-Sensitive Fiscal Planning:** Formulating objective formulas for municipal grant distributions that balance crude population headcounts with localized age structures, migration outflows, and dependency burdens.

### Vertical IV: Migration Dynamics & Labor Mobility

- **Migration Patterns:** Tracking internal labor migration into Kerala alongside outward emigration toward West Asia and OECD nations.
- **Skill-Labor Linkages:** Evaluating the alignment between higher education outputs, vocational training certifications, and international employment demands.
- **Remittance Economics & Household Welfare:** Studying remittance utilization channels, household consumption patterns, the structural concerns of returnees, and the specific needs of left-behind families.
- **Mobility Cost Economics:** Undertaking empirical assessments of migration transaction costs (including recruitment fees, credential recognition, travel, and health clearances) to inform supportive diaspora policies.

## The Kerala Demographic Conclave

As part of its dissemination and stakeholder-engagement agenda, PRI plans to convene the Kerala Demographic Conclave, an institutional forum designed to bring academic rigor to public conversations on population change.

- **Format & Participation:** An annual symposium bringing together demographers, development economists, sociologists, public finance specialists, municipal administrators, and research scholars.
- **Primary Objective:** Establish a verified, data-grounded demographic baseline to reduce misinformation, dispel population-based social anxiety, and inform long-term development policy.
- **Deliverables:** An edited proceedings volume, policy working papers, and evidence-based submissions to state planning bodies.

### Core Themes

- **Kerala’s Long-Term Fertility and Mortality Trajectories:** Demonstrating broad-based transition trends across regions and communities.
- **Economic Policy for a Dual-Demographic Age Structure:** Balancing youth employment creation with social security and healthcare for an aging society.
- **Demographic Weighting and Spatial Justice in Budget Allocations:** Integrating dependency ratios and localized needs into municipal funding frameworks.
- **Forward-Looking Population Projections for Public Service Capacity:** Planning future school, healthcare, and urban infrastructure based on projected cohort sizes.
""",
    },
}


def load_writeups(apps, schema_editor):
    Project = apps.get_model("projects", "Project")
    for slug, fields in PROJECTS.items():
        Project.objects.filter(slug=slug).update(**fields)


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0006_project_facts_details"),
    ]

    operations = [
        migrations.RunPython(load_writeups, migrations.RunPython.noop),
    ]
