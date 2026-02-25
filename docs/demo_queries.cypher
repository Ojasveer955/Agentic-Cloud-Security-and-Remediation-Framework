// Demo queries for Neo4j Browser

// Path from user to secret via role and bucket
MATCH p=(u:IAMUser {userName:'alice'})-[:CAN_ASSUME]->(:IAMRole)-[:CAN_READ]->(:S3Bucket)-[:CONTAINS]->(s:Secret)
RETURN p;

// Internet reachability to high-criticality compute
MATCH p=(:Internet {cidr:'0.0.0.0/0'})-[:CAN_REACH]->(e:EC2Instance {criticality:'high'})
RETURN p;

// Assumable privileged roles
MATCH (u:IAMUser {userName:'alice'})-[:CAN_ASSUME]->(r:IAMRole {isPrivileged:true})
RETURN u.userName, r.roleName;

// Public path to secret via compute pivot
MATCH p=(:Internet)-[:CAN_REACH]->(:EC2Instance)<-[:CAN_SSM]-(:IAMRole)-[:CAN_READ]->(:S3Bucket)-[:CONTAINS]->(:Secret)
RETURN p;

// Shortest path from user to specific secret (bounded)
MATCH (u:IAMUser {userName:'alice'}), (s:Secret {name:'prod/db/password'})
MATCH p=shortestPath((u)-[*..5]->(s))
RETURN p;
