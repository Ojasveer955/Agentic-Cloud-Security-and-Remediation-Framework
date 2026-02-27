"""CLI entrypoint for the graph-first demo MVP."""
import argparse
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

from acsrf.graph.schema_init import initialize_database_constraints
from acsrf.graph.ingest_real import ingest_aws_data_to_neo4j
from acsrf.queries.query_pack import QUERY_PACK
from acsrf.agents.enum_agent import execute_aws_enumeration_and_save


def _create_neo4j_driver(uri: str, user: str, password: str):
    return GraphDatabase.driver(uri, auth=(user, password))


def _get_neo4j_credentials(args):
    uri = args.uri or os.environ.get("NEO4J_URI")
    user = args.user or os.environ.get("NEO4J_USER")
    password = args.password or os.environ.get("NEO4J_PASSWORD")

    missing = [
        name
        for name, value in (
            ("NEO4J_URI", uri),
            ("NEO4J_USER", user),
            ("NEO4J_PASSWORD", password),
        )
        if not value
    ]
    if missing:
        names = ", ".join(missing)
        raise ValueError(f"Missing Neo4j configuration: {names}. Set them in .env or pass --uri/--user/--password.")
    return uri, user, password


def _initialize_driver_from_args(args):
    uri, user, password = _get_neo4j_credentials(args)
    return _create_neo4j_driver(uri, user, password)


def handle_init_db_command(args) -> None:
    driver = _initialize_driver_from_args(args)
    initialize_database_constraints(driver)
    print("Constraints ensured.")


def _get_node_count_by_label(session, label: str) -> int:
    res = session.run(f"MATCH (n:{label}) RETURN count(n) AS c")
    return res.single()["c"]



def handle_enum_real_command(args) -> None:
    print("Running real AWS enumeration agent...")
    enum_data = execute_aws_enumeration_and_save(artifacts_dir="artifacts")
    print("Enumeration summary:", enum_data.get("enum_summary", {}))
    print("Artifacts:", enum_data.get("artifacts", {}))

    driver = _initialize_driver_from_args(args)
    ingest_aws_data_to_neo4j(driver, enum_data)

    with driver.session() as session:
        labels = ["Account", "IAMUser", "IAMRole", "IAMPolicy", "EC2Instance", "SecurityGroup", "Internet"]
        counts = {label: _get_node_count_by_label(session, label) for label in labels}
        print("Node counts after real enum ingest:", counts)

    print("Real enum ingestion complete.")


def handle_run_queries_command(args) -> None:
    driver = _initialize_driver_from_args(args)
    with driver.session() as session:
        for name, meta in QUERY_PACK.items():
            result = session.run(meta["cypher"])
            rows = list(result)
            print(f"[{name}] {meta['description']} -> rows: {len(rows)}")
    print("Queries executed. Inspect Neo4j Browser for graph paths.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ACSRF demo (graph-first)")
    parser.add_argument("--uri", default=None)
    parser.add_argument("--user", default=None)
    parser.add_argument("--password", default=None)

    sub = parser.add_subparsers(dest="command", required=True)

    sub_init = sub.add_parser("init-db", help="Create constraints")
    sub_init.set_defaults(func=handle_init_db_command)

    sub_real = sub.add_parser("enum-real", help="Enumerate real AWS resources and ingest results")
    sub_real.set_defaults(func=handle_enum_real_command)

    sub_queries = sub.add_parser("run-queries", help="Run predefined queries")
    sub_queries.set_defaults(func=handle_run_queries_command)

    return parser


def main() -> None:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
