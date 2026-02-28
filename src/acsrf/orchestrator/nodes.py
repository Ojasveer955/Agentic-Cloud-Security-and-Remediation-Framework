"""Node functions for the ACSRF LangGraph orchestrator.

Each function receives the full ``ACSRFState`` and returns a *partial*
dict update that LangGraph merges back into the state.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from neo4j import GraphDatabase
from dotenv import load_dotenv

from acsrf.orchestrator.state import ACSRFState, MAX_INFLIGHT_FINDINGS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _ts() -> str:
    """ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def _neo4j_driver():
    """Build a Neo4j driver from env vars."""
    load_dotenv()
    return GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
    )


def _check_cancel(state: ACSRFState) -> dict | None:
    """Return an audit entry if cancellation was requested, else None."""
    if state.get("cancel_requested"):
        return {
            "audit_log": [{"timestamp": _ts(), "node": "cancel_check",
                           "action": "CANCELLED", "detail": "Human requested stop"}],
            "current_phase": "cancelled",
        }
    return None


# ---------------------------------------------------------------------------
# Node: Enumerate
# ---------------------------------------------------------------------------
def enumerate_node(state: ACSRFState) -> dict:
    """Run the AWS enumeration agent and store raw data in state."""
    cancel = _check_cancel(state)
    if cancel:
        return cancel

    from acsrf.agents.enum_agent import run_real_enum_and_save

    audit_entry = {"timestamp": _ts(), "node": "enumerate", "action": "Starting AWS enumeration"}

    try:
        enum_data = run_real_enum_and_save(artifacts_dir="artifacts")
        audit_entry["output_summary"] = f"Enumerated account: {enum_data.get('enum_summary', {})}"
        return {
            "enum_data": enum_data,
            "current_phase": "enumerate_done",
            "audit_log": [audit_entry],
        }
    except Exception as exc:
        audit_entry["action"] = "Enumeration FAILED"
        audit_entry["output_summary"] = str(exc)
        return {
            "current_phase": "enumerate_error",
            "errors": [f"Enumerate: {exc}"],
            "audit_log": [audit_entry],
        }


# ---------------------------------------------------------------------------
# Node: Ingest
# ---------------------------------------------------------------------------
def ingest_node(state: ACSRFState) -> dict:
    """Ingest enumerated data into Neo4j."""
    cancel = _check_cancel(state)
    if cancel:
        return cancel

    from acsrf.graph.ingest_real import ingest_real_enum
    from acsrf.graph.schema_init import init_constraints

    audit_entry = {"timestamp": _ts(), "node": "ingest", "action": "Ingesting into Neo4j"}

    try:
        driver = _neo4j_driver()
        init_constraints(driver)

        enum_data = state.get("enum_data", {})
        ingest_real_enum(driver, enum_data)

        # Collect node counts
        with driver.session() as session:
            labels = ["Account", "IAMUser", "IAMRole", "IAMPolicy",
                      "EC2Instance", "SecurityGroup", "Internet"]
            counts = {}
            for label in labels:
                res = session.run(f"MATCH (n:{label}) RETURN count(n) AS c")
                counts[label] = res.single()["c"]

        audit_entry["output_summary"] = f"Node counts: {counts}"
        return {
            "node_counts": counts,
            "current_phase": "ingest_done",
            "audit_log": [audit_entry],
        }
    except Exception as exc:
        audit_entry["action"] = "Ingestion FAILED"
        audit_entry["output_summary"] = str(exc)
        return {
            "current_phase": "ingest_error",
            "errors": [f"Ingest: {exc}"],
            "audit_log": [audit_entry],
        }


# ---------------------------------------------------------------------------
# Node: Analyze (NL2Cypher)
# ---------------------------------------------------------------------------
def analyze_node(state: ACSRFState) -> dict:
    """Run the NL2Cypher agent and extract findings."""
    cancel = _check_cancel(state)
    if cancel:
        return cancel

    from acsrf.agents.nl2cypher.agent import (
        run_nl2cypher, UnsafeCypherError, UnsupportedQueryError,
    )
    from acsrf.llm import get_llm_backend
    from acsrf.graph.viz import generate_html_visualizer

    question = state.get("nl_question", "What are the attack paths from the internet to privileged resources?")
    loop = state.get("loop_count", 0) + 1

    audit_entry = {
        "timestamp": _ts(), "node": "analyze",
        "action": f"NL2Cypher query (loop {loop})",
        "input_summary": f"Question: {question}",
    }

    try:
        driver = _neo4j_driver()
        llm = get_llm_backend()
        result = run_nl2cypher(question, driver, llm, summarize=True)

        # Build findings from the result
        new_findings = []
        out_dir = Path("artifacts")
        out_dir.mkdir(parents=True, exist_ok=True)

        if result.has_graph:
            finding = {
                "id": f"F-{loop:03d}",
                "source_node": "analyze",
                "severity": "HIGH",
                "type": "attack_path",
                "title": f"Attack path discovered (cycle {loop})",
                "description": result.summary or "Path found via NL2Cypher",
                "cypher": result.cypher,
                "graph_data": result.graph_data,
                "resources": [n["display"] for n in result.graph_data.get("nodes", [])],
            }
            new_findings.append(finding)

            # Auto-generate HTML visualizer
            viz_path = out_dir / "graph_viz.html"
            generate_html_visualizer(question, result.graph_data, result.summary, viz_path)

        # Save raw result JSON
        (out_dir / "nl2cypher_last_result.json").write_text(result.to_json(), encoding="utf-8")

        # ── Findings rotation: cap in-flight findings ─────────────
        existing_findings = state.get("findings", [])
        total = len(existing_findings) + len(new_findings)
        if total > MAX_INFLIGHT_FINDINGS:
            overflow = total - MAX_INFLIGHT_FINDINGS
            archived = existing_findings[:overflow]
            # Append archived findings to disk (never lost)
            archive_path = out_dir / "archived_findings.json"
            prev_archived = []
            if archive_path.exists():
                prev_archived = json.loads(archive_path.read_text(encoding="utf-8"))
            prev_archived.extend(archived)
            archive_path.write_text(json.dumps(prev_archived, indent=2, default=str), encoding="utf-8")
            audit_entry["detail"] = f"Rotated {overflow} older finding(s) to {archive_path}"

        audit_entry["output_summary"] = (
            f"Cypher: {result.cypher} | "
            f"Rows: {len(result.rows)} | "
            f"Graph: {len(result.graph_data.get('nodes', []))} nodes, "
            f"{len(result.graph_data.get('edges', []))} edges"
        )
        audit_entry["routed_to"] = "validate" if new_findings else "end"
        audit_entry["loop_count"] = loop

        return {
            "analysis_result": {
                "cypher": result.cypher,
                "row_count": len(result.rows),
                "summary": result.summary,
                "has_graph": result.has_graph,
            },
            "findings": new_findings,
            "loop_count": loop,
            "current_phase": "analyze_done",
            "audit_log": [audit_entry],
        }
    except (UnsafeCypherError, UnsupportedQueryError) as exc:
        audit_entry["action"] = f"Query blocked: {exc}"
        return {
            "loop_count": loop,
            "current_phase": "analyze_blocked",
            "errors": [f"Analyze: {exc}"],
            "audit_log": [audit_entry],
        }
    except Exception as exc:
        audit_entry["action"] = "Analysis FAILED"
        audit_entry["output_summary"] = str(exc)
        return {
            "loop_count": loop,
            "current_phase": "analyze_error",
            "errors": [f"Analyze: {exc}"],
            "audit_log": [audit_entry],
        }


# ---------------------------------------------------------------------------
# Node: Validate (stub)
# ---------------------------------------------------------------------------
def validate_node(state: ACSRFState) -> dict:
    """Stub: validation agent (MCP-connected) — not yet implemented."""
    audit_entry = {
        "timestamp": _ts(), "node": "validate",
        "action": "Validation skipped (stub — MCP agent not yet implemented)",
    }
    return {
        "validation_result": {"status": "skipped"},
        "current_phase": "validate_done",
        "audit_log": [audit_entry],
    }


# ---------------------------------------------------------------------------
# Node: Human Escalation (loop limit reached or cancel)
# ---------------------------------------------------------------------------
def human_escalation_node(state: ACSRFState) -> dict:
    """Paused for human intervention due to loop limit or cancellation."""
    reason = "cancel requested" if state.get("cancel_requested") else f"loop limit ({state.get('loop_count', '?')}) reached"
    audit_entry = {
        "timestamp": _ts(), "node": "human_escalation",
        "action": f"Human escalation: {reason}",
        "detail": f"Total findings so far: {len(state.get('findings', []))}",
    }
    return {
        "current_phase": "human_escalation",
        "audit_log": [audit_entry],
    }


# ---------------------------------------------------------------------------
# Node: HITL Gate
# ---------------------------------------------------------------------------
def hitl_gate_node(state: ACSRFState) -> dict:
    """Human reviews findings and decides whether to proceed to remediation.

    This node is used with ``interrupt_before`` so execution pauses
    *before* entering it, giving the human time to review.
    """
    findings = state.get("findings", [])
    audit_entry = {
        "timestamp": _ts(), "node": "hitl_gate",
        "action": f"HITL gate entered — {len(findings)} finding(s) for review",
    }
    return {
        "current_phase": "hitl_gate",
        "audit_log": [audit_entry],
    }


# ---------------------------------------------------------------------------
# Node: Remediate (stub)
# ---------------------------------------------------------------------------
def remediate_node(state: ACSRFState) -> dict:
    """Stub: remediation agent — not yet implemented."""
    audit_entry = {
        "timestamp": _ts(), "node": "remediate",
        "action": "Remediation skipped (stub — Terraform agent not yet implemented)",
    }
    return {
        "remediation_plan": "No remediation generated (stub)",
        "current_phase": "remediate_done",
        "audit_log": [audit_entry],
    }


# ---------------------------------------------------------------------------
# Node: Deep Analysis (optional)
# ---------------------------------------------------------------------------
def deep_analysis_node(state: ACSRFState) -> dict:
    """Feeds ALL findings to the LLM for holistic cross-correlation analysis.

    Only runs if ``deep_analysis_requested`` is True and total findings
    fit within the context window.
    """
    if not state.get("deep_analysis_requested"):
        return {
            "current_phase": "deep_analysis_skipped",
            "audit_log": [{"timestamp": _ts(), "node": "deep_analysis",
                           "action": "Skipped (not requested)"}],
        }

    from acsrf.llm import get_llm_backend

    findings = state.get("findings", [])

    audit_entry = {
        "timestamp": _ts(), "node": "deep_analysis",
        "action": f"Running deep cross-correlation analysis on {len(findings)} findings",
    }

    # Build the prompt
    findings_json = json.dumps(findings, indent=2, default=str)
    prompt = (
        "You are an expert cloud security analyst. Below is a JSON array of "
        "security findings discovered during an automated assessment of an AWS "
        "environment. Each finding may represent an individual attack path or "
        "misconfiguration.\n\n"
        "Analyze ALL findings holistically. Identify:\n"
        "1. Multi-step attack chains that span multiple findings\n"
        "2. Common root causes\n"
        "3. Priority ranking (which to fix first for maximum risk reduction)\n"
        "4. Any findings that, when combined, create critical escalation paths\n\n"
        f"Findings:\n```json\n{findings_json}\n```\n\n"
        "Provide a structured security report."
    )

    try:
        llm = get_llm_backend()
        summary = llm.generate(prompt, system="You are a senior cloud security analyst.")

        audit_entry["output_summary"] = f"Deep analysis complete ({len(summary)} chars)"
        return {
            "deep_analysis_result": summary,
            "current_phase": "deep_analysis_done",
            "audit_log": [audit_entry],
        }
    except Exception as exc:
        audit_entry["action"] = "Deep analysis FAILED"
        audit_entry["output_summary"] = str(exc)
        return {
            "current_phase": "deep_analysis_error",
            "errors": [f"Deep analysis: {exc}"],
            "audit_log": [audit_entry],
        }
