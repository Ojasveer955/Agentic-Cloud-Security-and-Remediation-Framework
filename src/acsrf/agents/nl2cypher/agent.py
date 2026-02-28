"""Core NL-to-Cypher agent: translate → validate → execute → visualize → summarize."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from neo4j import Driver, graph as neo4j_graph

from acsrf.llm.backend import LLMBackend
from acsrf.agents.nl2cypher.schema_context import get_schema_context
from acsrf.agents.nl2cypher.prompts import build_cypher_prompt, build_summarize_prompt


# ---------------------------------------------------------------------------
# Safety validation
# ---------------------------------------------------------------------------
_WRITE_PATTERN = re.compile(
    r"\b(CREATE|MERGE|SET|DELETE|DETACH|REMOVE|DROP|CALL|LOAD\s+CSV|FOREACH)\b",
    re.IGNORECASE,
)

_UNSUPPORTED_MARKER = "// UNSUPPORTED"


class UnsafeCypherError(Exception):
    """Raised when the LLM produces a Cypher query containing write operations."""


class UnsupportedQueryError(Exception):
    """Raised when the LLM signals the question cannot be answered."""


def _validate_cypher(query: str) -> str:
    """Strip whitespace, remove markdown fences, and reject write operations."""
    # Strip markdown code fences the LLM might wrap around the query
    cleaned = query.strip()
    # Handle ```cypher ... ``` blocks (multiline)
    fence_match = re.search(r"```(?:cypher)?\s*\n?(.*?)\n?\s*```", cleaned, re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1).strip()
    cleaned = cleaned.strip()

    if _UNSUPPORTED_MARKER in cleaned:
        raise UnsupportedQueryError(
            "The model indicated this question cannot be answered with the current graph schema."
        )

    if _WRITE_PATTERN.search(cleaned):
        raise UnsafeCypherError(
            f"Generated Cypher contains write operations and was blocked:\n{cleaned}"
        )

    return cleaned


# ---------------------------------------------------------------------------
# Graph data extraction (for visualization)
# ---------------------------------------------------------------------------
def _extract_graph_elements(records: list) -> Dict[str, Any]:
    """Walk Neo4j result records and pull out unique nodes & relationships.

    Returns a dict with ``nodes`` and ``edges`` lists suitable for
    front-end graph rendering (e.g. vis.js / D3 / Cytoscape).
    """
    nodes_map: Dict[int, Dict[str, Any]] = {}  # element_id -> node dict
    edges_list: List[Dict[str, Any]] = []
    seen_edge_ids: set = set()

    def _process_node(node: neo4j_graph.Node) -> None:
        eid = node.element_id
        if eid in nodes_map:
            return
        labels = list(node.labels)
        props = dict(node)
        # Build a human-friendly display label
        display = props.get("userName") or props.get("roleName") or props.get(
            "policyName") or props.get("name") or props.get(
            "instanceId") or props.get("groupName") or props.get(
            "bucketName") or props.get("cidr") or props.get(
            "accountId") or labels[0] if labels else "?"
        nodes_map[eid] = {
            "id": eid,
            "labels": labels,
            "display": display,
            "properties": _safe_props(props),
        }

    def _process_relationship(rel: neo4j_graph.Relationship) -> None:
        eid = rel.element_id
        if eid in seen_edge_ids:
            return
        seen_edge_ids.add(eid)
        edges_list.append({
            "id": eid,
            "type": rel.type,
            "startNode": rel.start_node.element_id,
            "endNode": rel.end_node.element_id,
            "properties": _safe_props(dict(rel)),
        })
        # Ensure both endpoint nodes are captured
        _process_node(rel.start_node)
        _process_node(rel.end_node)

    def _process_path(path: neo4j_graph.Path) -> None:
        for node in path.nodes:
            _process_node(node)
        for rel in path.relationships:
            _process_relationship(rel)

    for record in records:
        for value in record.values():
            if isinstance(value, neo4j_graph.Path):
                _process_path(value)
            elif isinstance(value, neo4j_graph.Node):
                _process_node(value)
            elif isinstance(value, neo4j_graph.Relationship):
                _process_relationship(value)

    return {
        "nodes": list(nodes_map.values()),
        "edges": edges_list,
    }


def _safe_props(props: dict) -> dict:
    """Make property values JSON-serializable."""
    out = {}
    for k, v in props.items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v
        elif isinstance(v, list):
            out[k] = v
        else:
            out[k] = str(v)
    return out


# ---------------------------------------------------------------------------
# Tabular result flattening (for non-path queries)
# ---------------------------------------------------------------------------
def _flatten_records(records: list) -> List[Dict[str, Any]]:
    """Convert Neo4j records to a list of plain dicts for JSON output."""
    rows = []
    for record in records:
        row = {}
        for key in record.keys():
            val = record[key]
            if isinstance(val, neo4j_graph.Node):
                row[key] = {**dict(val), "_labels": list(val.labels)}
            elif isinstance(val, neo4j_graph.Relationship):
                row[key] = {**dict(val), "_type": val.type}
            elif isinstance(val, neo4j_graph.Path):
                row[key] = f"Path(length={len(val)})"
            else:
                row[key] = val
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Main agent entry-point
# ---------------------------------------------------------------------------
class NL2CypherResult:
    """Structured result bundle from a NL2Cypher query."""

    def __init__(
        self,
        question: str,
        cypher: str,
        rows: List[Dict[str, Any]],
        graph_data: Dict[str, Any],
        summary: str,
    ):
        self.question = question
        self.cypher = cypher
        self.rows = rows
        self.graph_data = graph_data  # {nodes: [...], edges: [...]}
        self.summary = summary

    @property
    def has_graph(self) -> bool:
        return bool(self.graph_data.get("nodes"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "cypher": self.cypher,
            "row_count": len(self.rows),
            "rows": self.rows,
            "graph": self.graph_data,
            "summary": self.summary,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)


def run_nl2cypher(
    question: str,
    driver: Driver,
    llm: LLMBackend,
    *,
    summarize: bool = True,
) -> NL2CypherResult:
    """Full NL → Cypher → Execute → Visualize → Summarize pipeline.

    Parameters
    ----------
    question : str
        Natural-language security question from the user.
    driver : neo4j.Driver
        Active Neo4j driver.
    llm : LLMBackend
        The LLM backend to use for generation and summarization.
    summarize : bool
        Whether to ask the LLM to summarize the raw results.

    Returns
    -------
    NL2CypherResult
        Bundle containing generated Cypher, raw rows, graph data, and summary.
    """
    # 1. Build prompt and generate Cypher
    schema_ctx = get_schema_context()
    system, user_prompt = build_cypher_prompt(question, schema_ctx)
    raw_cypher = llm.generate(user_prompt, system=system)

    # 2. Validate (strips fences, rejects writes)
    cypher = _validate_cypher(raw_cypher)

    # 3. Execute (read-only transaction)
    with driver.session() as session:
        result = session.run(cypher)
        records = list(result)

    # 4. Extract graph elements for visualization
    graph_data = _extract_graph_elements(records)

    # 5. Flatten for tabular / JSON output
    rows = _flatten_records(records)

    # 6. Summarize (optional)
    summary = ""
    if summarize and rows:
        # Feed at most 20 rows to avoid blowing the context window
        truncated = rows[:20]
        sum_system, sum_user = build_summarize_prompt(cypher, json.dumps(truncated, default=str))
        summary = llm.generate(sum_user, system=sum_system)

    return NL2CypherResult(
        question=question,
        cypher=cypher,
        rows=rows,
        graph_data=graph_data,
        summary=summary,
    )
