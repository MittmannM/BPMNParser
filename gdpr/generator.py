from utils import generate_id

def generate_bpmn_master(tasks, output_file):
    if not tasks:
        print("Keine Aufgaben zum Generieren vorhanden.")
        return

    print(f"Generiere BPMN 2.0 XML in '{output_file}'...")
    
    bpmn_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" xmlns:di="http://www.omg.org/spec/DD/20100524/DI" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" id="Definitions_1" targetNamespace="http://bpmn.io/schema/bpmn">',
        '  <bpmn:collaboration id="Collaboration_1">',
        '    <bpmn:participant id="Participant_Process" name="GDPR Process" processRef="Process_GDPR" />',
        '  </bpmn:collaboration>',
        '  <bpmn:process id="Process_GDPR" isExecutable="false">'
    ]
    
    actors_found = list(set([t['actor'] for t in tasks]))
    bpmn_lines.append('    <bpmn:laneSet id="LaneSet_1">')
    for actor in actors_found:
        bpmn_lines.append(f'      <bpmn:lane id="Lane_{actor}" name="{actor}">')
        for t in tasks:
            if t['actor'] == actor:
                bpmn_lines.append(f'        <bpmn:flowNodeRef>{t["id"]}</bpmn:flowNodeRef>')
        bpmn_lines.append('      </bpmn:lane>')
    bpmn_lines.append('    </bpmn:laneSet>')

    start_id = generate_id("StartEvent_")
    bpmn_lines.append(f'    <bpmn:startEvent id="{start_id}" name="Start" />')
    
    shapes, edges = [], []
    lane_y_map = {actor: 100 + (idx * 300) for idx, actor in enumerate(actors_found)}
    first_y = lane_y_map[tasks[0]['actor']] + 60
    x_pos = 100
    
    last_id = start_id
    last_out_x, last_out_y = x_pos + 36, first_y + 18
    shapes.append(f'      <bpmndi:BPMNShape id="{start_id}_di" bpmnElement="{start_id}"><dc:Bounds x="{x_pos}" y="{first_y}" width="36" height="36" /></bpmndi:BPMNShape>')

    for task in tasks:
        y_pos = lane_y_map[task['actor']] + 80
        
        # --- EVENTS ---
        for ev in task['events']:
            ev_id = generate_id("Event_")
            ev_flow = generate_id("Flow_")
            x_pos += 100
            bpmn_lines.append(f'    <bpmn:sequenceFlow id="{ev_flow}" sourceRef="{last_id}" targetRef="{ev_id}" />')
            cond_def_id = generate_id("CondDef_")
            bpmn_lines.append(f'    <bpmn:intermediateCatchEvent id="{ev_id}" name="{ev}"><bpmn:incoming>{ev_flow}</bpmn:incoming><bpmn:conditionalEventDefinition id="{cond_def_id}"><bpmn:condition xsi:type="bpmn:tFormalExpression">{ev}</bpmn:condition></bpmn:conditionalEventDefinition></bpmn:intermediateCatchEvent>')
            edges.append(f'      <bpmndi:BPMNEdge id="{ev_flow}_di" bpmnElement="{ev_flow}"><di:waypoint x="{last_out_x}" y="{last_out_y}" /><di:waypoint x="{x_pos}" y="{y_pos+25}" /></bpmndi:BPMNEdge>')
            shapes.append(f'      <bpmndi:BPMNShape id="{ev_id}_di" bpmnElement="{ev_id}"><dc:Bounds x="{x_pos}" y="{y_pos+7}" width="36" height="36" /></bpmndi:BPMNShape>')
            last_id = ev_id
            last_out_x, last_out_y = x_pos + 36, y_pos + 25

        # --- GATEWAYS & TASKS ---
        task_id = task['id']
        x_task = x_pos + 180
        has_gateway = bool(task['gateway_cond'])
        gw_split_id = None
        
        if has_gateway:
            gw_split_id = generate_id("Gateway_Split_")
            split_flow = generate_id("Flow_")
            x_pos += 120
            gw_tag = "bpmn:exclusiveGateway"
            gw_name = f"If {task['gateway_cond']}?"
            bpmn_lines.append(f'    <bpmn:sequenceFlow id="{split_flow}" sourceRef="{last_id}" targetRef="{gw_split_id}" />')
            bpmn_lines.append(f'    <{gw_tag} id="{gw_split_id}" name="{gw_name}"><bpmn:incoming>{split_flow}</bpmn:incoming></{gw_tag}>')
            edges.append(f'      <bpmndi:BPMNEdge id="{split_flow}_di" bpmnElement="{split_flow}"><di:waypoint x="{last_out_x}" y="{last_out_y}" /><di:waypoint x="{x_pos}" y="{y_pos+25}" /></bpmndi:BPMNEdge>')
            shapes.append(f'      <bpmndi:BPMNShape id="{gw_split_id}_di" bpmnElement="{gw_split_id}" isMarkerVisible="true"><dc:Bounds x="{x_pos}" y="{y_pos}" width="50" height="50" /></bpmndi:BPMNShape>')
            last_id = gw_split_id
            last_out_x, last_out_y = x_pos + 50, y_pos + 25

        # --- XOR ALTERNATIVES ---
        or_alts = task.get('or_alternatives', [])
        xor_split_id = None
        xor_merge_id = None
        if or_alts and len(or_alts) >= 2:
            xor_split_id = generate_id("XOR_Split_")
            xor_merge_id = generate_id("XOR_Merge_")
            xor_flow_in = generate_id("Flow_")
            x_pos += 140
            x_xor_split = x_pos
            bpmn_lines.append(f'    <bpmn:sequenceFlow id="{xor_flow_in}" sourceRef="{last_id}" targetRef="{xor_split_id}" />')
            bpmn_lines.append(f'    <bpmn:exclusiveGateway id="{xor_split_id}" name="Measures Type?"><bpmn:incoming>{xor_flow_in}</bpmn:incoming></bpmn:exclusiveGateway>')
            edges.append(f'      <bpmndi:BPMNEdge id="{xor_flow_in}_di" bpmnElement="{xor_flow_in}"><di:waypoint x="{last_out_x}" y="{last_out_y}" /><di:waypoint x="{x_xor_split}" y="{y_pos+25}" /></bpmndi:BPMNEdge>')
            shapes.append(f'      <bpmndi:BPMNShape id="{xor_split_id}_di" bpmnElement="{xor_split_id}" isMarkerVisible="true"><dc:Bounds x="{x_xor_split}" y="{y_pos}" width="50" height="50" /></bpmndi:BPMNShape>')
            x_alt_tasks = x_xor_split + 120
            alt_end_ids = []
            for alt_idx, alt_label in enumerate(or_alts):
                alt_task_id = generate_id("AltTask_")
                alt_flow = generate_id("Flow_Alt_")
                alt_y = y_pos + (alt_idx * 100) - 50
                bpmn_lines.append(f'    <bpmn:sequenceFlow id="{alt_flow}" name="{alt_label}" sourceRef="{xor_split_id}" targetRef="{alt_task_id}" />')
                bpmn_lines.append(f'    <bpmn:task id="{alt_task_id}" name="{alt_label}"><bpmn:incoming>{alt_flow}</bpmn:incoming></bpmn:task>')
                edges.append(f'      <bpmndi:BPMNEdge id="{alt_flow}_di" bpmnElement="{alt_flow}"><di:waypoint x="{x_xor_split+50}" y="{y_pos+25}" /><di:waypoint x="{x_alt_tasks}" y="{alt_y+30}" /></bpmndi:BPMNEdge>')
                shapes.append(f'      <bpmndi:BPMNShape id="{alt_task_id}_di" bpmnElement="{alt_task_id}"><dc:Bounds x="{x_alt_tasks}" y="{alt_y}" width="150" height="60" /></bpmndi:BPMNShape>')
                alt_end_ids.append((alt_task_id, alt_y))
            x_xor_merge = x_alt_tasks + 200
            for alt_task_id_m, alt_y_m in alt_end_ids:
                merge_flow = generate_id("Flow_Merge_")
                bpmn_lines.append(f'    <bpmn:sequenceFlow id="{merge_flow}" sourceRef="{alt_task_id_m}" targetRef="{xor_merge_id}" />')
                edges.append(f'      <bpmndi:BPMNEdge id="{merge_flow}_di" bpmnElement="{merge_flow}"><di:waypoint x="{x_alt_tasks+150}" y="{alt_y_m+30}" /><di:waypoint x="{x_xor_merge}" y="{y_pos+25}" /></bpmndi:BPMNEdge>')
            bpmn_lines.append(f'    <bpmn:exclusiveGateway id="{xor_merge_id}"></bpmn:exclusiveGateway>')
            shapes.append(f'      <bpmndi:BPMNShape id="{xor_merge_id}_di" bpmnElement="{xor_merge_id}" isMarkerVisible="true"><dc:Bounds x="{x_xor_merge}" y="{y_pos}" width="50" height="50" /></bpmndi:BPMNShape>')
            last_id = xor_merge_id
            last_out_x, last_out_y = x_xor_merge + 50, y_pos + 25
            x_task = x_xor_merge + 120
            x_pos = x_xor_merge

        flow_id = generate_id("Flow_Yes_" if has_gateway and not xor_split_id else "Flow_")
        flow_label = ' name="Yes"' if has_gateway and not xor_split_id else ''
        bpmn_lines.append(f'    <bpmn:sequenceFlow id="{flow_id}"{flow_label} sourceRef="{last_id}" targetRef="{task_id}" />')
        edges.append(f'      <bpmndi:BPMNEdge id="{flow_id}_di" bpmnElement="{flow_id}"><di:waypoint x="{last_out_x}" y="{last_out_y}" /><di:waypoint x="{x_task}" y="{y_pos+25}" /></bpmndi:BPMNEdge>')
        
        recipient_str = f" to {task['recipient']}" if task.get('recipient') else ""
        task_label = f"{task['action']}{recipient_str}\n({task['source']})"
        task_tag = task['bpmn_type']
        task_block = f'    <{task_tag} id="{task_id}" name="{task_label}"><bpmn:incoming>{flow_id}</bpmn:incoming>'
        
        if task['data_objects']:
            for d_idx, doc_label in enumerate(task['data_objects']):
                data_id = generate_id("DataObj_")
                ref_id = generate_id("DataRef_")
                assoc_id = generate_id("Assoc_")
                task_block += f'<bpmn:dataOutputAssociation id="{assoc_id}"><bpmn:targetRef>{ref_id}</bpmn:targetRef></bpmn:dataOutputAssociation>'
                bpmn_lines.append(f'    <bpmn:dataObject id="{data_id}" />')
                bpmn_lines.append(f'    <bpmn:dataObjectReference id="{ref_id}" dataObjectRef="{data_id}" name="{doc_label}" />')
                doc_x, doc_y = x_task + (d_idx * 65) - 20, y_pos - 100
                shapes.append(f'      <bpmndi:BPMNShape id="{ref_id}_di" bpmnElement="{ref_id}"><dc:Bounds x="{doc_x}" y="{doc_y}" width="36" height="50" /></bpmndi:BPMNShape>')
                edges.append(f'      <bpmndi:BPMNEdge id="{assoc_id}_di" bpmnElement="{assoc_id}"><di:waypoint x="{x_task+75}" y="{y_pos-15}" /><di:waypoint x="{doc_x+18}" y="{doc_y+50}" /></bpmndi:BPMNEdge>')

        task_block += f'</{task_tag}>'
        bpmn_lines.append(task_block)
        shapes.append(f'      <bpmndi:BPMNShape id="{task_id}_di" bpmnElement="{task_id}"><dc:Bounds x="{x_task}" y="{y_pos-15}" width="150" height="80" /></bpmndi:BPMNShape>')
        
        if task['timer']:
            timer_id = generate_id("Timer_")
            bpmn_lines.append(f'    <bpmn:boundaryEvent id="{timer_id}" attachedToRef="{task_id}" cancelActivity="false"><bpmn:timerEventDefinition><bpmn:timeDuration xsi:type="bpmn:tFormalExpression">{task["timer"]}</bpmn:timeDuration></bpmn:timerEventDefinition></bpmn:boundaryEvent>')
            shapes.append(f'      <bpmndi:BPMNShape id="{timer_id}_di" bpmnElement="{timer_id}"><dc:Bounds x="{x_task+132}" y="{y_pos+47}" width="36" height="36" /></bpmndi:BPMNShape>')

        last_id, last_out_x, last_out_y = task_id, x_task + 150, y_pos + 25

        if has_gateway:
            gw_merge_id = generate_id("Gateway_Merge_")
            flow_from_task = generate_id("Flow_")
            x_pos = x_task + 200
            bpmn_lines.append(f'    <bpmn:sequenceFlow id="{flow_from_task}" sourceRef="{last_id}" targetRef="{gw_merge_id}" />')
            edges.append(f'      <bpmndi:BPMNEdge id="{flow_from_task}_di" bpmnElement="{flow_from_task}"><di:waypoint x="{last_out_x}" y="{last_out_y}" /><di:waypoint x="{x_pos}" y="{y_pos+25}" /></bpmndi:BPMNEdge>')
            flow_no, y_bypass = generate_id("Flow_No_"), y_pos + 120
            bpmn_lines.append(f'    <bpmn:sequenceFlow id="{flow_no}" name="No" sourceRef="{gw_split_id}" targetRef="{gw_merge_id}" />')
            edges.append(f'      <bpmndi:BPMNEdge id="{flow_no}_di" bpmnElement="{flow_no}"><di:waypoint x="{x_task-120+25}" y="{y_pos+50}" /><di:waypoint x="{x_task-120+25}" y="{y_bypass}" /><di:waypoint x="{x_pos+25}" y="{y_bypass}" /><di:waypoint x="{x_pos+25}" y="{y_pos+50}" /></bpmndi:BPMNEdge>')
            bpmn_lines.append(f'    <bpmn:exclusiveGateway id="{gw_merge_id}"><bpmn:incoming>{flow_from_task}</bpmn:incoming><bpmn:incoming>{flow_no}</bpmn:incoming></bpmn:exclusiveGateway>')
            shapes.append(f'      <bpmndi:BPMNShape id="{gw_merge_id}_di" bpmnElement="{gw_merge_id}" isMarkerVisible="true"><dc:Bounds x="{x_pos}" y="{y_pos}" width="50" height="50" /></bpmndi:BPMNShape>')
            last_id, last_out_x, last_out_y = gw_merge_id, x_pos + 50, y_pos + 25
        else:
            x_pos = x_task

    end_id, final_flow = generate_id("EndEvent_"), generate_id("Flow_")
    x_pos += 200
    bpmn_lines.append(f'    <bpmn:sequenceFlow id="{final_flow}" sourceRef="{last_id}" targetRef="{end_id}" />')
    bpmn_lines.append(f'    <bpmn:endEvent id="{end_id}" name="End"><bpmn:incoming>{final_flow}</bpmn:incoming></bpmn:endEvent>')
    shapes.append(f'      <bpmndi:BPMNShape id="{end_id}_di" bpmnElement="{end_id}"><dc:Bounds x="{x_pos}" y="{last_out_y-18}" width="36" height="36" /></bpmndi:BPMNShape>')
    edges.append(f'      <bpmndi:BPMNEdge id="{final_flow}_di" bpmnElement="{final_flow}"><di:waypoint x="{last_out_x}" y="{last_out_y}" /><di:waypoint x="{x_pos}" y="{last_out_y}" /></bpmndi:BPMNEdge>')
    bpmn_lines.append('  </bpmn:process>')
    
    bpmn_lines.append('  <bpmndi:BPMNDiagram id="BPMNDiagram_1">')
    bpmn_lines.append('    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="Collaboration_1">')
    pool_height = len(actors_found) * 300
    bpmn_lines.append(f'      <bpmndi:BPMNShape id="Participant_Process_di" bpmnElement="Participant_Process" isHorizontal="true"><dc:Bounds x="50" y="50" width="{x_pos+150}" height="{pool_height}" /></bpmndi:BPMNShape>')
    for idx, actor in enumerate(actors_found):
        lane_y = 50 + (idx * 300)
        bpmn_lines.append(f'      <bpmndi:BPMNShape id="Lane_{actor}_di" bpmnElement="Lane_{actor}" isHorizontal="true"><dc:Bounds x="80" y="{lane_y}" width="{x_pos+120}" height="300" /></bpmndi:BPMNShape>')
    bpmn_lines.extend(shapes)
    bpmn_lines.extend(edges)
    bpmn_lines.append('    </bpmndi:BPMNPlane>')
    bpmn_lines.append('  </bpmndi:BPMNDiagram>')
    bpmn_lines.append('</bpmn:definitions>')
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(bpmn_lines))
    print(f"BPMN gespeichert unter: {output_file}")
