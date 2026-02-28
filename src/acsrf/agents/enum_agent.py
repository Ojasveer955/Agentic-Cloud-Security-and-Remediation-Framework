"""AWS enumeration agent to pull real ."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import boto3


def _extract_account_id_from_arn(arn: str | None) -> str | None:
    if not arn:
        return None
    parts = arn.split(":")
    if len(parts) >= 5 and parts[4]:
        return parts[4]
    return None


def _is_likely_privileged(role_name: str, managed_policy_names: List[str]) -> bool:
    role_name_l = role_name.lower()
    if any(token in role_name_l for token in ["admin", "power", "root", "securityaudit"]):
        return True
    privileged_policy_tokens = [
        "administratoraccess",
        "poweruseraccess",
        "iamfullaccess",
    ]
    lower_policy_names = [name.lower() for name in managed_policy_names]
    return any(
        token in policy_name
        for token in privileged_policy_tokens
        for policy_name in lower_policy_names
    )


def _paginate_iam_auth_details(iam_client) -> Dict[str, Any]:
    merged: Dict[str, Any] = {
        "UserDetailList": [],
        "GroupDetailList": [],
        "RoleDetailList": [],
        "Policies": [],
    }

    marker = None
    while True:
        kwargs = {"Filter": ["User", "Role", "Group", "LocalManagedPolicy"]}
        if marker:
            kwargs["Marker"] = marker
        response = iam_client.get_account_authorization_details(**kwargs)

        merged["UserDetailList"].extend(response.get("UserDetailList", []))
        merged["GroupDetailList"].extend(response.get("GroupDetailList", []))
        merged["RoleDetailList"].extend(response.get("RoleDetailList", []))
        merged["Policies"].extend(response.get("Policies", []))

        if not response.get("IsTruncated"):
            break
        marker = response.get("Marker")
        if not marker:
            break

    return merged


def _paginate_ec2_instances(ec2_client) -> List[Dict[str, Any]]:
    paginator = ec2_client.get_paginator("describe_instances")
    instances: List[Dict[str, Any]] = []
    for page in paginator.paginate():
        for reservation in page.get("Reservations", []):
            instances.extend(reservation.get("Instances", []))
    return instances


def _paginate_security_groups(ec2_client) -> List[Dict[str, Any]]:
    paginator = ec2_client.get_paginator("describe_security_groups")
    groups: List[Dict[str, Any]] = []
    for page in paginator.paginate():
        groups.extend(page.get("SecurityGroups", []))
    return groups


def _normalize(
    iam_details: Dict[str, Any],
    instances_raw: List[Dict[str, Any]],
    security_groups_raw: List[Dict[str, Any]],
) -> Dict[str, Any]:
    role_items = iam_details.get("RoleDetailList", [])
    user_items = iam_details.get("UserDetailList", [])
    policy_items = iam_details.get("Policies", [])

    account_id = None
    roles: List[Dict[str, Any]] = []
    users: List[Dict[str, Any]] = []
    policies: List[Dict[str, Any]] = []
    seen_policy_arns: set = set()
    role_policy_edges: List[Tuple[str, str]] = []
    user_policy_edges: List[Tuple[str, str]] = []

    def _ensure_policy(arn: str, name: str) -> None:
        """Add a stub entry for any referenced policy not already in the list."""
        if arn and arn not in seen_policy_arns:
            policies.append({"arn": arn, "policyName": name, "document": None})
            seen_policy_arns.add(arn)

    for policy in policy_items:
        policy_arn = policy.get("Arn")
        if not account_id:
            account_id = _extract_account_id_from_arn(policy_arn)
        if not policy_arn:
            continue
        
        # Extract default policy version document
        document = None
        for version in policy.get("PolicyVersionList", []):
            if version.get("IsDefaultVersion"):
                document = version.get("Document")
                break

        policies.append(
            {
                "arn": policy_arn,
                "policyName": policy.get("PolicyName", "unknown-policy"),
                "document": json.dumps(document) if document else None,
            }
        )
        seen_policy_arns.add(policy_arn)

    for role in role_items:
        role_arn = role.get("Arn")
        role_name = role.get("RoleName", "unknown-role")
        attached = role.get("AttachedManagedPolicies", [])
        attached_names = [p.get("PolicyName") for p in attached if p.get("PolicyName")]

        if not account_id:
            account_id = _extract_account_id_from_arn(role_arn)
        if not role_arn:
            continue

        roles.append(
            {
                "arn": role_arn,
                "roleName": role_name,
                "isPrivileged": _is_likely_privileged(role_name, attached_names),
                "policyRefs": attached_names,
            }
        )

        for policy in attached:
            p_arn = policy.get("PolicyArn")
            p_name = policy.get("PolicyName", "unknown-policy")
            if p_arn:
                _ensure_policy(p_arn, p_name)
                role_policy_edges.append((role_arn, p_arn))

    for user in user_items:
        user_arn = user.get("Arn")
        user_name = user.get("UserName", "unknown-user")
        attached = user.get("AttachedManagedPolicies", [])
        attached_names = [p.get("PolicyName") for p in attached if p.get("PolicyName")]

        if not account_id:
            account_id = _extract_account_id_from_arn(user_arn)
        if not user_arn:
            continue

        users.append(
            {
                "arn": user_arn,
                "userName": user_name,
                "isPrivileged": _is_likely_privileged(user_name, attached_names),
                "mfaEnabled": None,
            }
        )

        for policy in attached:
            p_arn = policy.get("PolicyArn")
            p_name = policy.get("PolicyName", "unknown-policy")
            if p_arn:
                _ensure_policy(p_arn, p_name)
                user_policy_edges.append((user_arn, p_arn))

    normalized_instances: List[Dict[str, Any]] = []
    instance_to_sg_edges: List[Tuple[str, str]] = []
    for instance in instances_raw:
        instance_id = instance.get("InstanceId")
        if not instance_id:
            continue

        tags = instance.get("Tags", [])
        name = next((t.get("Value") for t in tags if t.get("Key") == "Name"), None) or instance_id
        public_ip = instance.get("PublicIpAddress")

        normalized_instances.append(
            {
                "instanceId": instance_id,
                "name": name,
                "publicIp": public_ip,
                "criticality": "unknown",
                "ssmEnabled": None,
            }
        )

        for sg in instance.get("SecurityGroups", []):
            group_id = sg.get("GroupId")
            if group_id:
                instance_to_sg_edges.append((instance_id, group_id))

    normalized_sgs: List[Dict[str, Any]] = []
    internet_edges: List[Dict[str, Any]] = []

    for sg in security_groups_raw:
        group_id = sg.get("GroupId")
        if not group_id:
            continue

        normalized_sgs.append(
            {
                "groupId": group_id,
                "groupName": sg.get("GroupName", group_id),
                "description": sg.get("Description"),
                "vpcId": sg.get("VpcId"),
            }
        )

        for perm in sg.get("IpPermissions", []):
            from_port = perm.get("FromPort")
            to_port = perm.get("ToPort")
            protocol = perm.get("IpProtocol", "-1")

            for ipr in perm.get("IpRanges", []):
                cidr = ipr.get("CidrIp")
                if cidr == "0.0.0.0/0":
                    internet_edges.append(
                        {
                            "cidr": cidr,
                            "groupId": group_id,
                            "fromPort": from_port,
                            "toPort": to_port,
                            "proto": protocol,
                        }
                    )

            for ipr6 in perm.get("Ipv6Ranges", []):
                cidr6 = ipr6.get("CidrIpv6")
                if cidr6 == "::/0":
                    internet_edges.append(
                        {
                            "cidr": cidr6,
                            "groupId": group_id,
                            "fromPort": from_port,
                            "toPort": to_port,
                            "proto": protocol,
                        }
                    )

    if not account_id:
        account_id = "unknown-account"

    return {
        "account": {
            "accountId": account_id,
            "name": "aws-account",
            "env": "unknown",
        },
        "users": users,
        "roles": roles,
        "policies": policies,
        "instances": normalized_instances,
        "security_groups": normalized_sgs,
        "role_policy_edges": role_policy_edges,
        "user_policy_edges": user_policy_edges,
        "instance_sg_edges": instance_to_sg_edges,
        "internet_edges": internet_edges,
        "enum_summary": {
            "users": len(users),
            "roles": len(roles),
            "policies": len(policies),
            "instances": len(normalized_instances),
            "security_groups": len(normalized_sgs),
            "public_ingress_edges": len(internet_edges),
        },
    }


def _fetch_missing_policy_documents(iam_client, policies: List[Dict[str, Any]]) -> None:
    """Fetch policy documents for any policy stub that has document=None (e.g. AWS-managed)."""
    for policy in policies:
        if policy.get("document") is not None:
            continue
        arn = policy.get("arn")
        if not arn:
            continue
        try:
            meta = iam_client.get_policy(PolicyArn=arn)
            version_id = meta["Policy"]["DefaultVersionId"]
            version = iam_client.get_policy_version(PolicyArn=arn, VersionId=version_id)
            document = version["PolicyVersion"].get("Document")
            policy["document"] = json.dumps(document) if document else None
        except Exception as exc:  # noqa: BLE001
            # Silently skip if access is denied or policy is not retrievable
            print(f"[warn] Could not fetch document for {arn}: {exc}")


def run_real_enum_and_save(artifacts_dir: str = "artifacts") -> Dict[str, Any]:
    session = boto3.Session()
    iam_client = session.client("iam")
    ec2_client = session.client("ec2")

    iam_details = _paginate_iam_auth_details(iam_client)
    instances_raw = _paginate_ec2_instances(ec2_client)
    security_groups_raw = _paginate_security_groups(ec2_client)

    normalized = _normalize(iam_details, instances_raw, security_groups_raw)

    # Fill in documents for AWS-managed policies that had no PolicyVersionList
    _fetch_missing_policy_documents(iam_client, normalized["policies"])

    out_dir = Path(artifacts_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / "aws_enum_raw.json"
    normalized_path = out_dir / "aws_enum_normalized.json"

    raw_payload = {
        "iam": iam_details,
        "ec2_instances": instances_raw,
        "security_groups": security_groups_raw,
    }

    raw_path.write_text(json.dumps(raw_payload, indent=2, default=str), encoding="utf-8")
    normalized_path.write_text(json.dumps(normalized, indent=2, default=str), encoding="utf-8")

    normalized["artifacts"] = {
        "raw": str(raw_path),
        "normalized": str(normalized_path),
    }
    return normalized
