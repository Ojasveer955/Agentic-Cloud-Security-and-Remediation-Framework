# Graph Schema (Demo MVP)

## Node Labels
- Account: `accountId` (pk), `name`, `env`
- IAMUser: `arn` (pk), `userName`, `mfaEnabled`, `riskTier`
- IAMRole: `arn` (pk), `roleName`, `isPrivileged`, `policyRefs` (list)
- IAMPolicy: `arn` (pk), `policyName`
- EC2Instance: `instanceId` (pk), `name`, `publicIp`, `criticality`, `ssmEnabled`
- SecurityGroup: `groupId` (pk), `groupName`, `description`, `vpcId`
- S3Bucket: `bucketName` (pk), `arn`, `publicRead`, `encryption`
- Secret: `secretId` (pk), `name`, `classification`
- Internet: `cidr` (pk) — typically `0.0.0.0/0`

## Relationships (all via MERGE)
- (IAMUser)-[:IN_ACCOUNT]->(Account)
- (IAMRole)-[:IN_ACCOUNT]->(Account)
- (IAMPolicy)-[:IN_ACCOUNT]->(Account)
- (EC2Instance)-[:IN_ACCOUNT]->(Account)
- (SecurityGroup)-[:IN_ACCOUNT]->(Account)
- (S3Bucket)-[:IN_ACCOUNT]->(Account)
- (Secret)-[:IN_ACCOUNT]->(Account)
- (IAMUser)-[:CAN_ASSUME {condition}]->(IAMRole)
- (IAMRole)-[:HAS_POLICY]->(IAMPolicy)
- (IAMPolicy)-[:CAN_READ]->(S3Bucket)
- (SecurityGroup)-[:ATTACHED_TO]->(EC2Instance)
- (S3Bucket)-[:CONTAINS]->(Secret)
- (Internet)-[:CAN_REACH {fromPort, toPort, proto}]->(SecurityGroup)

## Constraints (recommended)
- `CONSTRAINT account_id IF NOT EXISTS FOR (n:Account) REQUIRE n.accountId IS UNIQUE`
- `CONSTRAINT iamuser_arn IF NOT EXISTS FOR (n:IAMUser) REQUIRE n.arn IS UNIQUE`
- `CONSTRAINT iamrole_arn IF NOT EXISTS FOR (n:IAMRole) REQUIRE n.arn IS UNIQUE`
- `CONSTRAINT iampolicy_arn IF NOT EXISTS FOR (n:IAMPolicy) REQUIRE n.arn IS UNIQUE`
- `CONSTRAINT ec2_instance_id IF NOT EXISTS FOR (n:EC2Instance) REQUIRE n.instanceId IS UNIQUE`
- `CONSTRAINT sg_group_id IF NOT EXISTS FOR (n:SecurityGroup) REQUIRE n.groupId IS UNIQUE`
- `CONSTRAINT s3_bucket_name IF NOT EXISTS FOR (n:S3Bucket) REQUIRE n.bucketName IS UNIQUE`
- `CONSTRAINT secret_id IF NOT EXISTS FOR (n:Secret) REQUIRE n.secretId IS UNIQUE`
- `CONSTRAINT internet_cidr IF NOT EXISTS FOR (n:Internet) REQUIRE n.cidr IS UNIQUE`

## Notes
- Keep node keys stable for MERGE idempotency.
- Policy documents are not stored; only metadata (`IAMPolicy`) and derived effects (`HAS_POLICY`, `CAN_READ`) are mapped.
- Use only MERGE (never CREATE) in ingestion to avoid duplicates on reruns.
