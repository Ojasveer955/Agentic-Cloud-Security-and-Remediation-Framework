"""Build a concise schema context string for LLM prompt injection.

The context tells the model which node labels, relationship types, and
property keys exist in the ACSRF Neo4j graph so it can generate correct
Cypher queries.
"""
from __future__ import annotations

SCHEMA_CONTEXT = """\
=== Neo4j Graph Schema (ACSRF) ===

NODE LABELS & PROPERTIES:
  Account        : accountId (PK), name, env
  IAMUser        : arn (PK), userName, mfaEnabled, isPrivileged
  IAMRole        : arn (PK), roleName, isPrivileged, policyRefs (list)
  IAMPolicy      : arn (PK), policyName, document (JSON string)
  EC2Instance    : instanceId (PK), name, publicIp, criticality, ssmEnabled
  SecurityGroup  : groupId (PK), groupName, description, vpcId
  S3Bucket       : bucketName (PK), arn, publicRead, encryption
  Secret         : secretId (PK), name, classification
  Internet       : cidr (PK)  — typically "0.0.0.0/0" or "::/0"

RELATIONSHIPS:
  (IAMUser)-[:IN_ACCOUNT]->(Account)
  (IAMRole)-[:IN_ACCOUNT]->(Account)
  (IAMPolicy)-[:IN_ACCOUNT]->(Account)
  (EC2Instance)-[:IN_ACCOUNT]->(Account)
  (SecurityGroup)-[:IN_ACCOUNT]->(Account)
  (S3Bucket)-[:IN_ACCOUNT]->(Account)
  (Secret)-[:IN_ACCOUNT]->(Account)
  (IAMUser)-[:CAN_ASSUME {condition}]->(IAMRole)
  (IAMUser)-[:HAS_POLICY]->(IAMPolicy)
  (IAMRole)-[:HAS_POLICY]->(IAMPolicy)
  (IAMPolicy)-[:CAN_READ]->(S3Bucket)
  (SecurityGroup)-[:ATTACHED_TO]->(EC2Instance)
  (EC2Instance)-[:ASSUMES_ROLE]->(IAMRole)
  (S3Bucket)-[:CONTAINS]->(Secret)
  (Internet)-[:CAN_REACH {fromPort, toPort, proto}]->(SecurityGroup)

NOTES:
  - Use MATCH (never write operations).
  - Boolean properties (isPrivileged, mfaEnabled, publicRead): true / false.
  - Internet exposure: Internet node with cidr "0.0.0.0/0" connects via
    CAN_REACH to SecurityGroup, which connects via ATTACHED_TO to EC2Instance.
  - Return full paths (p=...) when the user asks about attack paths or
    connectivity chains so the graph can be visualized.
"""


def get_schema_context() -> str:
    """Return the static schema context string."""
    return SCHEMA_CONTEXT
