"""CLI entrypoint for the graph-first demo MVP."""
import argparse
import json
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

from acsrf.graph.schema_init import init_constraints
from acsrf.graph.ingest_real import ingest_real_enum
from acsrf.queries.query_pack import QUERY_PACK
from acsrf.agents.enum_agent import run_real_enum_and_save
from acsrf.agents.nl2cypher.agent import (
    run_nl2cypher,
    UnsafeCypherError,
    UnsupportedQueryError,
)
from acsrf.graph.viz import generate_html_visualizer
from acsrf.llm import get_llm_backend


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
        labels = ["Account", "IAMUser", "IAMRole", "IAMPolicy", "EC2Instance", "SecurityGroup", "Internet"]
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


def cmd_query_nl(args) -> None:
    question = args.question
    print(f"\n{'='*60}")
    print(f"  NL2Cypher Query Agent")
    print(f"{'='*60}")
    print(f"  Question: {question}")
    print(f"{'='*60}\n")

    driver = _driver_from_args(args)
    llm = get_llm_backend()

    try:
        result = run_nl2cypher(question, driver, llm, summarize=not args.no_summary)
    except UnsafeCypherError as exc:
        print(f"[BLOCKED] {exc}")
        return
    except UnsupportedQueryError as exc:
        print(f"[UNSUPPORTED] {exc}")
        return

    # Generated Cypher
    print("Generated Cypher:")
    print(f"  {result.cypher}\n")

    # Row count
    print(f"Results: {len(result.rows)} row(s) returned\n")

    # Graph visualization data
    if result.has_graph:
        g = result.graph_data
        print(f"Graph data: {len(g['nodes'])} nodes, {len(g['edges'])} edges")
        print("  Nodes:")
        for node in g["nodes"][:15]:
            label = node["labels"][0] if node["labels"] else "?"
            print(f"    [{label}] {node['display']}")
        if len(g["nodes"]) > 15:
            print(f"    ... and {len(g['nodes']) - 15} more")
        print("  Edges:")
        for edge in g["edges"][:15]:
            print(f"    -[:{edge['type']}]->")
        if len(g["edges"]) > 15:
            print(f"    ... and {len(g['edges']) - 15} more")
        print()

    # Summary
    if result.summary:
        print("Security Summary:")
        print(result.summary)
        print()

    # Save full result to artifacts
    from pathlib import Path as FilePath
    out_dir = FilePath("artifacts")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "nl2cypher_last_result.json"
    out_path.write_text(result.to_json(), encoding="utf-8")
    print(f"Full JSON result saved to: {out_path}")

    # Auto-generate HTML visualizer if we have graph data
    if result.has_graph:
        viz_path = out_dir / "graph_viz.html"
        generate_html_visualizer(question, result.graph_data, result.summary, viz_path)
        print(f"Graph Plotly HTML generated at: file:///{viz_path.absolute().as_posix()}")


# =====================================================================
#  orchestrate — full LangGraph pipeline
# =====================================================================
def cmd_orchestrate(args) -> None:
    import uuid
    from acsrf.orchestrator.graph import build_orchestrator_graph, save_audit_log

    question = args.question
    deep = args.deep_analysis
    thread_id = args.resume or str(uuid.uuid4())[:8]

    print(f"\n{'='*60}")
    print(f"  ACSRF Orchestrator (LangGraph)")
    print(f"{'='*60}")
    print(f"  Question : {question}")
    print(f"  Thread   : {thread_id}")
    print(f"  Deep mode: {'ON' if deep else 'OFF'}")
    print(f"{'='*60}\n")

    compiled, checkpointer = build_orchestrator_graph()
    config = {"configurable": {"thread_id": thread_id}}

    # Initial state
    initial_state = {
        "nl_question": question,
        "deep_analysis_requested": deep,
        "loop_count": 0,
        "cancel_requested": False,
        "human_approved": False,
        "audit_log": [],
        "errors": [],
        "findings": [],
    }

    # First run — will pause at interrupt_before nodes
    print("[*] Starting pipeline...\n")
    result_state = None

    try:
        for event in compiled.stream(initial_state, config, stream_mode="values"):
            result_state = event
            phase = event.get("current_phase", "")
            if phase:
                print(f"  [{phase}]")
    except Exception as exc:
        print(f"\n[!] Pipeline error: {exc}")
        if result_state:
            save_audit_log(result_state)
            print(f"  Audit log saved to artifacts/orchestrator_audit.json")
        return

    if result_state is None:
        print("[!] No state returned.")
        return

    # Check if we hit an interrupt (HITL gate or human escalation)
    snapshot = compiled.get_state(config)
    while snapshot.next:
        interrupted_at = snapshot.next[0] if snapshot.next else "unknown"
        print(f"\n{'='*60}")
        print(f"  PAUSED at: {interrupted_at}")
        print(f"{'='*60}")

        # Show findings summary
        findings = result_state.get("findings", [])
        print(f"\n  Findings so far: {len(findings)}")
        for f in findings:
            sev = f.get("severity", "?")
            title = f.get("title", "Untitled")
            print(f"    [{sev}] {title}")

        # Show errors if any
        errors = result_state.get("errors", [])
        if errors:
            print(f"\n  Errors: {len(errors)}")
            for e in errors:
                print(f"    ! {e}")

        # Human decision
        if interrupted_at == "hitl_gate":
            print("\n  Options:")
            print("    [a] Approve findings → proceed to remediation")
            print("    [r] Reject → end pipeline")
            print("    [c] Cancel pipeline")
            choice = input("\n  Your choice (a/r/c): ").strip().lower()

            if choice == "a":
                update = {"human_approved": True, "human_feedback": "Approved by human"}
            elif choice == "c":
                update = {"cancel_requested": True}
            else:
                update = {"human_approved": False, "human_feedback": "Rejected by human"}

            compiled.update_state(config, update)

        elif interrupted_at == "human_escalation":
            print("\n  The pipeline hit its loop limit or a cancel was requested.")
            print("  Options:")
            print("    [c] Continue (reset loop counter)")
            print("    [s] Stop here")
            choice = input("\n  Your choice (c/s): ").strip().lower()

            if choice == "c":
                compiled.update_state(config, {"loop_count": 0, "cancel_requested": False})
            else:
                print("\n  Pipeline stopped by human.")
                save_audit_log(result_state)
                print(f"  Audit log saved to artifacts/orchestrator_audit.json")
                return

        # Resume from interrupt
        print("\n[*] Resuming pipeline...\n")
        for event in compiled.stream(None, config, stream_mode="values"):
            result_state = event
            phase = event.get("current_phase", "")
            if phase:
                print(f"  [{phase}]")

        snapshot = compiled.get_state(config)

    # Pipeline complete
    print(f"\n{'='*60}")
    print(f"  Pipeline Complete")
    print(f"{'='*60}")

    findings = result_state.get("findings", [])
    print(f"  Total findings: {len(findings)}")
    print(f"  Total errors: {len(result_state.get('errors', []))}")
    print(f"  Total audit entries: {len(result_state.get('audit_log', []))}")

    if result_state.get("deep_analysis_result"):
        print(f"\n  Deep Analysis Report:")
        print(f"  {result_state['deep_analysis_result'][:500]}...")

    save_audit_log(result_state)
    print(f"\n  Audit log saved to: artifacts/orchestrator_audit.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="ACSRF — Agentic Cloud-Native Security & Remediation Framework",
    )
    parser.add_argument("--uri", default=None)
    parser.add_argument("--user", default=None)
    parser.add_argument("--password", default=None)

    # Orchestrator args on the top-level parser (default mode)
    parser.add_argument("--question", type=str,
                        default="What are the attack paths from the internet to privileged resources?",
                        help="Security question for the analysis agent")
    parser.add_argument("--deep-analysis", action="store_true",
                        help="Run holistic cross-correlation analysis at the end")
    parser.add_argument("--resume", type=str, default=None,
                        help="Resume a previous pipeline run by thread ID")

    sub = parser.add_subparsers(dest="command")

    sub_init = sub.add_parser("init-db", help="Create Neo4j constraints")
    sub_init.set_defaults(func=cmd_init_db)

    sub_real = sub.add_parser("enum-real", help="Enumerate real AWS resources and ingest results")
    sub_real.set_defaults(func=cmd_enum_real)

    sub_queries = sub.add_parser("run-queries", help="Run predefined queries")
    sub_queries.set_defaults(func=cmd_run_queries)

    sub_nl = sub.add_parser("query-nl", help="Ask a natural-language security question")
    sub_nl.add_argument("question", type=str, help="Your security question in plain English")
    sub_nl.add_argument("--no-summary", action="store_true", help="Skip LLM summarization of results")
    sub_nl.set_defaults(func=cmd_query_nl)

    sub_orch = sub.add_parser("orchestrate", help="Run the full LangGraph agent pipeline")
    sub_orch.add_argument("--question", type=str,
                          default="What are the attack paths from the internet to privileged resources?",
                          help="Security question for the analysis agent")
    sub_orch.add_argument("--deep-analysis", action="store_true",
                          help="Run holistic cross-correlation analysis at the end")
    sub_orch.add_argument("--resume", type=str, default=None,
                          help="Resume a previous pipeline run by thread ID")
    sub_orch.set_defaults(func=cmd_orchestrate)

    return parser


def main() -> None:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args()

    # Default to orchestrator when no subcommand is given
    func = getattr(args, "func", None)
    if func is None:
        cmd_orchestrate(args)
    else:
        func(args)


if __name__ == "__main__":
    main()

