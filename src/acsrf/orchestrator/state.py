"""Shared state schema for the ACSRF LangGraph orchestrator.

Uses ``Annotated`` reducers so list fields accumulate (append)
rather than overwrite across node transitions.
"""
from __future__ import annotations

import operator
from typing import Annotated, TypedDict

# Maximum number of agent-loop iterations before forcing human escalation.
MAX_LOOP_COUNT = 10

# Maximum in-flight findings before older ones are archived to SQLite.
MAX_INFLIGHT_FINDINGS = 100


class ACSRFState(TypedDict, total=False):
    """Shared state passed between every node in the orchestrator graph.

    Fields marked ``Annotated[list, operator.add]`` are **accumulative**:
    each node appends to them rather than replacing them.  All other
    fields follow last-writer-wins semantics.
    """

    # ── Accumulative fields (append-only) ─────────────────────────
    audit_log: Annotated[list[dict], operator.add]
    errors: Annotated[list[str], operator.add]
    findings: Annotated[list[dict], operator.add]

    # ── Overwrite fields (latest value wins) ──────────────────────
    # Enum stage
    enum_data: dict
    node_counts: dict

    # Analysis stage
    nl_question: str
    analysis_result: dict

    # Validation stage (stub)
    validation_result: dict

    # HITL
    human_approved: bool
    human_feedback: str

    # Remediation stage (stub)
    remediation_plan: str

    # Deep analysis
    deep_analysis_requested: bool
    deep_analysis_result: str

    # ── Control flow ──────────────────────────────────────────────
    current_phase: str
    loop_count: int
    cancel_requested: bool
