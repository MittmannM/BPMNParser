from utils import generate_id


LANE_H = 230
POOL_Y = 50
START_X = 150


def _lane_center_y(actor_idx):
    return POOL_Y + actor_idx * LANE_H + LANE_H // 2


def _expand_post_actions(tasks):
    expanded = []
    for task in tasks:
        if task.get('branches'):
            expanded.append(dict(task))
            continue
        base_task = dict(task)
        post_actions = list(base_task.pop('post_actions', []))
        expanded.append(base_task)
        for post_action in post_actions:
            expanded.append({
                'id': generate_id("Task_"),
                'actor': post_action.get('actor') or base_task['actor'],
                'action': post_action['action'],
                'recipient': post_action.get('recipient'),
                'source': base_task['source'],
                'timer': None,
                'bpmn_type': post_action.get('bpmn_type', 'bpmn:task'),
                'gateway_cond': None,
                'gateway_type': base_task.get('gateway_type', 'exclusive'),
                'use_gateway': bool(post_action.get('use_gateway', False)),
                'events': [],
                'data_objects': list(post_action.get('data_objects', [])),
                'or_alternatives': [],
                'has_time_bound': False,
                'notes': [],
                'article_notes': [],
                'branches': [],
            })
    return expanded


def generate_bpmn_master(tasks, output_file):
    if not tasks:
        print("Keine Aufgaben zum Generieren vorhanden.")
        return

    tasks = _expand_post_actions(tasks)
    print(f"Generiere BPMN 2.0 XML in '{output_file}'...")

    actors_ordered = []
    for task in tasks:
        if task['actor'] not in actors_ordered:
            actors_ordered.append(task['actor'])
        for branch in task.get('branches', []):
            for branch_task in branch.get('tasks', []):
                if branch_task['actor'] not in actors_ordered:
                    actors_ordered.append(branch_task['actor'])
    actor_idx = {actor: index for index, actor in enumerate(actors_ordered)}

    lane_nodes: dict[str, list[str]] = {actor: [] for actor in actors_ordered}
    first_actor = tasks[0]['actor']
    last_actor = tasks[-1]['actor']

    start_id = generate_id("StartEvent_")
    end_id = generate_id("EndEvent_")
    lane_nodes[first_actor].append(start_id)
    lane_nodes[last_actor].append(end_id)

    task_meta = []
    for task in tasks:
        actor = task['actor']
        branches = list(task.get('branches', []))
        if branches:
            split_id = generate_id("Gateway_Split_")
            merge_id = generate_id("Gateway_Merge_")
            lane_nodes[actor].append(split_id)
            lane_nodes[actor].append(merge_id)
            branch_defs = []
            for branch in branches:
                branch_tasks = []
                for branch_task in branch.get('tasks', []):
                    branch_id = branch_task['id']
                    branch_actor = branch_task['actor']
                    lane_nodes[branch_actor].append(branch_id)
                    branch_tasks.append({'task': branch_task, 'task_id': branch_id})
                branch_defs.append({'label': branch.get('label', ''), 'tasks': branch_tasks})
            task_meta.append({
                'task': task,
                'task_id': task['id'],
                'has_gateway': False,
                'gw_split_id': None,
                'gw_merge_id': None,
                'xor_split_id': split_id,
                'xor_merge_id': merge_id,
                'ev_ids': [],
                'branches': branch_defs,
            })
            continue

        task_id = task['id']
        lane_nodes[actor].append(task_id)

        has_gateway = bool(task.get('use_gateway') and task.get('gateway_cond'))
        gw_split_id = generate_id("Gateway_Split_") if has_gateway else None
        gw_merge_id = generate_id("Gateway_Merge_") if has_gateway else None
        if gw_split_id:
            lane_nodes[actor].append(gw_split_id)
        if gw_merge_id:
            lane_nodes[actor].append(gw_merge_id)

        xor_split_id = None
        xor_merge_id = None

        ev_ids = []
        for event in task.get('events', []):
            ev_id = generate_id("Event_")
            lane_nodes[actor].append(ev_id)
            ev_ids.append((event, ev_id))

        task_meta.append({
            'task': task,
            'task_id': task_id,
            'has_gateway': has_gateway,
            'gw_split_id': gw_split_id,
            'gw_merge_id': gw_merge_id,
            'xor_split_id': xor_split_id,
            'xor_merge_id': xor_merge_id,
            'ev_ids': ev_ids,
            'branches': [],
        })

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
        '    <bpmn:laneSet id="LaneSet_1">',
    ]

    for actor in actors_ordered:
        bpmn_lines.append(f'      <bpmn:lane id="Lane_{actor}" name="{actor}">')
        for node_id in lane_nodes[actor]:
            bpmn_lines.append(f'        <bpmn:flowNodeRef>{node_id}</bpmn:flowNodeRef>')
        bpmn_lines.append('      </bpmn:lane>')
    bpmn_lines.append('    </bpmn:laneSet>')

    shapes: list[str] = []
    edges: list[str] = []
    annotations: list[str] = []
    annotation_edges: list[str] = []

    def cy(actor):
        return _lane_center_y(actor_idx[actor])

    def task_y(actor):
        return cy(actor) - 40

    def branch_center_y(actor, branch_index, branch_count):
        base = cy(actor)
        if branch_count <= 1:
            return base
        raw_offset = int((branch_index - (branch_count - 1) / 2) * 110)
        limit = (LANE_H // 2) - 45
        offset = max(-limit, min(limit, raw_offset))
        return base + offset

    x_pos = START_X
    bpmn_lines.append(f'    <bpmn:startEvent id="{start_id}" name="Start" />')
    shapes.append(
        f'      <bpmndi:BPMNShape id="{start_id}_di" bpmnElement="{start_id}">'
        f'<dc:Bounds x="{x_pos}" y="{cy(first_actor) - 18}" width="36" height="36" /></bpmndi:BPMNShape>'
    )
    last_id = start_id
    last_out_x = x_pos + 36
    last_out_y = cy(first_actor)
    x_pos += 36

    for meta in task_meta:
        task = meta['task']
        actor = task['actor']
        task_id = meta['task_id']
        y_center = cy(actor)
        ty = task_y(actor)

        for ev_label, ev_id in meta['ev_ids']:
            flow_id = generate_id("Flow_")
            x_pos += 80
            bpmn_lines.append(f'    <bpmn:sequenceFlow id="{flow_id}" sourceRef="{last_id}" targetRef="{ev_id}" />')
            cond_def_id = generate_id("CondDef_")
            bpmn_lines.append(
                f'    <bpmn:intermediateCatchEvent id="{ev_id}" name="{ev_label}">'
                f'<bpmn:incoming>{flow_id}</bpmn:incoming>'
                f'<bpmn:conditionalEventDefinition id="{cond_def_id}">'
                f'<bpmn:condition xsi:type="bpmn:tFormalExpression">{ev_label}</bpmn:condition>'
                f'</bpmn:conditionalEventDefinition></bpmn:intermediateCatchEvent>'
            )
            edges.append(
                f'      <bpmndi:BPMNEdge id="{flow_id}_di" bpmnElement="{flow_id}">'
                f'<di:waypoint x="{last_out_x}" y="{last_out_y}" />'
                f'<di:waypoint x="{x_pos}" y="{y_center}" /></bpmndi:BPMNEdge>'
            )
            shapes.append(
                f'      <bpmndi:BPMNShape id="{ev_id}_di" bpmnElement="{ev_id}">'
                f'<dc:Bounds x="{x_pos}" y="{y_center - 18}" width="36" height="36" /></bpmndi:BPMNShape>'
            )
            last_id = ev_id
            last_out_x = x_pos + 36
            last_out_y = y_center
            x_pos += 36

        branches = meta.get('branches', [])
        if branches:
            split_id = meta['xor_split_id']
            merge_id = meta['xor_merge_id']
            gateway_tag = 'bpmn:parallelGateway' if task.get('gateway_type') == 'parallel' else 'bpmn:exclusiveGateway'
            gateway_name = task['action']

            x_pos += 100
            gw_x = x_pos
            split_flow = generate_id("Flow_")
            bpmn_lines.append(f'    <bpmn:sequenceFlow id="{split_flow}" sourceRef="{last_id}" targetRef="{split_id}" />')
            bpmn_lines.append(
                f'    <{gateway_tag} id="{split_id}" name="{gateway_name}">'
                f'<bpmn:incoming>{split_flow}</bpmn:incoming></{gateway_tag}>'
            )
            edges.append(
                f'      <bpmndi:BPMNEdge id="{split_flow}_di" bpmnElement="{split_flow}">'
                f'<di:waypoint x="{last_out_x}" y="{last_out_y}" />'
                f'<di:waypoint x="{gw_x}" y="{y_center}" /></bpmndi:BPMNEdge>'
            )
            shapes.append(
                f'      <bpmndi:BPMNShape id="{split_id}_di" bpmnElement="{split_id}" isMarkerVisible="true">'
                f'<dc:Bounds x="{gw_x}" y="{y_center - 25}" width="50" height="50" /></bpmndi:BPMNShape>'
            )

            branch_endpoints = []
            branch_rightmost = gw_x + 50
            for index, branch in enumerate(branches):
                branch_tasks = branch.get('tasks', [])
                if not branch_tasks:
                    continue
                prev_id = split_id
                prev_x = gw_x + 25
                prev_y = y_center
                branch_x = gw_x + 130
                branch_label = branch.get('label', '')
                for task_index, branch_meta in enumerate(branch_tasks):
                    branch_task = branch_meta['task']
                    branch_id = branch_meta['task_id']
                    if task_index == 0:
                        for parent_data_object in task.get('data_objects', []):
                            if parent_data_object not in branch_task.setdefault('data_objects', []):
                                branch_task['data_objects'].append(parent_data_object)
                    branch_actor = branch_task['actor']
                    if branch_actor == actor:
                        branch_y = branch_center_y(branch_actor, index, len(branches))
                    else:
                        branch_y = cy(branch_actor)
                    branch_ty = task_y(branch_actor)
                    if branch_actor == actor:
                        branch_ty = branch_y - 40
                    flow_id = generate_id("Flow_")
                    flow_label = f' name="{branch_label}"' if task_index == 0 and branch_label else ''
                    bpmn_lines.append(
                        f'    <bpmn:sequenceFlow id="{flow_id}"{flow_label} sourceRef="{prev_id}" targetRef="{branch_id}" />'
                    )
                    edges.append(
                        f'      <bpmndi:BPMNEdge id="{flow_id}_di" bpmnElement="{flow_id}">'
                        f'<di:waypoint x="{prev_x}" y="{prev_y}" />'
                        f'<di:waypoint x="{branch_x}" y="{branch_y}" /></bpmndi:BPMNEdge>'
                    )

                    recipient_str = f" to {branch_task['recipient']}" if branch_task.get('recipient') else ""
                    task_label = f"{branch_task['action']}{recipient_str}\n({branch_task['source']})"
                    task_tag = branch_task.get('bpmn_type', 'bpmn:task')
                    task_block = f'    <{task_tag} id="{branch_id}" name="{task_label}"><bpmn:incoming>{flow_id}</bpmn:incoming>'

                    for d_index, doc_label in enumerate(branch_task.get('data_objects', [])):
                        data_id = generate_id("DataObj_")
                        ref_id = generate_id("DataRef_")
                        assoc_id = generate_id("Assoc_")
                        task_block += (
                            f'<bpmn:dataOutputAssociation id="{assoc_id}">'
                            f'<bpmn:targetRef>{ref_id}</bpmn:targetRef>'
                            f'</bpmn:dataOutputAssociation>'
                        )
                        bpmn_lines.append(f'    <bpmn:dataObject id="{data_id}" />')
                        bpmn_lines.append(f'    <bpmn:dataObjectReference id="{ref_id}" dataObjectRef="{data_id}" name="{doc_label}" />')
                        doc_x = branch_x + (d_index * 70) - 10
                        doc_y = branch_ty - 80
                        shapes.append(
                            f'      <bpmndi:BPMNShape id="{ref_id}_di" bpmnElement="{ref_id}">'
                            f'<dc:Bounds x="{doc_x}" y="{doc_y}" width="36" height="50" /></bpmndi:BPMNShape>'
                        )
                        edges.append(
                            f'      <bpmndi:BPMNEdge id="{assoc_id}_di" bpmnElement="{assoc_id}">'
                            f'<di:waypoint x="{branch_x + 75}" y="{branch_ty}" />'
                            f'<di:waypoint x="{doc_x + 18}" y="{doc_y + 50}" /></bpmndi:BPMNEdge>'
                        )

                    task_block += f'</{task_tag}>'
                    bpmn_lines.append(task_block)
                    shapes.append(
                        f'      <bpmndi:BPMNShape id="{branch_id}_di" bpmnElement="{branch_id}">'
                        f'<dc:Bounds x="{branch_x}" y="{branch_ty}" width="150" height="80" /></bpmndi:BPMNShape>'
                    )

                    if branch_task.get('timer'):
                        timer_id = generate_id("Timer_")
                        bpmn_lines.append(
                            f'    <bpmn:boundaryEvent id="{timer_id}" attachedToRef="{branch_id}" cancelActivity="false">'
                            f'<bpmn:timerEventDefinition>'
                            f'<bpmn:timeDuration xsi:type="bpmn:tFormalExpression">{branch_task["timer"]}</bpmn:timeDuration>'
                            f'</bpmn:timerEventDefinition></bpmn:boundaryEvent>'
                        )
                        shapes.append(
                            f'      <bpmndi:BPMNShape id="{timer_id}_di" bpmnElement="{timer_id}">'
                            f'<dc:Bounds x="{branch_x + 132}" y="{branch_ty + 60}" width="36" height="36" /></bpmndi:BPMNShape>'
                        )

                    prev_id = branch_id
                    prev_x = branch_x + 150
                    prev_y = branch_y
                    branch_x += 210
                    branch_rightmost = max(branch_rightmost, prev_x)

                branch_endpoints.append((prev_id, prev_x, prev_y))

            merge_x = branch_rightmost + 90
            merge_incoming_ids = []
            for prev_id, prev_x, prev_y in branch_endpoints:
                flow_id = generate_id("Flow_")
                bpmn_lines.append(f'    <bpmn:sequenceFlow id="{flow_id}" sourceRef="{prev_id}" targetRef="{merge_id}" />')
                merge_incoming_ids.append(flow_id)
                edges.append(
                    f'      <bpmndi:BPMNEdge id="{flow_id}_di" bpmnElement="{flow_id}">'
                    f'<di:waypoint x="{prev_x}" y="{prev_y}" />'
                    f'<di:waypoint x="{merge_x}" y="{y_center}" /></bpmndi:BPMNEdge>'
                )

            incoming_xml = ''.join(f'<bpmn:incoming>{flow_id}</bpmn:incoming>' for flow_id in merge_incoming_ids)
            bpmn_lines.append(f'    <{gateway_tag} id="{merge_id}">{incoming_xml}</{gateway_tag}>')
            shapes.append(
                f'      <bpmndi:BPMNShape id="{merge_id}_di" bpmnElement="{merge_id}" isMarkerVisible="true">'
                f'<dc:Bounds x="{merge_x}" y="{y_center - 25}" width="50" height="50" /></bpmndi:BPMNShape>'
            )

            note_lines = []
            for note in task.get('article_notes', []):
                if note and note not in note_lines:
                    note_lines.append(note)
            for note in task.get('notes', []):
                if note and note not in note_lines:
                    note_lines.append(note)
            if note_lines:
                annotation_id = generate_id("Annotation_")
                assoc_id = generate_id("Assoc_Annot_")
                annotations.append(
                    f'    <bpmn:textAnnotation id="{annotation_id}"><bpmn:text>{"&#10;".join(note_lines)}</bpmn:text></bpmn:textAnnotation>'
                )
                annotation_edges.append(
                    f'    <bpmn:association id="{assoc_id}" sourceRef="{split_id}" targetRef="{annotation_id}" />'
                )
                note_x = gw_x + 210
                note_y = ty - 20
                note_h = max(80, 20 * len(note_lines) + 20)
                shapes.append(
                    f'      <bpmndi:BPMNShape id="{annotation_id}_di" bpmnElement="{annotation_id}">'
                    f'<dc:Bounds x="{note_x}" y="{note_y}" width="260" height="{note_h}" /></bpmndi:BPMNShape>'
                )
                edges.append(
                    f'      <bpmndi:BPMNEdge id="{assoc_id}_di" bpmnElement="{assoc_id}">'
                    f'<di:waypoint x="{gw_x + 50}" y="{y_center}" />'
                    f'<di:waypoint x="{note_x}" y="{note_y + note_h // 2}" /></bpmndi:BPMNEdge>'
                )

            last_id = merge_id
            last_out_x = merge_x + 50
            last_out_y = y_center
            x_pos = merge_x + 50
            continue

        xor_split_id = meta['xor_split_id']
        x_task = x_pos + 140

        has_gateway = meta['has_gateway']
        gw_split_id = meta['gw_split_id']
        gw_merge_id = meta['gw_merge_id']
        if has_gateway:
            split_flow = generate_id("Flow_")
            x_pos += 100
            gw_x = x_pos
            gw_name = f"If {task['gateway_cond']}?"
            bpmn_lines.append(f'    <bpmn:sequenceFlow id="{split_flow}" sourceRef="{last_id}" targetRef="{gw_split_id}" />')
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
            last_out_x = gw_x + 50
            last_out_y = y_center
            x_task = gw_x + 120
            x_pos = gw_x

        flow_id = generate_id("Flow_Yes_" if has_gateway and not xor_split_id else "Flow_")
        flow_label = ' name="Yes"' if has_gateway and not xor_split_id else ''
        bpmn_lines.append(f'    <bpmn:sequenceFlow id="{flow_id}"{flow_label} sourceRef="{last_id}" targetRef="{task_id}" />')
        edges.append(
            f'      <bpmndi:BPMNEdge id="{flow_id}_di" bpmnElement="{flow_id}">'
            f'<di:waypoint x="{last_out_x}" y="{last_out_y}" />'
            f'<di:waypoint x="{x_task}" y="{y_center}" /></bpmndi:BPMNEdge>'
        )

        recipient_str = f" to {task['recipient']}" if task.get('recipient') else ""
        task_label = f"{task['action']}{recipient_str}\n({task['source']})"
        task_tag = task['bpmn_type']
        task_block = (
            f'    <{task_tag} id="{task_id}" name="{task_label}">'
            f'<bpmn:incoming>{flow_id}</bpmn:incoming>'
        )

        for d_index, doc_label in enumerate(task.get('data_objects', [])):
            data_id = generate_id("DataObj_")
            ref_id = generate_id("DataRef_")
            assoc_id = generate_id("Assoc_")
            task_block += (
                f'<bpmn:dataOutputAssociation id="{assoc_id}">'
                f'<bpmn:targetRef>{ref_id}</bpmn:targetRef>'
                f'</bpmn:dataOutputAssociation>'
            )
            bpmn_lines.append(f'    <bpmn:dataObject id="{data_id}" />')
            bpmn_lines.append(f'    <bpmn:dataObjectReference id="{ref_id}" dataObjectRef="{data_id}" name="{doc_label}" />')
            doc_x = x_task + (d_index * 70) - 10
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

        note_lines = []
        for note in task.get('article_notes', []):
            if note and note not in note_lines:
                note_lines.append(note)
        for note in task.get('notes', []):
            if note and note not in note_lines:
                note_lines.append(note)
        for alt_label in task.get('or_alternatives', []):
            if alt_label and alt_label not in note_lines:
                note_lines.append(alt_label)
        if note_lines:
            annotation_id = generate_id("Annotation_")
            assoc_id = generate_id("Assoc_Annot_")
            annotations.append(
                f'    <bpmn:textAnnotation id="{annotation_id}"><bpmn:text>{"&#10;".join(note_lines)}</bpmn:text></bpmn:textAnnotation>'
            )
            annotation_edges.append(
                f'    <bpmn:association id="{assoc_id}" sourceRef="{task_id}" targetRef="{annotation_id}" />'
            )
            note_x = x_task + 210
            note_y = ty - 20
            note_h = max(80, 20 * len(note_lines) + 20)
            shapes.append(
                f'      <bpmndi:BPMNShape id="{annotation_id}_di" bpmnElement="{annotation_id}">'
                f'<dc:Bounds x="{note_x}" y="{note_y}" width="260" height="{note_h}" /></bpmndi:BPMNShape>'
            )
            edges.append(
                f'      <bpmndi:BPMNEdge id="{assoc_id}_di" bpmnElement="{assoc_id}">'
                f'<di:waypoint x="{x_task + 150}" y="{y_center}" />'
                f'<di:waypoint x="{note_x}" y="{note_y + note_h // 2}" /></bpmndi:BPMNEdge>'
            )

        last_id = task_id
        last_out_x = x_task + 150
        last_out_y = y_center
        x_pos = x_task + 150

        if has_gateway:
            flow_from_task = generate_id("Flow_")
            x_pos += 80
            bpmn_lines.append(f'    <bpmn:sequenceFlow id="{flow_from_task}" sourceRef="{last_id}" targetRef="{gw_merge_id}" />')
            edges.append(
                f'      <bpmndi:BPMNEdge id="{flow_from_task}_di" bpmnElement="{flow_from_task}">'
                f'<di:waypoint x="{last_out_x}" y="{last_out_y}" />'
                f'<di:waypoint x="{x_pos}" y="{y_center}" /></bpmndi:BPMNEdge>'
            )
            flow_no = generate_id("Flow_No_")
            y_bypass = y_center + LANE_H // 3
            bpmn_lines.append(
                f'    <bpmn:sequenceFlow id="{flow_no}" name="No" sourceRef="{gw_split_id}" targetRef="{gw_merge_id}" />'
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
                f'<bpmn:incoming>{flow_no}</bpmn:incoming></bpmn:exclusiveGateway>'
            )
            shapes.append(
                f'      <bpmndi:BPMNShape id="{gw_merge_id}_di" bpmnElement="{gw_merge_id}" isMarkerVisible="true">'
                f'<dc:Bounds x="{x_pos}" y="{y_center - 25}" width="50" height="50" /></bpmndi:BPMNShape>'
            )
            last_id = gw_merge_id
            last_out_x = x_pos + 50
            last_out_y = y_center
            x_pos += 50

    final_flow = generate_id("Flow_")
    x_pos += 100
    bpmn_lines.append(f'    <bpmn:sequenceFlow id="{final_flow}" sourceRef="{last_id}" targetRef="{end_id}" />')
    bpmn_lines.append(
        f'    <bpmn:endEvent id="{end_id}" name="End">'
        f'<bpmn:incoming>{final_flow}</bpmn:incoming></bpmn:endEvent>'
    )
    shapes.append(
        f'      <bpmndi:BPMNShape id="{end_id}_di" bpmnElement="{end_id}">'
        f'<dc:Bounds x="{x_pos}" y="{cy(last_actor) - 18}" width="36" height="36" /></bpmndi:BPMNShape>'
    )
    edges.append(
        f'      <bpmndi:BPMNEdge id="{final_flow}_di" bpmnElement="{final_flow}">'
        f'<di:waypoint x="{last_out_x}" y="{last_out_y}" />'
        f'<di:waypoint x="{x_pos}" y="{cy(last_actor)}" /></bpmndi:BPMNEdge>'
    )

    bpmn_lines.extend(annotations)
    bpmn_lines.extend(annotation_edges)
    bpmn_lines.append('  </bpmn:process>')

    pool_width = x_pos + 200
    pool_height = len(actors_ordered) * LANE_H
    bpmn_lines.append('  <bpmndi:BPMNDiagram id="BPMNDiagram_1">')
    bpmn_lines.append('    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="Collaboration_1">')
    bpmn_lines.append(
        f'      <bpmndi:BPMNShape id="Participant_Process_di" bpmnElement="Participant_Process" isHorizontal="true">'
        f'<dc:Bounds x="50" y="{POOL_Y}" width="{pool_width}" height="{pool_height}" /></bpmndi:BPMNShape>'
    )
    for index, actor in enumerate(actors_ordered):
        lane_y = POOL_Y + index * LANE_H
        bpmn_lines.append(
            f'      <bpmndi:BPMNShape id="Lane_{actor}_di" bpmnElement="Lane_{actor}" isHorizontal="true">'
            f'<dc:Bounds x="80" y="{lane_y}" width="{pool_width - 30}" height="{LANE_H}" /></bpmndi:BPMNShape>'
        )
    bpmn_lines.extend(shapes)
    bpmn_lines.extend(edges)
    bpmn_lines.append('    </bpmndi:BPMNPlane>')
    bpmn_lines.append('  </bpmndi:BPMNDiagram>')
    bpmn_lines.append('</bpmn:definitions>')

    with open(output_file, 'w', encoding='utf-8') as file_obj:
        file_obj.write("\n".join(bpmn_lines))
    print(f"BPMN gespeichert unter: {output_file}")
