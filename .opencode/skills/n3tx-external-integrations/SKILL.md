---
name: n3tx-external-integrations
description: N3TX external API and service integration patterns. Use when calling third-party APIs, scraping, webhooks, protocol bridges, credentials, sync jobs, or making capabilities available to agents/UI.
argument-hint: "<external integration>"
---

# N3TX External Integrations

External IO must be wrapped in a reusable N3TX boundary.

## Choose an integration boundary

| Use case | Recommended shape | Reason |
|---|---|---|
| Stateless API call or scraper | Non-storable `ActorModel` | Schema-discoverable tool methods, no DB |
| API client with saved credentials/config | Storable `ActorModel` | Config/state in DB and addressable |
| Domain sync result | Storable domain `ActorModel` | Imported records become normal app data |
| New protocol bridge | `NetworkAdapter` | Protocol -> TX translation |
| Agent tool | Actor/ActorModel with `@expose_route` | Tool discovery from schema |
| Scheduled workflow | Actor invoking other actors | Reusable and observable through Matrix |

## Stateless tool actor

```python
class GitHubTools(ActorModel):
    __tablename__ = 'github_tools'
    __storable__ = False

    @expose_route('/repo', methods=['POST'])
    async def repo(self, owner: str, name: str) -> dict:
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get(f'https://api.github.com/repos/{owner}/{name}')
            r.raise_for_status()
        return r.json()
```

External HTTP is acceptable here because it is contained inside a dedicated actor capability.

## Persisted integration config

```python
class StripeAccount(ActorModel):
    __tablename__ = 'stripe_accounts'
    __storable__ = True
    api_key_ref: str
    account_name: str

    @expose_route('/sync_customers', methods=['POST'])
    async def sync_customers(self) -> dict:
        ...
```

## Guardrails

- Do not call third-party APIs from arbitrary model methods if the capability should be reused.
- Do not expose secrets in schema or responses.
- Do not let UI call external APIs directly when backend auth/audit/reuse matters.
- Do not bypass actors for integrations used by agents.

## Verification

- Integration actor appears in schema.
- Methods are callable through generated routes/TX.
- Errors are structured and safe.
- Agents can use integration if listed in tools.
- Secrets are not leaked in schema/entity responses.

## Source-reading policy

Inspect framework source only when docs/skills are insufficient, do not cover the intended implementation, or observed behavior contradicts docs. Update/propose docs when gaps are found.
