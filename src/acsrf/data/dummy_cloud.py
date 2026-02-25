"""Static dummy cloud dataset for the demo graph."""

def get_dummy_dataset() -> dict:
    account = {
        "accountId": "111111111111",
        "name": "demo-account",
        "env": "dev",
    }

    users = [
        {
            "arn": "arn:aws:iam::111111111111:user/alice",
            "userName": "alice",
            "mfaEnabled": True,
            "riskTier": "medium",
        },
        {
            "arn": "arn:aws:iam::111111111111:user/bob",
            "userName": "bob",
            "mfaEnabled": False,
            "riskTier": "high",
        },
    ]

    roles = [
        {
            "arn": "arn:aws:iam::111111111111:role/AdminRole",
            "roleName": "AdminRole",
            "isPrivileged": True,
            "policyRefs": ["AdministratorAccess"],
        },
        {
            "arn": "arn:aws:iam::111111111111:role/SSMRole",
            "roleName": "SSMRole",
            "isPrivileged": False,
            "policyRefs": ["AmazonSSMManagedInstanceCore"],
        },
        {
            "arn": "arn:aws:iam::111111111111:role/ReadBucketRole",
            "roleName": "ReadBucketRole",
            "isPrivileged": False,
            "policyRefs": ["S3ReadOnly"],
        },
    ]

    instances = [
        {
            "instanceId": "i-0demo12345",
            "name": "frontend",
            "publicIp": "1.2.3.4",
            "criticality": "high",
            "ssmEnabled": True,
        },
        {
            "instanceId": "i-0demo67890",
            "name": "backend",
            "publicIp": None,
            "criticality": "medium",
            "ssmEnabled": True,
        },
    ]

    buckets = [
        {
            "bucketName": "demo-logs",
            "arn": "arn:aws:s3:::demo-logs",
            "publicRead": False,
            "encryption": "AES256",
        },
        {
            "bucketName": "demo-secrets",
            "arn": "arn:aws:s3:::demo-secrets",
            "publicRead": False,
            "encryption": "AES256",
        },
    ]

    secrets = [
        {
            "secretId": "sec-001",
            "name": "prod/db/password",
            "classification": "high",
        },
    ]

    internet = {"cidr": "0.0.0.0/0"}

    relationships = [
        # Account scoping
        ("IAMUser", "IN_ACCOUNT", "Account", "arn", "accountId"),
        ("IAMRole", "IN_ACCOUNT", "Account", "arn", "accountId"),
        ("EC2Instance", "IN_ACCOUNT", "Account", "instanceId", "accountId"),
        ("S3Bucket", "IN_ACCOUNT", "Account", "bucketName", "accountId"),
        ("Secret", "IN_ACCOUNT", "Account", "secretId", "accountId"),
        # Permissions and reachability
        ("IAMUser", "CAN_ASSUME", "IAMRole", "arn", "arn"),
        ("IAMRole", "CAN_SSM", "EC2Instance", "arn", "instanceId"),
        ("IAMRole", "CAN_READ", "S3Bucket", "arn", "bucketName"),
        ("S3Bucket", "CONTAINS", "Secret", "bucketName", "secretId"),
        ("Internet", "CAN_REACH", "EC2Instance", "cidr", "instanceId"),
    ]

    # Relationship instances keyed by tuple identifiers
    rel_instances = [
        {"type": "IN_ACCOUNT", "from": ("IAMUser", "arn", users[0]["arn"]), "to": ("Account", "accountId", account["accountId"]), "props": {}},
        {"type": "IN_ACCOUNT", "from": ("IAMUser", "arn", users[1]["arn"]), "to": ("Account", "accountId", account["accountId"]), "props": {}},
        {"type": "IN_ACCOUNT", "from": ("IAMRole", "arn", roles[0]["arn"]), "to": ("Account", "accountId", account["accountId"]), "props": {}},
        {"type": "IN_ACCOUNT", "from": ("IAMRole", "arn", roles[1]["arn"]), "to": ("Account", "accountId", account["accountId"]), "props": {}},
        {"type": "IN_ACCOUNT", "from": ("IAMRole", "arn", roles[2]["arn"]), "to": ("Account", "accountId", account["accountId"]), "props": {}},
        {"type": "IN_ACCOUNT", "from": ("EC2Instance", "instanceId", instances[0]["instanceId"]), "to": ("Account", "accountId", account["accountId"]), "props": {}},
        {"type": "IN_ACCOUNT", "from": ("EC2Instance", "instanceId", instances[1]["instanceId"]), "to": ("Account", "accountId", account["accountId"]), "props": {}},
        {"type": "IN_ACCOUNT", "from": ("S3Bucket", "bucketName", buckets[0]["bucketName"]), "to": ("Account", "accountId", account["accountId"]), "props": {}},
        {"type": "IN_ACCOUNT", "from": ("S3Bucket", "bucketName", buckets[1]["bucketName"]), "to": ("Account", "accountId", account["accountId"]), "props": {}},
        {"type": "IN_ACCOUNT", "from": ("Secret", "secretId", secrets[0]["secretId"]), "to": ("Account", "accountId", account["accountId"]), "props": {}},
        # Alice can assume AdminRole
        {"type": "CAN_ASSUME", "from": ("IAMUser", "arn", users[0]["arn"]), "to": ("IAMRole", "arn", roles[0]["arn"]), "props": {"condition": "MFA"}},
        # AdminRole can reach instances via SSM
        {"type": "CAN_SSM", "from": ("IAMRole", "arn", roles[0]["arn"]), "to": ("EC2Instance", "instanceId", instances[0]["instanceId"]), "props": {}},
        {"type": "CAN_SSM", "from": ("IAMRole", "arn", roles[0]["arn"]), "to": ("EC2Instance", "instanceId", instances[1]["instanceId"]), "props": {}},
        # AdminRole can read buckets
        {"type": "CAN_READ", "from": ("IAMRole", "arn", roles[0]["arn"]), "to": ("S3Bucket", "bucketName", buckets[0]["bucketName"]), "props": {}},
        {"type": "CAN_READ", "from": ("IAMRole", "arn", roles[0]["arn"]), "to": ("S3Bucket", "bucketName", buckets[1]["bucketName"]), "props": {}},
        # Buckets contain secret
        {"type": "CONTAINS", "from": ("S3Bucket", "bucketName", buckets[1]["bucketName"]), "to": ("Secret", "secretId", secrets[0]["secretId"]), "props": {}},
        # Internet reachability to high-criticality instance
        {"type": "CAN_REACH", "from": ("Internet", "cidr", internet["cidr"]), "to": ("EC2Instance", "instanceId", instances[0]["instanceId"]), "props": {"port": 443, "proto": "tcp"}},
    ]

    return {
        "account": account,
        "users": users,
        "roles": roles,
        "instances": instances,
        "buckets": buckets,
        "secrets": secrets,
        "internet": internet,
        "relationships": rel_instances,
    }
