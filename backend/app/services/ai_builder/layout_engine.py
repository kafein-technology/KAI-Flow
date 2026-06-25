from typing import Dict, Any

def calculate_auto_layout(workflow: Dict[str, Any], existing_workflow: Dict[str, Any] = None) -> Dict[str, Any]:
    nodes = workflow.get("nodes", [])
    edges = workflow.get("edges", [])
    if not nodes:
        return workflow

    # Track existing positions to preserve them
    existing_positions = {}
    if existing_workflow:
        for node in existing_workflow.get("nodes", []):
            if "id" in node and "position" in node:
                existing_positions[node["id"]] = node["position"]

    # Regular flow handles
    main_handles = {"input", "trigger", "documents", "chunks", "target"}

    # Separate supporting/provider nodes from main flow nodes
    supporting_nodes = set()
    node_targets = {}  # maps supporting_node_id -> list of target_node_ids
    
    for edge in edges:
        src = edge.get("source")
        tgt = edge.get("target")
        tgt_handle = edge.get("targetHandle", "")
        if tgt_handle not in main_handles:
            supporting_nodes.add(src)
            node_targets.setdefault(src, []).append(tgt)

    # Main flow nodes are those not in supporting_nodes
    main_flow_nodes = [n for n in nodes if n.get("id") not in supporting_nodes]
    supporting_flow_nodes = [n for n in nodes if n.get("id") in supporting_nodes]

    # Topological sorting / Layering on main flow nodes
    main_node_ids = {n.get("id") for n in main_flow_nodes}
    adj_list = {n_id: [] for n_id in main_node_ids}
    in_degree = {n_id: 0 for n_id in main_node_ids}

    for edge in edges:
        src = edge.get("source")
        tgt = edge.get("target")
        # Only build main flow graph edges
        if src in main_node_ids and tgt in main_node_ids:
            adj_list[src].append(tgt)
            in_degree[tgt] += 1

    # BFS/Kahn's algorithm to assign layers
    queue = [n_id for n_id, deg in in_degree.items() if deg == 0]
    node_layers = {n_id: 0 for n_id in main_node_ids}

    while queue:
        curr = queue.pop(0)
        curr_layer = node_layers[curr]
        for neighbor in adj_list[curr]:
            node_layers[neighbor] = max(node_layers[neighbor], curr_layer + 1)
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # Group main flow nodes by layer
    layer_groups = {}
    for n_id, layer in node_layers.items():
        layer_groups.setdefault(layer, []).append(n_id)

    X_GAP = 280
    Y_GAP = 180

    # Layout main flow nodes
    for layer, n_ids in sorted(layer_groups.items()):
        for index, n_id in enumerate(n_ids):
            node = next((n for n in nodes if n.get("id") == n_id), None)
            if not node:
                continue
            
            # Preserve existing position if available
            if n_id in existing_positions:
                node["position"] = existing_positions[n_id]
            else:
                node["position"] = {
                    "x": layer * X_GAP + 100,
                    "y": index * Y_GAP + 150
                }

    # Layout supporting/provider nodes
    placed_supporting = set()
    for s_node in supporting_flow_nodes:
        s_id = s_node.get("id")
        if s_id in existing_positions:
            s_node["position"] = existing_positions[s_id]
            placed_supporting.add(s_id)

    # Place new/unpositioned supporting nodes stacked below target
    target_supporting_counts = {}
    for s_node in supporting_flow_nodes:
        s_id = s_node.get("id")
        if s_id in placed_supporting:
            continue
            
        targets = node_targets.get(s_id, [])
        if targets:
            tgt_id = targets[0]
            target_node = next((n for n in nodes if n.get("id") == tgt_id), None)
            if target_node and "position" in target_node:
                t_pos = target_node["position"]
                count = target_supporting_counts.get(tgt_id, 0)
                s_node["position"] = {
                    "x": t_pos["x"],
                    "y": t_pos["y"] + 150 + (count * 120)
                }
                target_supporting_counts[tgt_id] = count + 1
            else:
                s_node["position"] = {"x": 100, "y": 450}
        else:
            s_node["position"] = {"x": 100, "y": 450}

    return workflow
