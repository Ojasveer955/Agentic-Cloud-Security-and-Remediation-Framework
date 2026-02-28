"""Build and compile the ACSRF LangGraph StateGraph.

Wires all node functions, conditional edges, HITL interrupts,
and the SqliteSaver checkpointer.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.sqlite import SqliteSaver

from acsrf.orchestrator.state import ACSRFState, MAX_LOOP_COUNT
from acsrf.orchestrator.nodes import (
    enumerate_node,
    ingest_node,
    analyze_node,
    validate_node,
    human_escalation_node,
    hitl_gate_node,
    remediate_node,
    deep_analysis_node,
)


# ---------------------------------------------------------------------------
# Conditional-edge routers
# ---------------------------------------------------------------------------
def _after_analyze(state: ACSRFState) -> str:
    """Decide what happens after the Analyze node."""
    if state.get("cancel_requested"):
        return "human_escalation"
    if state.get("loop_count", 0) >= MAX_LOOP_COUNT:
        return "human_escalation"

    # Check if there are any findings from this cycle
    analysis = state.get("analysis_result", {})
    if analysis.get("has_graph"):
        return "validate"

    # No findings — skip straight to HITL for review
    return "hitl_gate"


def _after_hitl(state: ACSRFState) -> str:
    """Route based on human decision at the HITL gate."""
    if state.get("human_approved"):
        return "remediate"
    return END


def _after_remediate(state: ACSRFState) -> str:
    """Route to deep analysis if requested, otherwise end."""
    if state.get("deep_analysis_requested"):
        return "deep_analysis"
    return END


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------
def build_orchestrator_graph(db_path: str = "artifacts/orchestrator.db") -> tuple:
    """Construct and compile the ACSRF orchestrator.

    Returns
    -------
    (compiled_graph, checkpointer)
        The compiled LangGraph app and its SqliteSaver so both can
        be used by the CLI runner.
    """
    graph = StateGraph(ACSRFState)

    # Register nodes
    graph.add_node("enumerate", enumerate_node)
    graph.add_node("ingest", ingest_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("validate", validate_node)
    graph.add_node("human_escalation", human_escalation_node)
    graph.add_node("hitl_gate", hitl_gate_node)
    graph.add_node("remediate", remediate_node)
    graph.add_node("deep_analysis", deep_analysis_node)

    # Linear edges: START → enumerate → ingest → analyze
    graph.add_edge(START, "enumerate")
    graph.add_edge("enumerate", "ingest")
    graph.add_edge("ingest", "analyze")

    # Conditional: analyze → validate | hitl_gate | human_escalation
    graph.add_conditional_edges("analyze", _after_analyze, {
        "validate": "validate",
        "hitl_gate": "hitl_gate",
        "human_escalation": "human_escalation",
    })

    # validate → hitl_gate
    graph.add_edge("validate", "hitl_gate")

    # human_escalation → END (after interrupt)
    graph.add_edge("human_escalation", END)

    # Conditional: hitl_gate → remediate | END
    graph.add_conditional_edges("hitl_gate", _after_hitl, {
        "remediate": "remediate",
        END: END,
    })

    # Conditional: remediate → deep_analysis | END
    graph.add_conditional_edges("remediate", _after_remediate, {
        "deep_analysis": "deep_analysis",
        END: END,
    })

    # deep_analysis → END
    graph.add_edge("deep_analysis", END)

    # Compile with HITL interrupts and SQLite persistence
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    compiled = graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["hitl_gate", "human_escalation"],
    )

    return compiled, checkpointer


def save_audit_log(state: ACSRFState, output_path: str = "artifacts/orchestrator_audit.json") -> None:
    """Dump the accumulated audit log to a JSON file."""
    audit = state.get("audit_log", [])
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(
        json.dumps(audit, indent=2, default=str),
        encoding="utf-8",
    )
