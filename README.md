# ACSRF Demo (Graph-First MVP)

Minimal demo that ingests a hardcoded cloud graph into Neo4j and runs predefined Cypher queries. No AWS calls, no agents, no LLMs—just a deterministic dataset to prove the graph slice.

## Prereqs
- Python 3.10+
- Neo4j (recommended: Docker `neo4j:5`)
- Env vars: `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`

## Quickstart
```
python -m venv .venv
. .venv/Scripts/activate
pip install -r requirements.txt
python -m acsrf.main init-db
python -m acsrf.main ingest-dummy
python -m acsrf.main run-queries
```

## Notes
- Ingestion is idempotent (MERGE-only). Reruns should keep node/edge counts stable.
- Queries are provided in docs/demo_queries.cypher for use directly in Neo4j Browser.
- Schema is documented in docs/schema.md.
