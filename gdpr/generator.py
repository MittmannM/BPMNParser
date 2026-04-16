from utils import generate_id


def xml_escape(s: str) -> str:
    """Escape special XML characters in attribute/element values."""
    return (s
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&apos;'))

# Lane height in pixels
LANE_H = 200
# Top offset for the pool
POOL_Y = 50
# Left margin for lane label column
LANE_LABEL_W = 30
# Starting x for all flow elements
START_X = 150


def _lane_center_y(actor_idx):
    """Return the vertical center of a lane (for routing elements within it)."""
    return POOL_Y + actor_idx * LANE_H + LANE_H // 2


def generate_bpmn_master(tasks, output_file):
    if not tasks:
        print("Keine Aufgaben zum Generieren vorhanden.")
        return

    print(f"Generiere BPMN 2.0 XML in '{output_file}'...")

    # Preserve task ordering while getting unique actors in appearance order
    seen_actors = []
    for t in tasks:
        if t['actor'] not in seen_actors:
            seen_actors.append(t['actor'])
    actors_ordered = seen_actors  # ordered by first appearance

    # actor → lane index
    actor_idx = {a: i for i, a in enumerate(actors_ordered)}

    # ── node tracking for laneSet flowNodeRefs ─────────────────────────────
    # Maps actor → list of BPMN element IDs that belong in that lane
    lane_nodes: dict[str, list[str]] = {a: [] for a in actors_ordered}
    # The start event belongs to the first task's lane
    first_actor = tasks[0]['actor']

    # Pre-allocate IDs we will need but generate them now so we can
    # reference them in laneSet *before* emitting the actual elements.
    start_id = generate_id("StartEvent_")
    end_id   = generate_id("EndEvent_")
    lane_nodes[first_actor].append(start_id)
    # End event goes in the last task's lane
    last_actor = tasks[-1]['actor']
    lane_nodes[last_actor].append(end_id)

    # ── collect all element IDs and their lane up front for each task ──────
    # We also pre-generate gateway/event IDs so we can add them to lane_nodes
    task_meta = []
    for task in tasks:
        actor = task['actor']
        task_id = task['id']
        lane_nodes[actor].append(task_id)

        has_gateway = bool(task['gateway_cond'])
        gw_split_id = generate_id("Gateway_Split_") if has_gateway else None
        gw_merge_id = generate_id("Gateway_Merge_") if has_gateway else None
        if gw_split_id: lane_nodes[actor].append(gw_split_id)
        if gw_merge_id: lane_nodes[actor].append(gw_merge_id)

        or_alts = task.get('or_alternatives', [])
        xor_split_id = generate_id("XOR_Split_") if len(or_alts) >= 2 else None
        xor_merge_id = generate_id("XOR_Merge_") if len(or_alts) >= 2 else None
        if xor_split_id: lane_nodes[actor].append(xor_split_id)
        if xor_merge_id: lane_nodes[actor].append(xor_merge_id)

        ev_ids = []
        for ev in task['events']:
            ev_id = generate_id("Event_")
            lane_nodes[actor].append(ev_id)
            ev_ids.append((ev, ev_id))

        task_meta.append({
            'task': task,
            'task_id': task_id,
            'has_gateway': has_gateway,
            'gw_split_id': gw_split_id,
            'gw_merge_id': gw_merge_id,
            'xor_split_id': xor_split_id,
            'xor_merge_id': xor_merge_id,
            'ev_ids': ev_ids,
        })

    # ── XML header & process ────────────────────────────────────────────────
    bpmn_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"'
        ' xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"'
        ' xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"'
        ' xmlns:di="http://www.omg.org/spec/DD/20100524/DI"'
        ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
        ' id="Definitions_1" targetNamespace="http://bpmn.io/schema/bpmn">',
        '  <bpmn:collaboration id="Collaboration_1">',
        '    <bpmn:participant id="Participant_Process" name="GDPR Process" processRef="Process_GDPR" />',
        '  </bpmn:collaboration>',
        '  <bpmn:process id="Process_GDPR" isExecutable="false">',
    ]

    # ── laneSet (with all flowNodeRefs pre-populated) ──────────────────────
    bpmn_lines.append('    <bpmn:laneSet id="LaneSet_1">')
    for actor in actors_ordered:
        bpmn_lines.append(f'      <bpmn:lane id="Lane_{actor}" name="{actor}">')
        for node_id in lane_nodes[actor]:
            bpmn_lines.append(f'        <bpmn:flowNodeRef>{node_id}</bpmn:flowNodeRef>')
        bpmn_lines.append('      </bpmn:lane>')
    bpmn_lines.append('    </bpmn:laneSet>')

    # ── shapes & edges lists (DI section) ──────────────────────────────────
    shapes: list[str] = []
    edges:  list[str] = []

    # ── layout: one horizontal band per actor, top-to-bottom ───────────────
    def cy(actor):
        """Center Y of this actor's lane."""
        return _lane_center_y(actor_idx[actor])

    def task_y(actor):
        """Top-left Y of a task box in this actor's lane (80px tall box)."""
        return cy(actor) - 40

    # Start event position
    x_pos = START_X
    s_y = cy(first_actor) - 18
    bpmn_lines.append(f'    <bpmn:startEvent id="{start_id}" name="Start" />')
    shapes.append(
        f'      <bpmndi:BPMNShape id="{start_id}_di" bpmnElement="{start_id}">'
        f'<dc:Bounds x="{x_pos}" y="{s_y}" width="36" height="36" /></bpmndi:BPMNShape>'
    )
    last_id = start_id
    last_out_x, last_out_y = x_pos + 36, cy(first_actor)
    x_pos += 36

    # ── iterate tasks ───────────────────────────────────────────────────────
    for meta in task_meta:
        task     = meta['task']
        actor    = task['actor']
        task_id  = meta['task_id']
        y_center = cy(actor)
        ty       = task_y(actor)   # top of task box

        # ── intermediate catch events ──────────────────────────────────────
        for ev_label, ev_id in meta['ev_ids']:
            ev_flow = generate_id("Flow_")
            x_pos += 80
            ev_y = y_center - 18
            bpmn_lines.append(
                f'    <bpmn:sequenceFlow id="{ev_flow}" sourceRef="{last_id}" targetRef="{ev_id}" />'
            )
            cond_def_id = generate_id("CondDef_")
            bpmn_lines.append(
                f'    <bpmn:intermediateCatchEvent id="{ev_id}" name="{ev_label}">'
                f'<bpmn:incoming>{ev_flow}</bpmn:incoming>'
                f'<bpmn:conditionalEventDefinition id="{cond_def_id}">'
                f'<bpmn:condition xsi:type="bpmn:tFormalExpression">{ev_label}</bpmn:condition>'
                f'</bpmn:conditionalEventDefinition>'
                f'</bpmn:intermediateCatchEvent>'
            )
            edges.append(
                f'      <bpmndi:BPMNEdge id="{ev_flow}_di" bpmnElement="{ev_flow}">'
                f'<di:waypoint x="{last_out_x}" y="{last_out_y}" />'
                f'<di:waypoint x="{x_pos}" y="{y_center}" /></bpmndi:BPMNEdge>'
            )
            shapes.append(
                f'      <bpmndi:BPMNShape id="{ev_id}_di" bpmnElement="{ev_id}">'
                f'<dc:Bounds x="{x_pos}" y="{ev_y}" width="36" height="36" /></bpmndi:BPMNShape>'
            )
            last_id = ev_id
            last_out_x, last_out_y = x_pos + 36, y_center
            x_pos += 36

        # ── optional XOR gateway for OR alternatives ───────────────────────
        or_alts = task.get('or_alternatives', [])
        xor_split_id = meta['xor_split_id']
        xor_merge_id = meta['xor_merge_id']
        if xor_split_id and len(or_alts) >= 2:
            xor_flow_in = generate_id("Flow_")
            x_pos += 100
            x_xor_split = x_pos
            bpmn_lines.append(
                f'    <bpmn:sequenceFlow id="{xor_flow_in}" sourceRef="{last_id}" targetRef="{xor_split_id}" />'
            )
            bpmn_lines.append(
                f'    <bpmn:exclusiveGateway id="{xor_split_id}" name="Measures Type?">'
                f'<bpmn:incoming>{xor_flow_in}</bpmn:incoming></bpmn:exclusiveGateway>'
            )
            edges.append(
                f'      <bpmndi:BPMNEdge id="{xor_flow_in}_di" bpmnElement="{xor_flow_in}">'
                f'<di:waypoint x="{last_out_x}" y="{last_out_y}" />'
                f'<di:waypoint x="{x_xor_split}" y="{y_center}" /></bpmndi:BPMNEdge>'
            )
            shapes.append(
                f'      <bpmndi:BPMNShape id="{xor_split_id}_di" bpmnElement="{xor_split_id}" isMarkerVisible="true">'
                f'<dc:Bounds x="{x_xor_split}" y="{y_center - 25}" width="50" height="50" /></bpmndi:BPMNShape>'
            )
            x_alt_tasks = x_xor_split + 100
            alt_end_ids = []
            for alt_idx, alt_label in enumerate(or_alts):
                alt_task_id = generate_id("AltTask_")
                alt_flow    = generate_id("Flow_Alt_")
                alt_y = ty + (alt_idx * 90) - 45
                bpmn_lines.append(
                    f'    <bpmn:sequenceFlow id="{alt_flow}" name="{alt_label}" '
                    f'sourceRef="{xor_split_id}" targetRef="{alt_task_id}" />'
                )
                bpmn_lines.append(
                    f'    <bpmn:task id="{alt_task_id}" name="{alt_label}">'
                    f'<bpmn:incoming>{alt_flow}</bpmn:incoming></bpmn:task>'
                )
                edges.append(
                    f'      <bpmndi:BPMNEdge id="{alt_flow}_di" bpmnElement="{alt_flow}">'
                    f'<di:waypoint x="{x_xor_split + 50}" y="{y_center}" />'
                    f'<di:waypoint x="{x_alt_tasks}" y="{alt_y + 30}" /></bpmndi:BPMNEdge>'
                )
                shapes.append(
                    f'      <bpmndi:BPMNShape id="{alt_task_id}_di" bpmnElement="{alt_task_id}">'
                    f'<dc:Bounds x="{x_alt_tasks}" y="{alt_y}" width="150" height="60" /></bpmndi:BPMNShape>'
                )
                alt_end_ids.append((alt_task_id, alt_y))
            x_xor_merge = x_alt_tasks + 180
            for alt_task_id_m, alt_y_m in alt_end_ids:
                merge_flow = generate_id("Flow_Merge_")
                bpmn_lines.append(
                    f'    <bpmn:sequenceFlow id="{merge_flow}" sourceRef="{alt_task_id_m}" targetRef="{xor_merge_id}" />'
                )
                edges.append(
                    f'      <bpmndi:BPMNEdge id="{merge_flow}_di" bpmnElement="{merge_flow}">'
                    f'<di:waypoint x="{x_alt_tasks + 150}" y="{alt_y_m + 30}" />'
                    f'<di:waypoint x="{x_xor_merge}" y="{y_center}" /></bpmndi:BPMNEdge>'
                )
            bpmn_lines.append(
                f'    <bpmn:exclusiveGateway id="{xor_merge_id}"></bpmn:exclusiveGateway>'
            )
            shapes.append(
                f'      <bpmndi:BPMNShape id="{xor_merge_id}_di" bpmnElement="{xor_merge_id}" isMarkerVisible="true">'
                f'<dc:Bounds x="{x_xor_merge}" y="{y_center - 25}" width="50" height="50" /></bpmndi:BPMNShape>'
            )
            last_id = xor_merge_id
            last_out_x, last_out_y = x_xor_merge + 50, y_center
            x_task = x_xor_merge + 100
            x_pos  = x_xor_merge
        else:
            x_task = x_pos + 140

        # ── optional conditional gateway (XOR split for gateway_cond) ──────
        gw_split_id = meta['gw_split_id']
        gw_merge_id = meta['gw_merge_id']
        has_gateway = meta['has_gateway']
        if has_gateway:
            split_flow = generate_id("Flow_")
            x_pos += 100
            gw_x = x_pos
            gw_name = f"If {task['gateway_cond']}?"
            bpmn_lines.append(
                f'    <bpmn:sequenceFlow id="{split_flow}" sourceRef="{last_id}" targetRef="{gw_split_id}" />'
            )
            bpmn_lines.append(
                f'    <bpmn:exclusiveGateway id="{gw_split_id}" name="{gw_name}">'
                f'<bpmn:incoming>{split_flow}</bpmn:incoming></bpmn:exclusiveGateway>'
            )
            edges.append(
                f'      <bpmndi:BPMNEdge id="{split_flow}_di" bpmnElement="{split_flow}">'
                f'<di:waypoint x="{last_out_x}" y="{last_out_y}" />'
                f'<di:waypoint x="{gw_x}" y="{y_center}" /></bpmndi:BPMNEdge>'
            )
            shapes.append(
                f'      <bpmndi:BPMNShape id="{gw_split_id}_di" bpmnElement="{gw_split_id}" isMarkerVisible="true">'
                f'<dc:Bounds x="{gw_x}" y="{y_center - 25}" width="50" height="50" /></bpmndi:BPMNShape>'
            )
            last_id = gw_split_id
            last_out_x, last_out_y = gw_x + 50, y_center
            x_task = gw_x + 120
            x_pos  = gw_x

        # ── main task ──────────────────────────────────────────────────────
        flow_id    = generate_id("Flow_Yes_" if has_gateway and not xor_split_id else "Flow_")
        flow_label = ' name="Yes"' if has_gateway and not xor_split_id else ''
        bpmn_lines.append(
            f'    <bpmn:sequenceFlow id="{flow_id}"{flow_label} sourceRef="{last_id}" targetRef="{task_id}" />'
        )
        edges.append(
            f'      <bpmndi:BPMNEdge id="{flow_id}_di" bpmnElement="{flow_id}">'
            f'<di:waypoint x="{last_out_x}" y="{last_out_y}" />'
            f'<di:waypoint x="{x_task}" y="{y_center}" /></bpmndi:BPMNEdge>'
        )

        recipient_str = f" to {task['recipient']}" if task.get('recipient') else ""
        task_label    = f"{task['action']}{recipient_str}\n({task['source']})"
        task_tag      = task['bpmn_type']
        task_block    = (
            f'    <{task_tag} id="{task_id}" name="{task_label}">'
            f'<bpmn:incoming>{flow_id}</bpmn:incoming>'
        )

        # Data output associations
        if task['data_objects']:
            for d_idx, doc_label in enumerate(task['data_objects']):
                data_id  = generate_id("DataObj_")
                ref_id   = generate_id("DataRef_")
                assoc_id = generate_id("Assoc_")
                task_block += (
                    f'<bpmn:dataOutputAssociation id="{assoc_id}">'
                    f'<bpmn:targetRef>{ref_id}</bpmn:targetRef>'
                    f'</bpmn:dataOutputAssociation>'
                )
                bpmn_lines.append(f'    <bpmn:dataObject id="{data_id}" />')
                bpmn_lines.append(
                    f'    <bpmn:dataObjectReference id="{ref_id}" dataObjectRef="{data_id}" name="{doc_label}" />'
                )
                doc_x = x_task + (d_idx * 70) - 10
                doc_y = ty - 80
                shapes.append(
                    f'      <bpmndi:BPMNShape id="{ref_id}_di" bpmnElement="{ref_id}">'
                    f'<dc:Bounds x="{doc_x}" y="{doc_y}" width="36" height="50" /></bpmndi:BPMNShape>'
                )
                edges.append(
                    f'      <bpmndi:BPMNEdge id="{assoc_id}_di" bpmnElement="{assoc_id}">'
                    f'<di:waypoint x="{x_task + 75}" y="{ty}" />'
                    f'<di:waypoint x="{doc_x + 18}" y="{doc_y + 50}" /></bpmndi:BPMNEdge>'
                )

        task_block += f'</{task_tag}>'
        bpmn_lines.append(task_block)
        shapes.append(
            f'      <bpmndi:BPMNShape id="{task_id}_di" bpmnElement="{task_id}">'
            f'<dc:Bounds x="{x_task}" y="{ty}" width="150" height="80" /></bpmndi:BPMNShape>'
        )

        # Optional timer boundary event
        if task.get('timer'):
            timer_id = generate_id("Timer_")
            bpmn_lines.append(
                f'    <bpmn:boundaryEvent id="{timer_id}" attachedToRef="{task_id}" cancelActivity="false">'
                f'<bpmn:timerEventDefinition>'
                f'<bpmn:timeDuration xsi:type="bpmn:tFormalExpression">{task["timer"]}</bpmn:timeDuration>'
                f'</bpmn:timerEventDefinition></bpmn:boundaryEvent>'
            )
            shapes.append(
                f'      <bpmndi:BPMNShape id="{timer_id}_di" bpmnElement="{timer_id}">'
                f'<dc:Bounds x="{x_task + 132}" y="{ty + 60}" width="36" height="36" /></bpmndi:BPMNShape>'
            )

        last_id      = task_id
        last_out_x   = x_task + 150
        last_out_y   = y_center
        x_pos        = x_task + 150

        # ── closing XOR merge gateway ──────────────────────────────────────
        if has_gateway:
            flow_from_task = generate_id("Flow_")
            x_pos += 80
            bpmn_lines.append(
                f'    <bpmn:sequenceFlow id="{flow_from_task}" sourceRef="{last_id}" targetRef="{gw_merge_id}" />'
            )
            edges.append(
                f'      <bpmndi:BPMNEdge id="{flow_from_task}_di" bpmnElement="{flow_from_task}">'
                f'<di:waypoint x="{last_out_x}" y="{last_out_y}" />'
                f'<di:waypoint x="{x_pos}" y="{y_center}" /></bpmndi:BPMNEdge>'
            )
            # "No" bypass arc — routes below the task in the same lane
            flow_no  = generate_id("Flow_No_")
            y_bypass = y_center + LANE_H // 3
            bpmn_lines.append(
                f'    <bpmn:sequenceFlow id="{flow_no}" name="No" '
                f'sourceRef="{gw_split_id}" targetRef="{gw_merge_id}" />'
            )
            edges.append(
                f'      <bpmndi:BPMNEdge id="{flow_no}_di" bpmnElement="{flow_no}">'
                f'<di:waypoint x="{gw_x + 25}" y="{y_center + 25}" />'
                f'<di:waypoint x="{gw_x + 25}" y="{y_bypass}" />'
                f'<di:waypoint x="{x_pos + 25}" y="{y_bypass}" />'
                f'<di:waypoint x="{x_pos + 25}" y="{y_center + 25}" /></bpmndi:BPMNEdge>'
            )
            bpmn_lines.append(
                f'    <bpmn:exclusiveGateway id="{gw_merge_id}">'
                f'<bpmn:incoming>{flow_from_task}</bpmn:incoming>'
                f'<bpmn:incoming>{flow_no}</bpmn:incoming>'
                f'</bpmn:exclusiveGateway>'
            )
            shapes.append(
                f'      <bpmndi:BPMNShape id="{gw_merge_id}_di" bpmnElement="{gw_merge_id}" isMarkerVisible="true">'
                f'<dc:Bounds x="{x_pos}" y="{y_center - 25}" width="50" height="50" /></bpmndi:BPMNShape>'
            )
            last_id      = gw_merge_id
            last_out_x   = x_pos + 50
            last_out_y   = y_center
            x_pos       += 50

    # ── end event ──────────────────────────────────────────────────────────
    final_flow = generate_id("Flow_")
    x_pos += 100
    end_y = cy(last_actor) - 18
    bpmn_lines.append(
        f'    <bpmn:sequenceFlow id="{final_flow}" sourceRef="{last_id}" targetRef="{end_id}" />'
    )
    bpmn_lines.append(
        f'    <bpmn:endEvent id="{end_id}" name="End">'
        f'<bpmn:incoming>{final_flow}</bpmn:incoming></bpmn:endEvent>'
    )
    shapes.append(
        f'      <bpmndi:BPMNShape id="{end_id}_di" bpmnElement="{end_id}">'
        f'<dc:Bounds x="{x_pos}" y="{end_y}" width="36" height="36" /></bpmndi:BPMNShape>'
    )
    edges.append(
        f'      <bpmndi:BPMNEdge id="{final_flow}_di" bpmnElement="{final_flow}">'
        f'<di:waypoint x="{last_out_x}" y="{last_out_y}" />'
        f'<di:waypoint x="{x_pos}" y="{cy(last_actor)}" /></bpmndi:BPMNEdge>'
    )
    bpmn_lines.append('  </bpmn:process>')

    # ── DI section ─────────────────────────────────────────────────────────
    pool_width  = x_pos + 200
    pool_height = len(actors_ordered) * LANE_H
    bpmn_lines.append('  <bpmndi:BPMNDiagram id="BPMNDiagram_1">')
    bpmn_lines.append('    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="Collaboration_1">')
    bpmn_lines.append(
        f'      <bpmndi:BPMNShape id="Participant_Process_di" bpmnElement="Participant_Process"'
        f' isHorizontal="true"><dc:Bounds x="50" y="{POOL_Y}" width="{pool_width}" height="{pool_height}" />'
        f'</bpmndi:BPMNShape>'
    )
    for idx, actor in enumerate(actors_ordered):
        lane_y = POOL_Y + idx * LANE_H
        bpmn_lines.append(
            f'      <bpmndi:BPMNShape id="Lane_{actor}_di" bpmnElement="Lane_{actor}"'
            f' isHorizontal="true"><dc:Bounds x="80" y="{lane_y}" width="{pool_width - 30}"'
            f' height="{LANE_H}" /></bpmndi:BPMNShape>'
        )
    bpmn_lines.extend(shapes)
    bpmn_lines.extend(edges)
    bpmn_lines.append('    </bpmndi:BPMNPlane>')
    bpmn_lines.append('  </bpmndi:BPMNDiagram>')
    bpmn_lines.append('</bpmn:definitions>')

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(bpmn_lines))
    print(f"BPMN gespeichert unter: {output_file}")
