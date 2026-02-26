"""Idempotent ingestion for real AWS enumeration output (MERGE only)."""
from __future__ import annotations

from typing import Any, Dict, Iterable, Tuple

from neo4j import Driver


def _merge_account(tx, account: Dict[str, Any]) -> None:
    tx.run(
        """
        MERGE (a:Account {accountId: $accountId})
        SET a.name = $name, a.env = $env
        """,
        **account,
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


def _merge_policy(tx, policy: Dict[str, Any], account_id: str) -> None:
    tx.run(
        """
        MERGE (p:IAMPolicy {arn: $arn})
        SET p.policyName = $policyName
        WITH p
        MATCH (a:Account {accountId: $accountId})
        MERGE (p)-[:IN_ACCOUNT]->(a)
        """,
        accountId=account_id,
        **policy,
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


def _merge_security_group(tx, sg: Dict[str, Any], account_id: str) -> None:
    tx.run(
        """
        MERGE (sg:SecurityGroup {groupId: $groupId})
        SET sg.groupName = $groupName, sg.description = $description, sg.vpcId = $vpcId
        WITH sg
        MATCH (a:Account {accountId: $accountId})
        MERGE (sg)-[:IN_ACCOUNT]->(a)
        """,
        accountId=account_id,
        **sg,
    )


def _merge_internet(tx, cidr: str) -> None:
    tx.run(
        """
        MERGE (i:Internet {cidr: $cidr})
        """,
        cidr=cidr,
    )


def _merge_role_policy_edge(tx, role_arn: str, policy_arn: str) -> None:
    tx.run(
        """
        MATCH (r:IAMRole {arn: $roleArn})
        MATCH (p:IAMPolicy {arn: $policyArn})
        MERGE (r)-[:HAS_POLICY]->(p)
        """,
        roleArn=role_arn,
        policyArn=policy_arn,
    )


def _merge_instance_sg_edge(tx, instance_id: str, group_id: str) -> None:
    tx.run(
        """
        MATCH (e:EC2Instance {instanceId: $instanceId})
        MATCH (sg:SecurityGroup {groupId: $groupId})
        MERGE (sg)-[:ATTACHED_TO]->(e)
        """,
        instanceId=instance_id,
        groupId=group_id,
    )


def _merge_internet_sg_edge(tx, edge: Dict[str, Any]) -> None:
    tx.run(
        """
        MATCH (i:Internet {cidr: $cidr})
        MATCH (sg:SecurityGroup {groupId: $groupId})
        MERGE (i)-[r:CAN_REACH]->(sg)
        SET r.fromPort = $fromPort, r.toPort = $toPort, r.proto = $proto
        """,
        **edge,
    )


def _dedupe_pairs(items: Iterable[Tuple[str, str]]) -> set[Tuple[str, str]]:
    return {(a, b) for a, b in items if a and b}


def ingest_real_enum(driver: Driver, enum_data: Dict[str, Any]) -> None:
    account = enum_data["account"]
    account_id = account["accountId"]
    roles = enum_data.get("roles", [])
    policies = enum_data.get("policies", [])
    instances = enum_data.get("instances", [])
    security_groups = enum_data.get("security_groups", [])
    role_policy_edges = _dedupe_pairs(enum_data.get("role_policy_edges", []))
    instance_sg_edges = _dedupe_pairs(enum_data.get("instance_sg_edges", []))
    internet_edges = enum_data.get("internet_edges", [])

    with driver.session() as session:
        session.execute_write(_merge_account, account)

        for role in roles:
            session.execute_write(_merge_role, role, account_id)
        for policy in policies:
            session.execute_write(_merge_policy, policy, account_id)
        for instance in instances:
            session.execute_write(_merge_instance, instance, account_id)
        for sg in security_groups:
            session.execute_write(_merge_security_group, sg, account_id)

        for role_arn, policy_arn in role_policy_edges:
            session.execute_write(_merge_role_policy_edge, role_arn, policy_arn)
        for instance_id, group_id in instance_sg_edges:
            session.execute_write(_merge_instance_sg_edge, instance_id, group_id)

        for edge in internet_edges:
            cidr = edge.get("cidr")
            if cidr:
                session.execute_write(_merge_internet, cidr)
                session.execute_write(_merge_internet_sg_edge, edge)
