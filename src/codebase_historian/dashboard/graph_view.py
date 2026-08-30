"""
Interactive HTML Network Graph Visualizer for Streamlit using vis.js.
Renders files, commits, authors, and relations with physics, zoom, and inspection.
"""

import json

from codebase_historian.graph.graph import CodebaseKnowledgeGraph, NodeType


def generate_graph_html(
    kg: CodebaseKnowledgeGraph,
    max_nodes: int = 80,
    max_edges: int = 120,
    edge_types: list[str] | None = None,
) -> str:
    """Generate standalone HTML string embedding vis.js interactive graph."""
    nodes = []
    edges = []

    # Map node types to colors and shapes
    type_styles = {
        NodeType.FILE.value: {"color": "#00d2ff", "shape": "dot", "size": 18},
        NodeType.COMMIT.value: {"color": "#ff9f43", "shape": "diamond", "size": 14},
        NodeType.AUTHOR.value: {"color": "#a55eea", "shape": "square", "size": 16},
        NodeType.PULL_REQUEST.value: {"color": "#2bcbba", "shape": "triangle", "size": 16},
        NodeType.ISSUE.value: {"color": "#eb3b5a", "shape": "triangleDown", "size": 16},
    }

    # Sort nodes to include most relevant nodes first:
    # 1. Central files (sorted by PageRank centrality descending)
    # 2. Commits & Authors
    sorted_nodes = sorted(
        kg.g.nodes(data=True),
        key=lambda x: (
            0 if x[1].get("type") == NodeType.FILE.value else 1,
            -x[1].get("centrality", 0.0),
        ),
    )

    included_nodes = set()
    for node_id, data in sorted_nodes:
        if len(included_nodes) >= max_nodes:
            break
        ntype = data.get("type", "File")
        style = type_styles.get(ntype, {"color": "#778ca3", "shape": "dot", "size": 14})

        label = data.get("path", data.get("message", data.get("display_name", node_id)))
        if len(str(label)) > 30:
            label = str(label)[:27] + "..."

        title_info = f"<b>Type:</b> {ntype}<br/><b>ID:</b> {node_id}"
        if "centrality" in data:
            title_info += f"<br/><b>Centrality:</b> {data['centrality']:.4f}"

        nodes.append(
            {
                "id": node_id,
                "label": label,
                "title": title_info,
                "color": style["color"],
                "shape": style["shape"],
                "size": style["size"],
                "font": {"color": "#f1f2f6", "size": 12},
            }
        )
        included_nodes.add(node_id)

    # Collect and prioritize edges between included nodes
    # Priority order: DEPENDS_ON > MODIFIES > AUTHORED_BY > CO_CHANGES_WITH
    edge_priority = {
        "DEPENDS_ON": 1,
        "MODIFIES": 2,
        "AUTHORED_BY": 3,
        "CO_CHANGES_WITH": 4,
    }

    candidate_edges = []
    seen_pairs = set()

    for u, v, data in kg.g.edges(data=True):
        if u in included_nodes and v in included_nodes:
            edge_type = data.get("type", "")
            if edge_types and edge_type not in edge_types:
                continue

            # Deduplicate bidirectional / parallel edges in visualization
            canonical_pair = tuple(sorted([str(u), str(v)]))
            if canonical_pair in seen_pairs:
                continue
            seen_pairs.add(canonical_pair)

            prio = edge_priority.get(edge_type, 10)
            weight = data.get("co_change_count", 1)
            candidate_edges.append((prio, -weight, u, v, edge_type))

    # Sort candidate edges by priority and weight
    candidate_edges.sort()

    for _, _, u, v, edge_type in candidate_edges[:max_edges]:
        edge_color = "#4b6584"
        dashes = False

        if edge_type == "CO_CHANGES_WITH":
            edge_color = "#ff6b81"
        elif edge_type == "DEPENDS_ON":
            edge_color = "#2ed573"
        elif edge_type == "AUTHORED_BY":
            edge_color = "#fed330"
            dashes = True
        elif edge_type == "MODIFIES":
            edge_color = "#70a1ff"

        edges.append(
            {
                "from": u,
                "to": v,
                "title": f"Relation: {edge_type}",
                "color": {"color": edge_color, "highlight": "#ffffff"},
                "dashes": dashes,
                "width": 1.5,
            }
        )

    nodes_json = json.dumps(nodes)
    edges_json = json.dumps(edges)

    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
      <style type="text/css">
        body {{
          margin: 0;
          padding: 0;
          background-color: #0e1117;
          overflow: hidden;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }}
        #network {{
          width: 100%;
          height: 520px;
          border: 1px solid #262730;
          border-radius: 8px;
        }}
        #status {{
          position: absolute;
          bottom: 10px;
          right: 12px;
          background: rgba(0, 0, 0, 0.6);
          color: #2ed573;
          font-size: 11px;
          padding: 3px 8px;
          border-radius: 4px;
          pointer-events: none;
        }}
      </style>
    </head>
    <body>
    <div id="network"></div>
    <div id="status">Interactive • Physics Stabilized</div>
    <script type="text/javascript">
      var container = document.getElementById('network');
      var data = {{
        nodes: new vis.DataSet({nodes_json}),
        edges: new vis.DataSet({edges_json})
      }};
      var options = {{
        physics: {{
          solver: 'forceAtlas2Based',
          forceAtlas2Based: {{
            gravitationalConstant: -40,
            centralGravity: 0.015,
            springLength: 85,
            springConstant: 0.08,
            damping: 0.4
          }},
          stabilization: {{
            enabled: true,
            iterations: 60,
            updateInterval: 25
          }}
        }},
        interaction: {{
          hover: true,
          tooltipDelay: 100,
          zoomView: true,
          dragNodes: true,
          dragView: true,
          navigationButtons: true
        }}
      }};
      var network = new vis.Network(container, data, options);
      // Freeze physics after layout stabilizes to prevent browser CPU freeze
      network.once('stabilizationIterationsDone', function() {{
        network.setOptions({{ physics: false }});
        var statusEl = document.getElementById('status');
        if (statusEl) {{
          statusEl.innerText = 'Ready • Drag / Zoom enabled';
        }}
      }});
    </script>
    </body>
    </html>
    """
    return html_template
