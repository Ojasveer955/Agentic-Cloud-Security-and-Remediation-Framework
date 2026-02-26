"""CLI entrypoint for the graph-first demo MVP."""
import argparse
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

from acsrf.graph.schema_init import init_constraints
from acsrf.graph.ingest_dummy import ingest_dummy
from acsrf.data.dummy_cloud import get_dummy_dataset
from acsrf.queries.query_pack import QUERY_PACK


def _get_driver(uri: str, user: str, password: str):
    return GraphDatabase.driver(uri, auth=(user, password))


def cmd_init_db(args) -> None:
    driver = _get_driver(args.uri, args.user, args.password)
    init_constraints(driver)
    print("Constraints ensured.")


def _count_label(session, label: str) -> int:
    res = session.run(f"MATCH (n:{label}) RETURN count(n) AS c")
    return res.single()["c"]


def cmd_ingest_dummy(args) -> None:
    dataset = get_dummy_dataset()
    driver = _get_driver(args.uri, args.user, args.password)
    ingest_dummy(driver, dataset)
    with driver.session() as session:
        labels = ["Account", "IAMUser", "IAMRole", "IAMPolicy", "EC2Instance", "S3Bucket", "Secret", "Internet"]
        counts = {label: _count_label(session, label) for label in labels}
        print("Node counts:", counts)
    print("Ingestion complete (idempotent). Rerun should keep counts stable.")


def cmd_run_queries(args) -> None:
    driver = _get_driver(args.uri, args.user, args.password)
    with driver.session() as session:
        for name, meta in QUERY_PACK.items():
            result = session.run(meta["cypher"])
            rows = list(result)
            print(f"[{name}] {meta['description']} -> rows: {len(rows)}")
    print("Queries executed. Inspect Neo4j Browser for graph paths.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ACSRF demo (graph-first)")
    parser.add_argument("--uri", default=os.environ.get("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--user", default=os.environ.get("NEO4J_USER", "neo4j"))
    parser.add_argument("--password", default=os.environ.get("NEO4J_PASSWORD", "password"))

    sub = parser.add_subparsers(dest="command", required=True)

    sub_init = sub.add_parser("init-db", help="Create constraints")
    sub_init.set_defaults(func=cmd_init_db)

    sub_ingest = sub.add_parser("ingest-dummy", help="Ingest dummy dataset")
    sub_ingest.set_defaults(func=cmd_ingest_dummy)

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
