"""Seed script -- creates admin user, org profile, and initial sources."""
import os
import sys
import logging

sys.path.insert(0, os.path.dirname(__file__))
import config  # noqa: E402

from n3tx_core.storage.sqlite_storage import SQLiteStorage  # noqa: E402
from n3tx_core.utils.registrar import register_model  # noqa: E402
from n3tx_agents.actor import AgentActor  # noqa: E402
from n3tx_agents.tool_model import AgentTool  # noqa: E402
from models import User, Organization, Source, Grant  # noqa: E402

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')
logger = logging.getLogger('veille.seed')

_HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_HERE, config.SQLITE_DB_FILE)


def seed():
    storage = SQLiteStorage(DB_PATH)
    register_model(User, storage=storage)
    register_model(Organization, storage=storage)
    register_model(Source, storage=storage)
    register_model(Grant, storage=storage)
    register_model(AgentTool, storage=storage)
    register_model(AgentActor, storage=storage)

    # Admin user
    admin = User(name='Admin', email='admin@veille.local')
    admin._plain_password = 'admin123'
    admin.role = 'admin'
    User.create(admin)
    logger.info("Created admin user: admin@veille.local / admin123")

    # Organization profile (singleton -- only one record should exist)
    org = Organization(
        name='Federation franco-tenoise',
        mission='Represent, defend, and promote the rights of francophones in the Northwest Territories.',
        activities='Political advocacy, community development, immigration services, EDI initiatives.',
        legal_status='Registered non-profit',
        province='Northwest Territories',
        charitable_status='Not-for-profit corporation',
        employee_count=15,
        annual_budget=500000.0,
        focus_areas=[
            'Francophone minority services',
            'Health services in French',
            'Immigration and integration',
            'Community development',
            'Equity, diversity, inclusion',
        ],
        custom_criteria={
            'geographic_focus': 'Northwest Territories, Canada',
            'language_focus': 'French and bilingual',
            'target_population': 'Francophone minority community',
        },
    )
    Organization.create(org)
    logger.info("Created organization profile: FFT")

    # Initial scraping sources
    sources = [
        {
            'name': 'Friendly Future Foundation',
            'url': 'https://www.friendlyfuture.com/en/foundation/apply-for-funding',
            'description': 'Private foundation funding for community projects.',
            'language': 'en',
        },
        {
            'name': 'CCNDR',
            'url': 'https://ccndr.ca/',
            'description': 'National centre for community development resources.',
            'language': 'fr',
        },
        {
            'name': 'NRC Outreach Initiative',
            'url': 'https://nrc.canada.ca/en/support-technology-innovation/outreach-initiative-grants-contributions-program',
            'description': 'Federal government grants and contributions program.',
            'language': 'en',
        },
        {
            'name': 'OIF Appels a projets',
            'url': 'https://www.francophonie.org/appels-projets-candidatures-initiatives-1111',
            'description': 'International Organization of Francophonie project calls.',
            'language': 'fr',
        },
    ]
    for s in sources:
        Source.create(Source(**s))
        logger.info("Created source: %s", s['name'])

    # Initial grant opportunities. These make the demo database useful out of
    # the box and give browser smoke tests deterministic cards to render when
    # navigating to the Grant surface.
    grants = [
        {
            'title': 'Community Spaces Renewal Fund',
            'funder': 'Friendly Future Foundation',
            'url': 'https://www.friendlyfuture.com/en/foundation/apply-for-funding',
            'source_url': 'https://www.friendlyfuture.com/en/foundation/apply-for-funding',
            'source_urls': ['https://www.friendlyfuture.com/en/foundation/apply-for-funding'],
            'description': (
                'Support for community-led renovations, accessibility upgrades, '
                'and gathering spaces that improve local quality of life.'
            ),
            'amount_min': 5000.0,
            'amount_max': 50000.0,
            'deadline': '2026-06-30',
            'eligibility_criteria': [
                'Applicant must be a registered non-profit or community organization.',
                'Project must benefit underserved or minority-language communities.',
                'Activities must take place in Canada.',
            ],
            'required_documents': ['Project budget', 'Letters patent', 'Board resolution'],
            'application_process': 'Submit an online application with a project plan and budget.',
            'status': 'new',
            'language': 'en',
        },
        {
            'title': 'Fonds initiatives francophones en santé',
            'funder': 'Programme communautaire francophone',
            'url': 'https://example.org/financement/sante-francophone',
            'source_url': 'https://ccndr.ca/',
            'source_urls': ['https://ccndr.ca/'],
            'description': (
                'Financement pour améliorer l’accès aux services, ressources et '
                'activités de santé en français dans les communautés minoritaires.'
            ),
            'amount_min': 10000.0,
            'amount_max': 75000.0,
            'deadline': '2026-09-15',
            'eligibility_criteria': [
                'Organisme francophone ou bilingue au service d’une communauté minoritaire.',
                'Projet lié à la promotion de la santé ou à l’accès aux services en français.',
                'Capacité démontrée de livrer le projet dans le Nord canadien.',
            ],
            'required_documents': ['Plan de projet', 'Budget détaillé', 'États financiers récents'],
            'application_process': 'Déposer le formulaire et les pièces justificatives avant la date limite.',
            'status': 'new',
            'language': 'fr',
        },
    ]
    for g in grants:
        Grant.create(Grant(**g))
        logger.info("Created grant: %s", g['title'])

    scout = AgentActor(
        name='Veille Scout',
        prompt=(
            'You monitor francophone nonprofit funding opportunities. '
            'Review configured sources, use web tools for extraction, and '
            'help operators identify promising grants.'
        ),
        llm='anthropic:claude-sonnet-4-5-20250929',
        constraints={'max_iterations': 20},
    )
    created_agent = AgentActor.create(scout)
    logger.info("Created agent: %s", created_agent.name)

    tool_data = [
        {'target': 'grants', 'description': 'Grant CRUD operations'},
        {'target': 'sources', 'description': 'Source listing and management'},
        {'target': 'web_tools', 'description': 'Web scraping utilities'},
    ]
    tools = []
    for tool in tool_data:
        tools.append(AgentTool.create(AgentTool(**tool)))
        logger.info("Linked agent tool: %s", tool['target'])
    AgentActor.update(created_agent.id, {'tools': tools})


if __name__ == '__main__':
    if '--reset' in sys.argv:
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
            print(f"Deleted {DB_PATH}")

    if User.storage and User.list():
        print("Database already has data. Use --reset to wipe and re-seed.")
        sys.exit(0)

    print("Seeding database...")
    seed()
    print("Done.")
