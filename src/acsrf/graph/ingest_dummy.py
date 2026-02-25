"""Idempotent ingestion of the dummy dataset using MERGE only."""
from typing import Dict, Any
from neo4j import Driver


ALLOWED_NODE_LABELS = {
    "Account",
    "IAMUser",
    "IAMRole",
    "EC2Instance",
    "S3Bucket",
    "Secret",
    "Internet",
}


def _merge_account(tx, account: Dict[str, Any]) -> None:
    tx.run(
        """
        MERGE (a:Account {accountId: $accountId})
        SET a.name = $name, a.env = $env
        """,
        **account,
    )


def _merge_user(tx, user: Dict[str, Any], account_id: str) -> None:
    tx.run(
        """
        MERGE (u:IAMUser {arn: $arn})
        SET u.userName = $userName, u.mfaEnabled = $mfaEnabled, u.riskTier = $riskTier
        WITH u
        MATCH (a:Account {accountId: $accountId})
        MERGE (u)-[:IN_ACCOUNT]->(a)
        """,
        accountId=account_id,
        **user,
    )


def _merge_role(tx, role: Dict[str, Any], account_id: str) -> None:
    tx.run(
        """
        MERGE (r:IAMRole {arn: $arn})
        SET r.roleName = $roleName, r.isPrivileged = $isPrivileged, r.policyRefs = $policyRefs
        WITH r
        MATCH (a:Account {accountId: $accountId})
        MERGE (r)-[:IN_ACCOUNT]->(a)
        """,
        accountId=account_id,
        **role,
    )


def _merge_instance(tx, instance: Dict[str, Any], account_id: str) -> None:
    tx.run(
        """
        MERGE (e:EC2Instance {instanceId: $instanceId})
        SET e.name = $name, e.publicIp = $publicIp, e.criticality = $criticality, e.ssmEnabled = $ssmEnabled
        WITH e
        MATCH (a:Account {accountId: $accountId})
        MERGE (e)-[:IN_ACCOUNT]->(a)
        """,
        accountId=account_id,
        **instance,
    )


def _merge_bucket(tx, bucket: Dict[str, Any], account_id: str) -> None:
    tx.run(
        """
        MERGE (b:S3Bucket {bucketName: $bucketName})
        SET b.arn = $arn, b.publicRead = $publicRead, b.encryption = $encryption
        WITH b
        MATCH (a:Account {accountId: $accountId})
        MERGE (b)-[:IN_ACCOUNT]->(a)
        """,
        accountId=account_id,
        **bucket,
    )


def _merge_secret(tx, secret: Dict[str, Any], account_id: str) -> None:
    tx.run(
        """
        MERGE (s:Secret {secretId: $secretId})
        SET s.name = $name, s.classification = $classification
        WITH s
        MATCH (a:Account {accountId: $accountId})
        MERGE (s)-[:IN_ACCOUNT]->(a)
        """,
        accountId=account_id,
        **secret,
    )


def _merge_internet(tx, internet: Dict[str, Any]) -> None:
    tx.run(
        """
        MERGE (i:Internet {cidr: $cidr})
        """,
        **internet,
    )


def _merge_relationship(tx, rel: Dict[str, Any]) -> None:
    rel_type = rel["type"]
    from_label, from_key, from_val = rel["from"]
    to_label, to_key, to_val = rel["to"]
    if from_label not in ALLOWED_NODE_LABELS or to_label not in ALLOWED_NODE_LABELS:
        raise ValueError(f"Unexpected label in relationship: {from_label} -> {to_label}")

    tx.run(
        f"""
        MATCH (f:{from_label} {{{from_key}: $from_val}})
        MATCH (t:{to_label} {{{to_key}: $to_val}})
        MERGE (f)-[r:{rel_type}]->(t)
        SET r += $props
        """,
        from_val=from_val,
        to_val=to_val,
        props=rel.get("props", {}),
    )


def ingest_dummy(driver: Driver, dataset: Dict[str, Any]) -> None:
    account = dataset["account"]
    users = dataset.get("users", [])
    roles = dataset.get("roles", [])
    instances = dataset.get("instances", [])
    buckets = dataset.get("buckets", [])
    secrets = dataset.get("secrets", [])
    internet = dataset.get("internet")
    rels = dataset.get("relationships", [])

    with driver.session() as session:
        session.execute_write(_merge_account, account)
        if internet:
            session.execute_write(_merge_internet, internet)
        for user in users:
            session.execute_write(_merge_user, user, account["accountId"])
        for role in roles:
            session.execute_write(_merge_role, role, account["accountId"])
        for inst in instances:
            session.execute_write(_merge_instance, inst, account["accountId"])
        for bucket in buckets:
            session.execute_write(_merge_bucket, bucket, account["accountId"])
        for secret in secrets:
            session.execute_write(_merge_secret, secret, account["accountId"])
        for rel in rels:
            session.execute_write(_merge_relationship, rel)
