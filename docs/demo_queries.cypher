// Demo queries for Neo4j Browser

// Internet-exposed security groups
MATCH p=(:Internet)-[:CAN_REACH]->(:SecurityGroup)
RETURN p
LIMIT 100;

// Public path from Internet to EC2 via Security Group
MATCH p=(:Internet)-[:CAN_REACH]->(:SecurityGroup)-[:ATTACHED_TO]->(:EC2Instance)
RETURN p
LIMIT 100;

// Public exposure on SSH/RDP-like ports
MATCH p=(:Internet)-[r:CAN_REACH]->(:SecurityGroup)-[:ATTACHED_TO]->(:EC2Instance)
WHERE (r.fromPort <= 22 AND r.toPort >= 22) OR (r.fromPort <= 3389 AND r.toPort >= 3389)
RETURN p
LIMIT 100;

// IAM roles and their attached policies
MATCH p=(r:IAMRole)-[:HAS_POLICY]->(:IAMPolicy)
RETURN p
LIMIT 100;

// Privileged roles and their policies
MATCH p=(r:IAMRole {isPrivileged:true})-[:HAS_POLICY]->(:IAMPolicy)
RETURN p
LIMIT 100;
