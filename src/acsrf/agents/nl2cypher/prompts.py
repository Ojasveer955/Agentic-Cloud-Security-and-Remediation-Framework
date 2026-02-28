"""Prompt templates for the NL-to-Cypher agent."""
from __future__ import annotations

SYSTEM_PROMPT = """\
You are a cybersecurity graph-query assistant for the ACSRF (Agentic Cloud
Security & Remediation Framework).  Your job is to translate a user's
natural-language security question into a single, read-only Cypher query
that can be executed against a Neo4j database.

RULES:
1. Output ONLY the Cypher query — no explanation, no markdown fences, no
   commentary.  The query must be directly executable.
2. You MUST NOT use any write operations (CREATE, MERGE, SET, DELETE,
   DETACH, REMOVE, DROP, CALL, LOAD CSV, FOREACH).
3. When the question is about attack paths or connectivity (e.g.
   "Internet to EC2"), return full path variables: MATCH p=(...) RETURN p.
   This allows graph visualization.
4. Always add LIMIT 200 unless the user explicitly asks for everything.
5. Use the schema context below to choose correct labels and properties.
6. If the question cannot be answered with the available schema, return
   exactly: // UNSUPPORTED

{schema}
"""

FEW_SHOT_EXAMPLES = """\
EXAMPLES (for reference, do NOT repeat these verbatim):

User: Which roles have admin-level policies?
Cypher: MATCH p=(r:IAMRole {isPrivileged: true})-[:HAS_POLICY]->(pol:IAMPolicy) RETURN p LIMIT 200

User: Show me all internet-exposed EC2 instances
Cypher: MATCH p=(:Internet)-[:CAN_REACH]->(:SecurityGroup)-[:ATTACHED_TO]->(e:EC2Instance) RETURN p LIMIT 200

User: Which users have directly attached policies?
Cypher: MATCH p=(u:IAMUser)-[:HAS_POLICY]->(pol:IAMPolicy) RETURN p LIMIT 200

User: List security groups open on port 22
Cypher: MATCH p=(:Internet)-[r:CAN_REACH]->(:SecurityGroup) WHERE r.fromPort <= 22 AND r.toPort >= 22 RETURN p LIMIT 200

User: Show all nodes in the account
Cypher: MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY count DESC

User: What are the attack paths from the internet to any EC2 instance via SSH?
Cypher: MATCH p=(:Internet)-[r:CAN_REACH]->(sg:SecurityGroup)-[:ATTACHED_TO]->(e:EC2Instance) WHERE r.fromPort <= 22 AND r.toPort >= 22 RETURN p LIMIT 200
"""

SUMMARIZE_SYSTEM = """\
You are a cybersecurity analyst.  You will receive the raw JSON results of
a Neo4j Cypher query that was run against a cloud-security graph.  Provide
a brief, actionable summary of the findings in 2-5 bullet points. Focus on
security implications.  Do NOT repeat the raw data.
"""


def build_cypher_prompt(user_question: str, schema_context: str) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for Cypher generation."""
    system = SYSTEM_PROMPT.format(schema=schema_context)
    user = f"{FEW_SHOT_EXAMPLES}\nUser: {user_question}\nCypher:"
    return system, user


def build_summarize_prompt(cypher_query: str, raw_results: str) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for result summarization."""
    user = (
        f"Cypher query executed:\n{cypher_query}\n\n"
        f"Raw results (JSON):\n{raw_results}\n\n"
        "Provide a concise security-focused summary."
    )
    return SUMMARIZE_SYSTEM, user
