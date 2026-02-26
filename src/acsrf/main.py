"""CLI entrypoint for the graph-first demo MVP."""
import argparse
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

from acsrf.graph.schema_init import init_constraints
from acsrf.graph.ingest_real import ingest_real_enum
from acsrf.queries.query_pack import QUERY_PACK
from acsrf.agents.enum_agent import run_real_enum_and_save


def _get_driver(uri: str, user: str, password: str):
    return GraphDatabase.driver(uri, auth=(user, password))


def _resolve_neo4j_config(args):
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


def _driver_from_args(args):
    uri, user, password = _resolve_neo4j_config(args)
    return _get_driver(uri, user, password)


def cmd_init_db(args) -> None:
    driver = _driver_from_args(args)
    init_constraints(driver)
    print("Constraints ensured.")


def _count_label(session, label: str) -> int:
    res = session.run(f"MATCH (n:{label}) RETURN count(n) AS c")
    return res.single()["c"]



def cmd_enum_real(args) -> None:
    print("Running real AWS enumeration agent...")
    enum_data = run_real_enum_and_save(artifacts_dir="artifacts")
    print("Enumeration summary:", enum_data.get("enum_summary", {}))
    print("Artifacts:", enum_data.get("artifacts", {}))

    driver = _driver_from_args(args)
    ingest_real_enum(driver, enum_data)

    with driver.session() as session:
        labels = ["Account", "IAMRole", "IAMPolicy", "EC2Instance", "SecurityGroup", "Internet"]
        counts = {label: _count_label(session, label) for label in labels}
        print("Node counts after real enum ingest:", counts)

    print("Real enum ingestion complete.")


def cmd_run_queries(args) -> None:
    driver = _driver_from_args(args)
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
    sub_init.set_defaults(func=cmd_init_db)

    sub_real = sub.add_parser("enum-real", help="Enumerate real AWS resources and ingest results")
    sub_real.set_defaults(func=cmd_enum_real)

    sub_queries = sub.add_parser("run-queries", help="Run predefined queries")
    sub_queries.set_defaults(func=cmd_run_queries)

    return parser


def main() -> None:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
