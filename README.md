# ACSRF (Agentic Cloud-Native Security & Remediation Framework)

**Graph-First MVP Release**

This framework enumerates an AWS environment, structures the findings into a Neo4j graph database, and leverages a Natural Language to Cypher AI Agent to allow security analysts to query cloud attack paths in plain English. 

It assumes an "assumed breach" model, using a read-only role to discover vulnerabilities and visualize attack paths from the Internet down to highly privileged internal assets.

## Key Features
- **Idempotent Ingestion**: Data pipeline runs purely in Python (no LLMs in the data path), fetching Boto3 data and mapping it to a `MERGE`-only Neo4j Cypher protocol.
- **Natural Language Security Queries**: Ask questions like *"What are the attack paths from the internet to a highly privileged IAM role?"*
- **AI-Powered Translation**: `google-genai` (configured via an abstract `LLMBackend`, making it swappable to on-prem VLLM deployments) translates English into read-only Cypher statements.
- **Interactive Graph Visualization**: Dynamically generates standalone HTML (`artifacts/graph_viz.html`) rendering the attack paths with `vis.js`, along with an AI-generated security summary of the findings.

## Prereqs
- Python 3.10+
- Neo4j (recommended: Docker `neo4j:5` running on `localhost:7687`)
- A `.env` file (copy from `.env.example`) populated with:
  - `NEO4J` credentials
  - `AWS` credentials (for live cloud enumeration)
  - `GEMINI_API_KEY` (for the NL2Cypher Agent)

## Quickstart

```powershell
# Setup environment
python -m venv .venv
. .venv/Scripts/activate
pip install -e .

# Option A: Run Live AWS Enumeration
acsrf init-db
acsrf enum-real

# Option B: Run Dummy Vulnerable Path (for testing graph plotting)
python scripts/inject_dummy_path.py

# Query the Graph in Plain English
acsrf query-nl "What are the attack paths from the internet to a highly privileged EC2 IAM role?"
```

## Outputs
- **Raw/Normalized AWS Data**: Saved to `artifacts/aws_enum_normalized.json`
- **Query Results JSON**: Saved to `artifacts/nl2cypher_last_result.json`
- **Graph Plot**: Automatically generated at `artifacts/graph_viz.html` when a query outputs paths. Open this in your browser to view the interactive map and LLM summary!

## Full System Architecture (Vision)
While the current MVP focuses on the Graph-First Enum and NL2Cypher querying, the complete ACSRF architecture encompasses:
1. **Cloud Enumeration (Boto3)**: Safe, read-only extraction of IAM, EC2, SG, S3 data.
2. **Graph Mapping (Neo4j)**: Structuring resources to identify cross-boundary attack paths.
3. **NL2Cypher Agent**: Swappable LLM Backend (Gemini APIs or On-Prem models) to query graphs naturally.
4. **Agentic Orchestration (LangGraph)**: *(Planned)* Stateful orchestration of agents with cyclic routing and Human-in-the-Loop breakpoints.
5. **Advanced Recon (MCP Server)**: *(Planned)* Dockerized DevSecOps/Security tools (Prowler, Pacu, Nmap) exposed via MCP for targeted active scanning triggered by the orchestrator.
6. **Remediation Agent (Terraform)**: *(Planned)* Automated, drift-aware generation of Terraform HCL configurations to patch discovered attack paths.

## Architecture Map (Schema)
See `docs/schema.md` for a comprehensive breakdown of the modeled relationships (e.g. `(EC2Instance)-[:ASSUMES_ROLE]->(IAMRole)`).
