"""Predefined Cypher queries for the canonical SG-based graph model."""

QUERY_PACK = {
    "internet_to_security_group": {
        "description": "Internet-exposed security groups",
        "cypher": (
            "MATCH p=(:Internet)-[:CAN_REACH]->(:SecurityGroup) "
            "RETURN p LIMIT 100"
        ),
    },
    "internet_to_instance_via_sg": {
        "description": "Public path from Internet to EC2 via Security Group",
        "cypher": (
            "MATCH p=(:Internet)-[:CAN_REACH]->(:SecurityGroup)-[:ATTACHED_TO]->(:EC2Instance) "
            "RETURN p LIMIT 100"
        ),
    },
    "internet_to_instance_sensitive_ports": {
        "description": "Public exposure on SSH/RDP-like ports",
        "cypher": (
            "MATCH p=(:Internet)-[r:CAN_REACH]->(:SecurityGroup)-[:ATTACHED_TO]->(:EC2Instance) "
            "WHERE (r.fromPort <= 22 AND r.toPort >= 22) OR (r.fromPort <= 3389 AND r.toPort >= 3389) "
            "RETURN p LIMIT 100"
        ),
    },
    "role_to_policy": {
        "description": "IAM roles and their attached policies",
        "cypher": (
            "MATCH p=(r:IAMRole)-[:HAS_POLICY]->(:IAMPolicy) "
            "RETURN p LIMIT 100"
        ),
    },
    "privileged_role_to_policy": {
        "description": "Privileged roles and their policies",
        "cypher": (
            "MATCH p=(r:IAMRole {isPrivileged:true})-[:HAS_POLICY]->(:IAMPolicy) "
            "RETURN p LIMIT 100"
        ),
    },
}
