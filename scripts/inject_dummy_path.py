"""Inject dummy vulnerable path data into Neo4j for testing."""
from neo4j import GraphDatabase

CYPHER_SCRIPT = """
// 1. Setup the Environment
MERGE (a:Account {accountId: "999999999999"})
SET a.name = "Simulated-Vuln-Env"

// 2. The Internet Source
MERGE (i:Internet {cidr: "0.0.0.0/0"})

// 3. The Vulnerable Security Group (Open SSH)
MERGE (sg:SecurityGroup {groupId: "sg-vulnerable-001"})
SET sg.groupName = "public-ssh-sg", sg.vpcId = "vpc-dummy"
MERGE (sg)-[:IN_ACCOUNT]->(a)
MERGE (i)-[:CAN_REACH {fromPort: 22, toPort: 22, proto: "tcp"}]->(sg)

// 4. The Exposed EC2 Instance
MERGE (ec2:EC2Instance {instanceId: "i-dummy-exposed-001"})
SET ec2.publicIp = "203.0.113.42", ec2.name = "Jumpbox"
MERGE (ec2)-[:IN_ACCOUNT]->(a)
MERGE (sg)-[:ATTACHED_TO]->(ec2)

// 5. The IAM Role attached to the EC2 Instance
MERGE (role:IAMRole {arn: "arn:aws:iam::999999999999:role/ExposedEC2Role"})
SET role.roleName = "ExposedEC2Role", role.isPrivileged = true
MERGE (role)-[:IN_ACCOUNT]->(a)
MERGE (ec2)-[:ASSUMES_ROLE]->(role) // Represents Instance Profile attachment

// 6. The Highly Privileged Policy
MERGE (pol:IAMPolicy {arn: "arn:aws:iam::999999999999:policy/OverlyPermissiveAdmin"})
SET pol.policyName = "OverlyPermissiveAdmin", pol.document = '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"*","Resource":"*"}]}'
MERGE (pol)-[:IN_ACCOUNT]->(a)
MERGE (role)-[:HAS_POLICY]->(pol)
"""

def main():
    uri = "bolt://localhost:7687"
    driver = GraphDatabase.driver(uri, auth=("neo4j", "password"))
    with driver.session() as session:
        # Clear existing data so the visualization is clean
        session.run("MATCH (n) DETACH DELETE n")
        # Run the dummy inject
        session.run(CYPHER_SCRIPT)
        print("Successfully injected dummy vulnerable path into Neo4j!")

if __name__ == "__main__":
    main()
