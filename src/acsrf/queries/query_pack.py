"""Predefined Cypher queries for the demo dataset."""

QUERY_PACK = {
    "user_to_secret": {
        "description": "Path from user to secret via role and bucket",
        "cypher": (
            "MATCH p=(u:IAMUser {userName:'alice'})-[:CAN_ASSUME]->(:IAMRole)-[:CAN_READ]->(:S3Bucket)-[:CONTAINS]->(s:Secret) "
            "RETURN p"
        ),
    },
    "internet_to_critical_compute": {
        "description": "Internet reachability to high-criticality compute",
        "cypher": "MATCH p=(:Internet {cidr:'0.0.0.0/0'})-[:CAN_REACH]->(e:EC2Instance {criticality:'high'}) RETURN p",
    },
    "assumable_privileged_roles": {
        "description": "Assumable privileged roles",
        "cypher": "MATCH (u:IAMUser {userName:'alice'})-[:CAN_ASSUME]->(r:IAMRole {isPrivileged:true}) RETURN u.userName, r.roleName",
    },
    "public_path_to_secret": {
        "description": "Public path to secret via compute pivot",
        "cypher": (
            "MATCH p=(:Internet)-[:CAN_REACH]->(:EC2Instance)<-[:CAN_SSM]-(:IAMRole)-[:CAN_READ]->(:S3Bucket)-[:CONTAINS]->(:Secret) "
            "RETURN p"
        ),
    },
    "shortest_user_to_secret": {
        "description": "Shortest path from user to specific secret (bounded)",
        "cypher": (
            "MATCH (u:IAMUser {userName:'alice'}), (s:Secret {name:'prod/db/password'}) "
            "MATCH p=shortestPath((u)-[*..5]->(s)) RETURN p"
        ),
    },
}
