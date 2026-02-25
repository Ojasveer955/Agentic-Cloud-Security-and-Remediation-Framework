# Graph Schema (Demo MVP)

## Node Labels
- Account: `accountId` (pk), `name`, `env`
- IAMUser: `arn` (pk), `userName`, `mfaEnabled`, `riskTier`
- IAMRole: `arn` (pk), `roleName`, `isPrivileged`, `policyRefs` (list)
- EC2Instance: `instanceId` (pk), `name`, `publicIp`, `criticality`, `ssmEnabled`
- S3Bucket: `bucketName` (pk), `arn`, `publicRead`, `encryption`
- Secret: `secretId` (pk), `name`, `classification`
- Internet: `cidr` (pk) — typically `0.0.0.0/0`

## Relationships (all via MERGE)
- (IAMUser)-[:IN_ACCOUNT]->(Account)
- (IAMRole)-[:IN_ACCOUNT]->(Account)
- (EC2Instance)-[:IN_ACCOUNT]->(Account)
- (S3Bucket)-[:IN_ACCOUNT]->(Account)
- (Secret)-[:IN_ACCOUNT]->(Account)
- (IAMUser)-[:CAN_ASSUME {condition}]->(IAMRole)
- (IAMRole)-[:CAN_SSM]->(EC2Instance)
- (IAMRole)-[:CAN_READ]->(S3Bucket)
- (S3Bucket)-[:CONTAINS]->(Secret)
- (Internet)-[:CAN_REACH {port, proto}]->(EC2Instance)

## Constraints (recommended)
- `CONSTRAINT account_id IF NOT EXISTS FOR (n:Account) REQUIRE n.accountId IS UNIQUE`
- `CONSTRAINT iamuser_arn IF NOT EXISTS FOR (n:IAMUser) REQUIRE n.arn IS UNIQUE`
- `CONSTRAINT iamrole_arn IF NOT EXISTS FOR (n:IAMRole) REQUIRE n.arn IS UNIQUE`
- `CONSTRAINT ec2_instance_id IF NOT EXISTS FOR (n:EC2Instance) REQUIRE n.instanceId IS UNIQUE`
- `CONSTRAINT s3_bucket_name IF NOT EXISTS FOR (n:S3Bucket) REQUIRE n.bucketName IS UNIQUE`
- `CONSTRAINT secret_id IF NOT EXISTS FOR (n:Secret) REQUIRE n.secretId IS UNIQUE`
- `CONSTRAINT internet_cidr IF NOT EXISTS FOR (n:Internet) REQUIRE n.cidr IS UNIQUE`

## Notes
- Keep node keys stable for MERGE idempotency.
- Policy documents are not stored; only derived effects (`CAN_READ`, `CAN_SSM`) and optional `policyRefs` list on roles.
- Use only MERGE (never CREATE) in ingestion to avoid duplicates on reruns.
