"""Local HTML visualizer for Neo4j graph data.

Generates a standalone HTML file using vis-network.js to render
the nodes and edges extracted by the NL2Cypher agent.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ACSRF Graph Visualization</title>
    <!-- vis-network.js -->
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f8f9fa;
            color: #333;
            display: flex;
            flex-direction: column;
            height: 100vh;
        }
        header {
            background-color: #2c3e50;
            color: white;
            padding: 1rem 2rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
            margin: 0;
            font-size: 1.5rem;
        }
        .question {
            margin-top: 0.5rem;
            font-size: 1rem;
            color: #bdc3c7;
            font-style: italic;
        }
        .summary-box {
            background-color: #e8f4fd;
            border-left: 4px solid #3498db;
            padding: 1rem;
            margin: 1rem 1rem 0 1rem;
            border-radius: 0 4px 4px 0;
            font-size: 0.95rem;
            line-height: 1.5;
        }
        main {
            flex-grow: 1;
            display: flex;
            padding: 1rem;
            gap: 1rem;
            overflow: hidden; /* Stop flex infinite resize loops */
            height: calc(100vh - 100px);
        }
        #mynetwork {
            flex-grow: 1;
            background-color: white;
            border: 1px solid #ddd;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            min-height: 400px;
            height: 100%;
        }
        #sidebar {
            width: 300px;
            background-color: white;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 1rem;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            overflow-y: auto;
        }
        .node-details h2 {
            margin-top: 0;
            font-size: 1.2rem;
            border-bottom: 2px solid #3498db;
            padding-bottom: 0.5rem;
        }
        .prop-key {
            font-weight: bold;
            color: #555;
        }
        .prop-val {
            color: #222;
            word-break: break-all;
        }
        pre {
            white-space: pre-wrap;
            word-wrap: break-word;
            background-color: #f4f6f7;
            padding: 0.5rem;
            border-radius: 4px;
            font-size: 0.85rem;
        }
    </style>
</head>
<body>

<header>
    <h1>ACSRF Attack Path Viewer</h1>
    <div class="question">Query: "{question}"</div>
</header>

<div class="summary-box">
    <strong>Security Summary:</strong><br/>
    {summary_html}
</div>

<main>
    <div id="mynetwork"></div>
    <div id="sidebar">
        <div class="node-details" id="node-details">
            <h2>Selection Details</h2>
            <p>Click on a node or edge to see its properties.</p>
        </div>
    </div>
</main>

<script type="text/javascript">
    // Data injected from Python
    const rawData = {graph_data_json};

    // Transform for vis.js
    // Define color palette based on Neo4j schema
    const colorMap = {
        "Account": "#95a5a6",
        "IAMUser": "#3498db",
        "IAMRole": "#e67e22",
        "IAMPolicy": "#9b59b6",
        "EC2Instance": "#2ecc71",
        "SecurityGroup": "#f1c40f",
        "Internet": "#e74c3c"
    };

    // Icon map (using vis.js built-in shapes or simple labels)
    const shapeMap = {
        "Internet": "diamond",
        "Account": "database",
        "EC2Instance": "square"
    };

    const visNodes = new vis.DataSet(
        rawData.nodes.map(n => {
            const label = n.labels[0] || "Unknown";
            return {
                id: n.id,
                label: n.display,
                title: label, // hover tooltip
                color: colorMap[label] || "#bdc3c7",
                shape: shapeMap[label] || "dot",
                rawProperties: n.properties,
                rawLabels: n.labels
            };
        })
    );

    const visEdges = new vis.DataSet(
        rawData.edges.map(e => ({
            id: e.id,
            from: e.startNode,
            to: e.endNode,
            label: e.type,
            arrows: "to",
            rawProperties: e.properties,
            font: { size: 12, align: 'horizontal' },
            color: { color: '#7f8c8d' }
        }))
    );

    // Provide the data in the vis format
    const data = {
        nodes: visNodes,
        edges: visEdges
    };

    // Network configuration options
    const options = {
        physics: {
            forceAtlas2Based: {
                gravitationalConstant: -50,
                centralGravity: 0.01,
                springLength: 100,
                springConstant: 0.08
            },
            maxVelocity: 50,
            solver: 'forceAtlas2Based',
            timestep: 0.35,
            stabilization: { iterations: 150 }
        },
        nodes: {
            font: { size: 14, color: '#333' },
            borderWidth: 2,
            shadow: true
        },
        edges: {
            smooth: { type: 'continuous' }
        },
        interaction: {
            hover: true,
            tooltipDelay: 200
        }
    };

    // Initialize network!
    const container = document.getElementById('mynetwork');
    const network = new vis.Network(container, data, options);

    // Handle clicks to show properties in sidebar
    network.on("click", function (params) {
        const sideBar = document.getElementById('node-details');
        
        if (params.nodes.length > 0) {
            // Clicked a node
            const nodeId = params.nodes[0];
            const node = visNodes.get(nodeId);
            
            let html = `<h2>${node.rawLabels.join(', ')}</h2>`;
            html += `<div><strong>Label:</strong> ${node.label}</div><br/>`;
            
            for (const [key, val] of Object.entries(node.rawProperties)) {
                if (key === "document" && typeof val === "string") {
                    // Try to pretty-print JSON policy documents
                    try {
                        const obj = JSON.parse(val);
                        html += `<div><span class="prop-key">${key}:</span><pre>${JSON.stringify(obj, null, 2)}</pre></div>`;
                    } catch(e) {
                        html += `<div><span class="prop-key">${key}:</span> <span class="prop-val">${val}</span></div>`;
                    }
                } else {
                    html += `<div><span class="prop-key">${key}:</span> <span class="prop-val">${val}</span></div>`;
                }
            }
            sideBar.innerHTML = html;
            
        } else if (params.edges.length > 0) {
            // Clicked an edge
            const edgeId = params.edges[0];
            const edge = visEdges.get(edgeId);
            
            let html = `<h2>Relationship</h2>`;
            html += `<div><strong>Type:</strong> ${edge.label}</div><br/>`;
            
            if (Object.keys(edge.rawProperties).length === 0) {
                html += `<div><em>No properties</em></div>`;
            } else {
                for (const [key, val] of Object.entries(edge.rawProperties)) {
                    html += `<div><span class="prop-key">${key}:</span> <span class="prop-val">${val}</span></div>`;
                }
            }
            sideBar.innerHTML = html;
            
        } else {
            // Clicked empty space
            sideBar.innerHTML = `<h2>Selection Details</h2><p>Click on a node or edge to see its properties.</p>`;
        }
    });

</script>
</body>
</html>
"""


def generate_html_visualizer(
    question: str,
    graph_data: Dict[str, Any],
    summary: str,
    output_path: Path
) -> None:
    """Inject graph data into the HTML template and save it.
    
    Parameters
    ----------
    question : str
        The original user question.
    graph_data : dict
        Dict containing "nodes" and "edges" lists.
    summary : str
        The LLM-generated summary.
    output_path : Path
        Where to save the HTML file.
    """
    json_str = json.dumps(graph_data, separators=(',', ':'))
    
    # Format summary with basic HTML line breaks
    summary_html = summary.replace('\n', '<br/>') if summary else "<em>No summary available.</em>"
    
    html = HTML_TEMPLATE.replace("{question}", question.replace('"', '&quot;'))
    html = html.replace("{summary_html}", summary_html)
    html = html.replace("{graph_data_json}", json_str)
    
    output_path.write_text(html, encoding="utf-8")
