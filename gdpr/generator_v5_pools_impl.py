from collections import defaultdict
from xml.sax.saxutils import escape

from utils import generate_id


POOL_X = 60
POOL_Y = 50
POOL_H = 220
POOL_GAP = 40
START_X = 140
TASK_W = 170
TASK_H = 80
GATEWAY_W = 50
EVENT_W = 36


def _xml(text):
    return escape(str(text), {'"': '&quot;'})


def _annotation_text(lines):
    return '&#10;'.join(_xml(line) for line in lines if line)


def _expand_post_actions(tasks):
    expanded = []
    for task in tasks:
        expanded.append(dict(task))
        for post_action in task.get('post_actions', []):
            expanded.append({
                'id': generate_id('Task_'),
                'actor': post_action.get('actor') or task['actor'],
                'action': post_action['action'],
                'recipient': post_action.get('recipient'),
                'source': task['source'],
                'timer': None,
                'bpmn_type': post_action.get('bpmn_type', 'bpmn:task'),
                'gateway_cond': None,
                'gateway_type': 'annotation',
                'use_gateway': False,
                'events': [],
                'data_objects': list(post_action.get('data_objects', [])),
                'or_alternatives': [],
                'has_time_bound': False,
                'notes': [],
                'article_notes': [],
                'branches': [],
                'post_actions': [],
            })
    return expanded


def _actors_in_order(tasks):
    ordered = []
    for task in tasks:
        if task['actor'] not in ordered:
            ordered.append(task['actor'])
        if task.get('recipient') and task['recipient'] not in ordered:
            ordered.append(task['recipient'])
        for branch in task.get('branches', []):
            for branch_task in branch.get('tasks', []):
                actor = branch_task.get('actor', task['actor'])
                if actor not in ordered:
                    ordered.append(actor)
                if branch_task.get('recipient') and branch_task['recipient'] not in ordered:
                    ordered.append(branch_task['recipient'])
    return ordered


def _branch_y(base_y, index, total):
    if total <= 1:
        return base_y
    return base_y + int((index - (total - 1) / 2) * 95)


def _task_label(task):
    recipient = f" to {task['recipient']}" if task.get('recipient') else ""
    return f"{task['action']}{recipient}\n({task['source']})"


def _gateway_name(label: str, gateway_tag: str) -> str:
    clean = (label or "").strip()
    if gateway_tag == 'bpmn:exclusiveGateway' and clean and not clean.endswith('?'):
        return f"{clean}?"
    return clean


def _add_annotation(container, attached_id, x, y, lines):
    lines = [line for line in lines if line]
    if not lines:
        return
    annotation_id = generate_id('Annotation_')
    assoc_id = generate_id('Assoc_Annot_')
    height = max(80, 20 * len(lines) + 20)
    note_x = x + 200
    note_y = y - 10
    container['process_lines'].append(
        f'    <bpmn:textAnnotation id="{annotation_id}"><bpmn:text>{_annotation_text(lines)}</bpmn:text></bpmn:textAnnotation>'
    )
    container['process_lines'].append(
        f'    <bpmn:association id="{assoc_id}" sourceRef="{attached_id}" targetRef="{annotation_id}" />'
    )
    container['shapes'].append(
        f'      <bpmndi:BPMNShape id="{annotation_id}_di" bpmnElement="{annotation_id}"><dc:Bounds x="{note_x}" y="{note_y}" width="280" height="{height}" /></bpmndi:BPMNShape>'
    )
    container['edges'].append(
        f'      <bpmndi:BPMNEdge id="{assoc_id}_di" bpmnElement="{assoc_id}"><di:waypoint x="{x}" y="{y + 40}" /><di:waypoint x="{note_x}" y="{note_y + height // 2}" /></bpmndi:BPMNEdge>'
    )


def _add_data_objects(container, x, y, data_objects):
    task_lines = []
    for idx, label in enumerate(data_objects):
        data_id = generate_id('DataObj_')
        ref_id = generate_id('DataRef_')
        assoc_id = generate_id('Assoc_')
        task_lines.append(
            f'<bpmn:dataOutputAssociation id="{assoc_id}"><bpmn:targetRef>{ref_id}</bpmn:targetRef></bpmn:dataOutputAssociation>'
        )
        container['process_lines'].append(f'    <bpmn:dataObject id="{data_id}" />')
        container['process_lines'].append(
            f'    <bpmn:dataObjectReference id="{ref_id}" dataObjectRef="{data_id}" name="{_xml(label)}" />'
        )
        doc_x = x + idx * 70
        doc_y = y - 75
        container['shapes'].append(
            f'      <bpmndi:BPMNShape id="{ref_id}_di" bpmnElement="{ref_id}"><dc:Bounds x="{doc_x}" y="{doc_y}" width="36" height="50" /></bpmndi:BPMNShape>'
        )
        container['edges'].append(
            f'      <bpmndi:BPMNEdge id="{assoc_id}_di" bpmnElement="{assoc_id}"><di:waypoint x="{x + TASK_W // 2}" y="{y}" /><di:waypoint x="{doc_x + 18}" y="{doc_y + 50}" /></bpmndi:BPMNEdge>'
        )
    return ''.join(task_lines)


def _build_process(actor, actor_tasks, actor_index):
    container = {
        'process_id': f'Process_{generate_id(actor.replace(" ", "_") + "_")}',
        'participant_id': f'Participant_{generate_id(actor.replace(" ", "_") + "_")}',
        'process_lines': [],
        'shapes': [],
        'edges': [],
        'task_entry': {},
        'task_exit': {},
        'node_centers': {},
        'start_id': None,
    }
    pool_top = POOL_Y + actor_index * (POOL_H + POOL_GAP)
    center_y = pool_top + POOL_H // 2
    task_y = center_y - TASK_H // 2
    x = START_X

    start_id = generate_id('StartEvent_')
    end_id = generate_id('EndEvent_')
    container['start_id'] = start_id
    container['process_lines'].append(f'    <bpmn:startEvent id="{start_id}" name="Start" />')
    container['shapes'].append(
        f'      <bpmndi:BPMNShape id="{start_id}_di" bpmnElement="{start_id}"><dc:Bounds x="{x}" y="{center_y - 18}" width="{EVENT_W}" height="{EVENT_W}" /></bpmndi:BPMNShape>'
    )
    container['node_centers'][start_id] = (x + EVENT_W // 2, center_y)
    previous_id = start_id
    previous_x = x + EVENT_W
    x += 80

    for task in actor_tasks:
        task_id = task['id']
        if task.get('branches'):
            split_id = generate_id('Gateway_Split_')
            merge_id = generate_id('Gateway_Merge_')
            gateway_tag = 'bpmn:parallelGateway' if task.get('gateway_type') == 'parallel' else 'bpmn:exclusiveGateway'
            gateway_name = _gateway_name(task["action"], gateway_tag)
            split_x = x
            flow_id = generate_id('Flow_')
            container['process_lines'].append(
                f'    <bpmn:sequenceFlow id="{flow_id}" sourceRef="{previous_id}" targetRef="{split_id}" />'
            )
            container['process_lines'].append(
                f'    <{gateway_tag} id="{split_id}" name="{_xml(gateway_name)}"><bpmn:incoming>{flow_id}</bpmn:incoming></{gateway_tag}>'
            )
            container['edges'].append(
                f'      <bpmndi:BPMNEdge id="{flow_id}_di" bpmnElement="{flow_id}"><di:waypoint x="{previous_x}" y="{center_y}" /><di:waypoint x="{split_x}" y="{center_y}" /></bpmndi:BPMNEdge>'
            )
            container['shapes'].append(
                f'      <bpmndi:BPMNShape id="{split_id}_di" bpmnElement="{split_id}" isMarkerVisible="true"><dc:Bounds x="{split_x}" y="{center_y - 25}" width="{GATEWAY_W}" height="{GATEWAY_W}" /></bpmndi:BPMNShape>'
            )
            container['task_entry'][task_id] = split_id
            container['node_centers'][split_id] = (split_x + GATEWAY_W // 2, center_y)

            branch_endpoints = []
            branch_max_x = split_x + GATEWAY_W
            for branch_index, branch in enumerate(task['branches']):
                branch_tasks = branch.get('tasks', [])
                branch_prev = split_id
                branch_prev_x = split_x + GATEWAY_W // 2
                branch_y = _branch_y(center_y, branch_index, len(task['branches']))
                branch_x = split_x + 140
                for branch_task in branch_tasks:
                    branch_task_id = branch_task['id']
                    flow_id = generate_id('Flow_')
                    flow_name = f' name="{_xml(branch["label"])}"' if branch_prev == split_id and branch.get('label') else ''
                    container['process_lines'].append(
                        f'    <bpmn:sequenceFlow id="{flow_id}"{flow_name} sourceRef="{branch_prev}" targetRef="{branch_task_id}" />'
                    )
                    branch_join_x = split_x + GATEWAY_W + 30
                    container['edges'].append(
                        f'      <bpmndi:BPMNEdge id="{flow_id}_di" bpmnElement="{flow_id}">'
                        f'<di:waypoint x="{branch_prev_x}" y="{center_y}" />'
                        f'<di:waypoint x="{branch_join_x}" y="{center_y}" />'
                        f'<di:waypoint x="{branch_join_x}" y="{branch_y}" />'
                        f'<di:waypoint x="{branch_x}" y="{branch_y}" />'
                        f'</bpmndi:BPMNEdge>'
                    )
                    task_tag = branch_task.get('bpmn_type', 'bpmn:task')
                    task_block = (
                        f'    <{task_tag} id="{branch_task_id}" name="{_xml(_task_label(branch_task))}"><bpmn:incoming>{flow_id}</bpmn:incoming>'
                        f'{_add_data_objects(container, branch_x, branch_y - 5, branch_task.get("data_objects", []))}'
                        f'</{task_tag}>'
                    )
                    container['process_lines'].append(task_block)
                    container['shapes'].append(
                        f'      <bpmndi:BPMNShape id="{branch_task_id}_di" bpmnElement="{branch_task_id}"><dc:Bounds x="{branch_x}" y="{branch_y - TASK_H // 2}" width="{TASK_W}" height="{TASK_H}" /></bpmndi:BPMNShape>'
                    )
                    container['node_centers'][branch_task_id] = (branch_x + TASK_W // 2, branch_y)
                    branch_prev = branch_task_id
                    branch_prev_x = branch_x + TASK_W
                    branch_x += 210
                    branch_max_x = max(branch_max_x, branch_prev_x)
                branch_endpoints.append((branch_prev, branch_prev_x, branch_y))

            merge_x = branch_max_x + 100
            merge_incoming = []
            for branch_prev, branch_prev_x, branch_y in branch_endpoints:
                flow_id = generate_id('Flow_')
                merge_incoming.append(flow_id)
                container['process_lines'].append(
                    f'    <bpmn:sequenceFlow id="{flow_id}" sourceRef="{branch_prev}" targetRef="{merge_id}" />'
                )
                merge_join_x = merge_x - 30
                container['edges'].append(
                    f'      <bpmndi:BPMNEdge id="{flow_id}_di" bpmnElement="{flow_id}">'
                    f'<di:waypoint x="{branch_prev_x}" y="{branch_y}" />'
                    f'<di:waypoint x="{merge_join_x}" y="{branch_y}" />'
                    f'<di:waypoint x="{merge_join_x}" y="{center_y}" />'
                    f'<di:waypoint x="{merge_x}" y="{center_y}" />'
                    f'</bpmndi:BPMNEdge>'
                )
            incoming = ''.join(f'<bpmn:incoming>{flow}</bpmn:incoming>' for flow in merge_incoming)
            container['process_lines'].append(f'    <{gateway_tag} id="{merge_id}">{incoming}</{gateway_tag}>')
            container['shapes'].append(
                f'      <bpmndi:BPMNShape id="{merge_id}_di" bpmnElement="{merge_id}" isMarkerVisible="true"><dc:Bounds x="{merge_x}" y="{center_y - 25}" width="{GATEWAY_W}" height="{GATEWAY_W}" /></bpmndi:BPMNShape>'
            )
            container['task_exit'][task_id] = merge_id
            container['node_centers'][merge_id] = (merge_x + GATEWAY_W // 2, center_y)
            _add_annotation(container, split_id, split_x + GATEWAY_W // 2, center_y - 40, [*task.get('article_notes', []), *task.get('notes', [])])
            previous_id = merge_id
            previous_x = merge_x + GATEWAY_W
            x = merge_x + 120
            continue

        flow_id = generate_id('Flow_')
        container['process_lines'].append(
            f'    <bpmn:sequenceFlow id="{flow_id}" sourceRef="{previous_id}" targetRef="{task_id}" />'
        )
        container['edges'].append(
            f'      <bpmndi:BPMNEdge id="{flow_id}_di" bpmnElement="{flow_id}"><di:waypoint x="{previous_x}" y="{center_y}" /><di:waypoint x="{x}" y="{center_y}" /></bpmndi:BPMNEdge>'
        )
        task_tag = task.get('bpmn_type', 'bpmn:task')
        task_block = (
            f'    <{task_tag} id="{task_id}" name="{_xml(_task_label(task))}"><bpmn:incoming>{flow_id}</bpmn:incoming>'
            f'{_add_data_objects(container, x, center_y - 5, task.get("data_objects", []))}'
            f'</{task_tag}>'
        )
        container['process_lines'].append(task_block)
        container['shapes'].append(
            f'      <bpmndi:BPMNShape id="{task_id}_di" bpmnElement="{task_id}"><dc:Bounds x="{x}" y="{task_y}" width="{TASK_W}" height="{TASK_H}" /></bpmndi:BPMNShape>'
        )
        container['task_entry'][task_id] = task_id
        container['task_exit'][task_id] = task_id
        container['node_centers'][task_id] = (x + TASK_W // 2, center_y)
        if task.get('timer'):
            timer_id = generate_id('Timer_')
            container['process_lines'].append(
                f'    <bpmn:boundaryEvent id="{timer_id}" attachedToRef="{task_id}" cancelActivity="false"><bpmn:timerEventDefinition><bpmn:timeDuration xsi:type="bpmn:tFormalExpression">{_xml(task["timer"])}</bpmn:timeDuration></bpmn:timerEventDefinition></bpmn:boundaryEvent>'
            )
            container['shapes'].append(
                f'      <bpmndi:BPMNShape id="{timer_id}_di" bpmnElement="{timer_id}"><dc:Bounds x="{x + TASK_W - 18}" y="{task_y + 58}" width="36" height="36" /></bpmndi:BPMNShape>'
            )
        _add_annotation(container, task_id, x + TASK_W, center_y - 40, [*task.get('article_notes', []), *task.get('notes', []), *task.get('or_alternatives', [])])
        previous_id = task_id
        previous_x = x + TASK_W
        x += 250

    flow_id = generate_id('Flow_')
    container['process_lines'].append(
        f'    <bpmn:sequenceFlow id="{flow_id}" sourceRef="{previous_id}" targetRef="{end_id}" />'
    )
    container['process_lines'].append(
        f'    <bpmn:endEvent id="{end_id}" name="End"><bpmn:incoming>{flow_id}</bpmn:incoming></bpmn:endEvent>'
    )
    container['edges'].append(
        f'      <bpmndi:BPMNEdge id="{flow_id}_di" bpmnElement="{flow_id}"><di:waypoint x="{previous_x}" y="{center_y}" /><di:waypoint x="{x}" y="{center_y}" /></bpmndi:BPMNEdge>'
    )
    container['shapes'].append(
        f'      <bpmndi:BPMNShape id="{end_id}_di" bpmnElement="{end_id}"><dc:Bounds x="{x}" y="{center_y - 18}" width="{EVENT_W}" height="{EVENT_W}" /></bpmndi:BPMNShape>'
    )
    container['node_centers'][end_id] = (x + EVENT_W // 2, center_y)
    container['pool_bounds'] = (POOL_X, pool_top, max(1200, x + 180), POOL_H)
    return container


def generate_bpmn_master(tasks, output_file):
    if not tasks:
        print('Keine Aufgaben zum Generieren vorhanden.')
        return

    expanded_tasks = _expand_post_actions(tasks)
    print(f"Generiere BPMN 2.0 XML in '{output_file}'...")

    actors = _actors_in_order(expanded_tasks)
    actor_positions = {actor: index for index, actor in enumerate(actors)}
    tasks_by_actor = defaultdict(list)
    for task in expanded_tasks:
        tasks_by_actor[task['actor']].append(task)

    processes = []
    task_entry = {}
    task_exit = {}
    node_centers = {}
    max_width = 1200
    for actor in [actor for actor in actors if tasks_by_actor.get(actor)]:
        process = _build_process(actor, tasks_by_actor[actor], actor_positions[actor])
        processes.append((actor, process))
        task_entry.update(process['task_entry'])
        task_exit.update(process['task_exit'])
        node_centers.update(process['node_centers'])
        max_width = max(max_width, process['pool_bounds'][2])

    collaboration_lines = ['  <bpmn:collaboration id="Collaboration_1">']
    blackbox_participants = {}
    participant_by_actor = {}
    for actor, process in processes:
        participant_by_actor[actor] = process['participant_id']
        collaboration_lines.append(
            f'    <bpmn:participant id="{process["participant_id"]}" name="{_xml(actor)}" processRef="{process["process_id"]}" />'
        )
    active_actors = {actor for actor, _ in processes}
    all_participants = []
    for actor in actors:
        if actor in active_actors:
            process = next(proc for act, proc in processes if act == actor)
            all_participants.append((actor, process['participant_id'], True))
            continue
        participant_id = f'Participant_{generate_id(actor.replace(" ", "_") + "_")}'
        blackbox_participants[actor] = participant_id
        participant_by_actor[actor] = participant_id
        collaboration_lines.append(
            f'    <bpmn:participant id="{participant_id}" name="{_xml(actor)}" />'
        )
        all_participants.append((actor, participant_id, False))

    message_shapes = []
    seen_messages = set()
    for task in expanded_tasks:
        recipient = task.get('recipient')
        if not recipient or recipient == task['actor']:
            continue
        source_node = task_exit.get(task['id'])
        if not source_node:
            continue
        target_ref = participant_by_actor.get(recipient)
        if not target_ref:
            continue
        signature = (source_node, target_ref)
        if signature in seen_messages:
            continue
        seen_messages.add(signature)
        message_id = generate_id('MessageFlow_')
        collaboration_lines.append(
            f'    <bpmn:messageFlow id="{message_id}" sourceRef="{source_node}" targetRef="{target_ref}" />'
        )
        sx, sy = node_centers[source_node]
        recipient_index = actor_positions[recipient]
        pool_top = POOL_Y + recipient_index * (POOL_H + POOL_GAP)
        pool_bottom = pool_top + POOL_H
        ty = pool_top if sy < pool_top else pool_bottom
        tx = max(POOL_X + 20, min(sx, POOL_X + max_width - 20))
        message_shapes.append(
            f'      <bpmndi:BPMNEdge id="{message_id}_di" bpmnElement="{message_id}"><di:waypoint x="{sx}" y="{sy}" /><di:waypoint x="{tx}" y="{ty}" /></bpmndi:BPMNEdge>'
        )

    collaboration_lines.append('  </bpmn:collaboration>')

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"'
        ' xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"'
        ' xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"'
        ' xmlns:di="http://www.omg.org/spec/DD/20100524/DI"'
        ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
        ' id="Definitions_1" targetNamespace="http://bpmn.io/schema/bpmn">',
        *collaboration_lines,
    ]

    for _, process in processes:
        lines.append(f'  <bpmn:process id="{process["process_id"]}" isExecutable="false">')
        lines.extend(process['process_lines'])
        lines.append('  </bpmn:process>')

    lines.append('  <bpmndi:BPMNDiagram id="BPMNDiagram_1">')
    lines.append('    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="Collaboration_1">')
    for actor, participant_id, is_active in all_participants:
        actor_index = actor_positions[actor]
        y = POOL_Y + actor_index * (POOL_H + POOL_GAP)
        lines.append(
            f'      <bpmndi:BPMNShape id="{participant_id}_di" bpmnElement="{participant_id}" isHorizontal="true"><dc:Bounds x="{POOL_X}" y="{y}" width="{max_width}" height="{POOL_H}" /></bpmndi:BPMNShape>'
        )
    for _, process in processes:
        lines.extend(process['shapes'])
    for _, process in processes:
        lines.extend(process['edges'])
    lines.extend(message_shapes)
    lines.append('    </bpmndi:BPMNPlane>')
    lines.append('  </bpmndi:BPMNDiagram>')
    lines.append('</bpmn:definitions>')

    with open(output_file, 'w', encoding='utf-8') as file_obj:
        file_obj.write('\n'.join(lines))
    print(f"BPMN gespeichert unter: {output_file}")
