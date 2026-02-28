"""Neo4j schema initialization for the demo graph."""
from neo4j import Driver


CONSTRAINTS = [
    "CREATE CONSTRAINT account_id IF NOT EXISTS FOR (n:Account) REQUIRE n.accountId IS UNIQUE",
    "CREATE CONSTRAINT iamuser_arn IF NOT EXISTS FOR (n:IAMUser) REQUIRE n.arn IS UNIQUE",
    "CREATE CONSTRAINT iamrole_arn IF NOT EXISTS FOR (n:IAMRole) REQUIRE n.arn IS UNIQUE",
    "CREATE CONSTRAINT iampolicy_arn IF NOT EXISTS FOR (n:IAMPolicy) REQUIRE n.arn IS UNIQUE",
    "CREATE CONSTRAINT ec2_instance_id IF NOT EXISTS FOR (n:EC2Instance) REQUIRE n.instanceId IS UNIQUE",
    "CREATE CONSTRAINT sg_group_id IF NOT EXISTS FOR (n:SecurityGroup) REQUIRE n.groupId IS UNIQUE",
    "CREATE CONSTRAINT s3_bucket_name IF NOT EXISTS FOR (n:S3Bucket) REQUIRE n.bucketName IS UNIQUE",
    "CREATE CONSTRAINT secret_id IF NOT EXISTS FOR (n:Secret) REQUIRE n.secretId IS UNIQUE",
    "CREATE CONSTRAINT internet_cidr IF NOT EXISTS FOR (n:Internet) REQUIRE n.cidr IS UNIQUE",
]


def init_constraints(driver: Driver) -> None:
    with driver.session() as session:
        for stmt in CONSTRAINTS:
            session.run(stmt)
