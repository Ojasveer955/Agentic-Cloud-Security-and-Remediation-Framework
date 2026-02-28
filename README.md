# ACSRF (Agentic Cloud-Native Security & Remediation Framework)

**Graph-First MVP Release**

This framework enumerates an AWS environment, structures the findings into a Neo4j graph database, and leverages a Natural Language to Cypher AI Agent to allow security analysts to query cloud attack paths in plain English. 

It assumes an "assumed breach" model, using a read-only role to discover vulnerabilities and visualize attack paths from the Internet down to highly privileged internal assets.

## Key Features
- **Idempotent Ingestion**: Data pipeline runs purely in Python (no LLMs in the data path), fetching Boto3 data and mapping it to a `MERGE`-only Neo4j Cypher protocol.
- **Natural Language Security Queries**: Ask questions like *"What are the attack paths from the internet to a highly privileged IAM role?"*
- **AI-Powered Translation**: `google-genai` (configured via an abstract `LLMBackend`, making it swappable to on-prem vLLM deployments) translates English into read-only Cypher statements.
- **Interactive Graph Visualization**: Dynamically generates standalone HTML (`artifacts/graph_viz.html`) rendering the attack paths with `vis.js`, along with an AI-generated security summary of the findings.

## Prereqs
- Python 3.10+
- Neo4j (recommended: Docker `neo4j:5` running on `localhost:7687`)
- A `.env` file (copy from `.env.example`) populated with:
  - `NEO4J` credentials
  - `AWS` credentials (for live cloud enumeration. Permissions for the credentials: Read-only)
  - `GEMINI_API_KEY` (for the NL2Cypher Agent)

## Quickstart

```powershell
# Setup environment
python -m venv .venv
. .venv/Scripts/activate
```

### Option A: Editable Install (Recommended)

Registers the `acsrf` CLI command globally in your virtualenv. No `PYTHONPATH` needed.

```powershell
pip install -e .

acsrf init-db
acsrf enum-real                # OR: python scripts/inject_dummy_path.py (for dummy test data)
acsrf query-nl "What are the attack paths from the internet to a highly privileged EC2 IAM role?"
acsrf orchestrate --question "What are the attack paths from the internet to privileged resources?"
acsrf orchestrate --question "..." --deep-analysis   # Holistic cross-correlation
acsrf orchestrate --resume <thread-id>               # Resume a paused pipeline
```

### Option B: Simple Install

Uses `requirements.txt`. You must set `PYTHONPATH` to `src` before every command.

```powershell
pip install -r requirements.txt

$env:PYTHONPATH = "src"
python -m acsrf.main init-db
python -m acsrf.main enum-real   # OR: python scripts/inject_dummy_path.py
python -m acsrf.main query-nl "What are the attack paths from the internet to a highly privileged EC2 IAM role?"
python -m acsrf.main orchestrate --question "What are the attack paths from the internet to privileged resources?"
```

## Outputs
- **Raw/Normalized AWS Data**: Saved to `artifacts/aws_enum_normalized.json`
- **Query Results JSON**: Saved to `artifacts/nl2cypher_last_result.json`
- **Graph Plot**: Automatically generated at `artifacts/graph_viz.html` when a query outputs paths. Open this in your browser to view the interactive map and LLM summary!
- **Orchestrator Audit Log**: Saved to `artifacts/orchestrator_audit.json` — full trace of every agent node, routing decision, and state transition.

## Full System Architecture (Vision)
While the current MVP focuses on the Graph-First Enum and NL2Cypher querying, the complete ACSRF architecture encompasses:
1. **Cloud Enumeration Agent (Boto3)**: Safe, read-only extraction of IAM, EC2, SG, S3 data.
2. **Graph Mapping (Neo4j)**: Structuring resources to identify cross-boundary attack paths.
3. **NL2Cypher Agent**: Swappable LLM Backend (Gemini APIs or On-Prem models) to query graphs naturally.
4. **Analysis & Correlation Agent**: *(Planned)* The "brain" of the system — uses LLM reasoning over the Neo4j graph to discover and rank attack paths.
5. **Validation Agent (MCP-Connected)**: *(Planned)* Verifies if discovered attack paths are actually exploitable (e.g., IMDS reachability, SSRF, credential dumping). Connected via MCP to a Docker container with pre-selected security tools (Prowler, Nmap, etc.).
6. **LangGraph Orchestrator**: ✅ Stateful orchestration of all agents with cyclic routing, Human-in-the-Loop breakpoints, SqliteSaver persistence, and structured audit logging.
7. **Remediation Agent (Terraform)**: *(Planned)* Automated, drift-aware generation of Terraform HCL configurations to patch discovered attack paths.

## Architecture Map (Schema)
See `docs/schema.md` for a comprehensive breakdown of the modeled relationships (e.g. `(EC2Instance)-[:ASSUMES_ROLE]->(IAMRole)`).
