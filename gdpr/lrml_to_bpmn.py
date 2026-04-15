import re
import uuid
import os

def generate_id(prefix=""):
    return f"{prefix}{uuid.uuid4().hex[:8]}"

def extract_gdpr_ultimate(xml_path, target_article="art_33"):
    print(f"🚀 Starte ULTIMATIVE Extraktion (Lanes, Timer, Daten) für '{target_article}'...\n")
    
    try:
        with open(xml_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"❌ Fehler beim Lesen: {e}")
        return []

    # HOP 1 & 2: Verknüpfungen (Kurzfassung, da bereits bewährt)
    legal_refs = re.findall(r'<lrml:LegalReference[^>]+>', content)
    source_ids = {re.search(r'refersTo="([^"]+)"', r).group(1): re.search(r'refID="([^"]+)"', r).group(1) 
                  for r in legal_refs if target_article.lower() in r.lower() and re.search(r'refersTo="([^"]+)"', r)}

    assoc_blocks = re.findall(r'<lrml:Association>(.*?)</lrml:Association>', content, re.DOTALL | re.IGNORECASE)
    statement_ids = {}
    for block in assoc_blocks:
        src = re.search(r'appliesSource[^>]*keyref="#([^"]+)"', block)
        tgt = re.search(r'toTarget[^>]*keyref="#([^"]+)"', block)
        if src and tgt and src.group(1) in source_ids:
            statement_ids[tgt.group(1)] = source_ids[src.group(1)]

    # HOP 3: Semantische Tiefenanalyse
    raw_tasks = []
    blacklist = ['RexistAtTime', 'Obligation', 'Permission', 'and', 'or', 'atTime', '>', '<', '>=', '<=', '+', 'cause', 'lawfulness', 'fair', 'transparent', 'relatedTo', 'measure', 'DataSubject', 'PersonalData']
    actor_list = ['Controller', 'Processor', 'SupervisoryAuthority']

    for stmt_id, human_ref in statement_ids.items():
        start_idx = content.find(f'<lrml:Statements key="{stmt_id}">')
        if start_idx == -1: continue
        end_idx = content.find('</lrml:Statements>', start_idx)
        playground = content[start_idx:end_idx if end_idx != -1 else len(content)]

        # Variablen Wörterbuch aufbauen
        var_dict = {}
        if_match = re.search(r'<ruleml:if>(.*?)</ruleml:if>', playground, re.DOTALL | re.IGNORECASE)
        if if_match:
            for atom in re.findall(r'<ruleml:Atom[^>]*>(.*?)</ruleml:Atom>', if_match.group(1), re.DOTALL):
                rel = re.search(r'<ruleml:Rel[^>]*iri="[^"]*:([^"]+)"', atom)
                var = re.search(r'<ruleml:Var[^>]*key="([^"]+)"', atom)
                if rel and var and rel.group(1) not in blacklist:
                    var_dict[var.group(1)] = rel.group(1)

        # Aktionen finden
        then_match = re.search(r'<ruleml:then>(.*?)</ruleml:then>', playground, re.DOTALL | re.IGNORECASE)
        if then_match:
            for atom in re.findall(r'<ruleml:Atom[^>]*>(.*?)</ruleml:Atom>', then_match.group(1), re.DOTALL):
                rel = re.search(r'<ruleml:Rel[^>]*iri="[^"]*:([^"]+)"', atom)
                if not rel or rel.group(1) in blacklist: continue
                
                verb = rel.group(1)
                objects = [var_dict[v] for v in re.findall(r'<ruleml:Var[^>]*keyref="([^"]+)"', atom) if v in var_dict]
                objects.extend(re.findall(r'<ruleml:Fun[^>]*iri="[^"]*:([^"]+)"', atom))
                
                # Wir fischen nach harten Zeitangaben (z.B. 72h aus <ruleml:Ind>72h</ruleml:Ind>)
                time_inds = re.findall(r'<ruleml:Ind>([^<]+)</ruleml:Ind>', playground)
                
                actor = next((o for o in objects if o in actor_list), "System")
                objects = [o for o in objects if o not in actor_list]

                raw_tasks.append({
                    "actor": actor, "verb": verb, "objects": objects, 
                    "times": time_inds, "source": human_ref
                })

    # HOP 4: Konsolidierung (Daten, Zeiten & Lanes)
    processed_tasks = []
    data_verbs = ['Describe', 'Contain', 'Document', 'partOf', 'Define']
    junk_words = ['System', 'possible', 'allInfoAbout']
    
    current_actor = "Controller" 
    
    for rt in raw_tasks:
        src = rt['source'].replace('GDPR:art_', 'Art. ').replace('__para_', ' Abs. ')
        src = re.sub(r'__content__list_\d+__point_([a-z])', r' lit. \1', src)
        
        if rt['actor'] != "System": current_actor = rt['actor']
        else: rt['actor'] = current_actor 
            
        clean_objects = [o for o in rt['objects'] if o not in junk_words]
        obj_string = " ".join(clean_objects) if clean_objects else (rt['objects'][0] if rt['objects'] else "")
        
        # Zeit-Check
        timer = None
        if 'nonDelayed' in rt['verb']: timer = "Unverzüglich"
        elif any('h' in t or 'd' in t for t in rt['times']): timer = next(t for t in rt['times'] if 'h' in t or 'd' in t)
        
        # Ist es ein Datenobjekt oder eine echte Aufgabe?
        if rt['verb'] in data_verbs and processed_tasks:
            processed_tasks[-1]['data_objects'].append(f"{obj_string} ({rt['verb']})")
        elif rt['verb'] != 'nonDelayed':
            processed_tasks.append({
                "id": generate_id("Task_"),
                "actor": rt['actor'],
                "action": f"{rt['verb']} {obj_string}".strip(),
                "source": src,
                "timer": timer,
                "data_objects": []
            })

    print(f"✅ HOP 4: {len(processed_tasks)} Multidimensionale Aufgaben generiert!")
    return processed_tasks

def generate_bpmn_ultimate(tasks, output_file):
    if not tasks: return

    print("🏗️ Generiere BPMN 2.0 XML inkl. Lanes, Timer und DataObjects...")
    
    bpmn_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" xmlns:di="http://www.omg.org/spec/DD/20100524/DI" id="Definitions_1" targetNamespace="http://bpmn.io/schema/bpmn">',
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
    
    # Bahnen etwas höher machen, damit Dokumente Platz haben
    lane_y_map = {}
    for idx, actor in enumerate(actors_found):
        lane_y_map[actor] = 100 + (idx * 280) 

    first_y = lane_y_map[tasks[0]['actor']] + 40
    x_pos = 100
    
    # WICHTIGER FIX: Wir speichern die exakten X/Y-Ausgänge der jeweils letzten Box!
    last_id = start_id
    last_out_x = x_pos + 36
    last_out_y = first_y + 18
    
    shapes.append(f'      <bpmndi:BPMNShape id="{start_id}_di" bpmnElement="{start_id}"><dc:Bounds x="{x_pos}" y="{first_y}" width="36" height="36" /></bpmndi:BPMNShape>')

    for task in tasks:
        task_id = task['id']
        flow_id = generate_id("Flow_")
        
        y_pos = lane_y_map[task['actor']] + 60
        x_pos += 260 # Mehr Abstand horizontal
        
        bpmn_lines.append(f'    <bpmn:sequenceFlow id="{flow_id}" sourceRef="{last_id}" targetRef="{task_id}" />')
        task_label = f"{task['action']}\n({task['source']})"
        
        task_block = f'    <bpmn:task id="{task_id}" name="{task_label}">'
        task_block += f'<bpmn:incoming>{flow_id}</bpmn:incoming>'
        
        # --- DATA OBJECTS ---
        if task['data_objects']:
            doc_label = "\n".join(task['data_objects'])
            data_id = generate_id("DataObj_")
            ref_id = generate_id("DataRef_")
            assoc_id = generate_id("Assoc_")
            
            task_block += f'<bpmn:dataOutputAssociation id="{assoc_id}"><bpmn:targetRef>{ref_id}</bpmn:targetRef></bpmn:dataOutputAssociation>'
            task_block += '</bpmn:task>'
            bpmn_lines.append(task_block)
            
            bpmn_lines.append(f'    <bpmn:dataObject id="{data_id}" />')
            bpmn_lines.append(f'    <bpmn:dataObjectReference id="{ref_id}" dataObjectRef="{data_id}" name="{doc_label}" />')
            
            # Dokument höher zeichnen
            doc_y = y_pos - 80
            shapes.append(f'      <bpmndi:BPMNShape id="{ref_id}_di" bpmnElement="{ref_id}"><dc:Bounds x="{x_pos+50}" y="{doc_y}" width="36" height="50" /></bpmndi:BPMNShape>')
            edges.append(f'      <bpmndi:BPMNEdge id="{assoc_id}_di" bpmnElement="{assoc_id}"><di:waypoint x="{x_pos+75}" y="{y_pos}" /><di:waypoint x="{x_pos+75}" y="{doc_y+50}" /></bpmndi:BPMNEdge>')
        else:
            task_block += '</bpmn:task>'
            bpmn_lines.append(task_block)
            
        # FIX PFEILE: Verbinde exakt den gespeicherten Ausgang mit dem neuen Eingang
        in_x = x_pos
        in_y = y_pos + 40
        edges.append(f'      <bpmndi:BPMNEdge id="{flow_id}_di" bpmnElement="{flow_id}"><di:waypoint x="{last_out_x}" y="{last_out_y}" /><di:waypoint x="{in_x}" y="{in_y}" /></bpmndi:BPMNEdge>')
        
        shapes.append(f'      <bpmndi:BPMNShape id="{task_id}_di" bpmnElement="{task_id}"><dc:Bounds x="{x_pos}" y="{y_pos}" width="150" height="80" /></bpmndi:BPMNShape>')
        
        # --- TIMER ---
        if task['timer']:
            timer_id = generate_id("Timer_")
            bpmn_lines.append(f'    <bpmn:boundaryEvent id="{timer_id}" attachedToRef="{task_id}" cancelActivity="false"><bpmn:timerEventDefinition><bpmn:timeDuration>{task["timer"]}</bpmn:timeDuration></bpmn:timerEventDefinition></bpmn:boundaryEvent>')
            shapes.append(f'      <bpmndi:BPMNShape id="{timer_id}_di" bpmnElement="{timer_id}"><dc:Bounds x="{x_pos+132}" y="{y_pos+62}" width="36" height="36" /></bpmndi:BPMNShape>')

        # Nächster Ausgangspunkt ist genau die Mitte der rechten Kante dieser Box
        last_id = task_id
        last_out_x = x_pos + 150
        last_out_y = y_pos + 40

    # --- END EVENT (Ist wieder da!) ---
    end_id = generate_id("EndEvent_")
    final_flow = generate_id("Flow_")
    x_pos += 260
    
    bpmn_lines.append(f'    <bpmn:sequenceFlow id="{final_flow}" sourceRef="{last_id}" targetRef="{end_id}" />')
    bpmn_lines.append(f'    <bpmn:endEvent id="{end_id}" name="Ende"><bpmn:incoming>{final_flow}</bpmn:incoming></bpmn:endEvent>')
    
    shapes.append(f'      <bpmndi:BPMNShape id="{end_id}_di" bpmnElement="{end_id}"><dc:Bounds x="{x_pos}" y="{last_out_y-18}" width="36" height="36" /></bpmndi:BPMNShape>')
    edges.append(f'      <bpmndi:BPMNEdge id="{final_flow}_di" bpmnElement="{final_flow}"><di:waypoint x="{last_out_x}" y="{last_out_y}" /><di:waypoint x="{x_pos}" y="{last_out_y}" /></bpmndi:BPMNEdge>')

    bpmn_lines.append('  </bpmn:process>')
    
    # Diagramm rendern
    bpmn_lines.append('  <bpmndi:BPMNDiagram id="BPMNDiagram_1">')
    bpmn_lines.append('    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="Collaboration_1">')
    
    pool_height = len(actors_found) * 280
    bpmn_lines.append(f'      <bpmndi:BPMNShape id="Participant_Process_di" bpmnElement="Participant_Process" isHorizontal="true"><dc:Bounds x="50" y="50" width="{x_pos+150}" height="{pool_height}" /></bpmndi:BPMNShape>')
    for idx, actor in enumerate(actors_found):
        lane_y = 50 + (idx * 280)
        bpmn_lines.append(f'      <bpmndi:BPMNShape id="Lane_{actor}_di" bpmnElement="Lane_{actor}" isHorizontal="true"><dc:Bounds x="80" y="{lane_y}" width="{x_pos+120}" height="280" /></bpmndi:BPMNShape>')

    bpmn_lines.extend(shapes)
    bpmn_lines.extend(edges)
    bpmn_lines.append('    </bpmndi:BPMNPlane>')
    bpmn_lines.append('  </bpmndi:BPMNDiagram>')
    bpmn_lines.append('</bpmn:definitions>')
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(bpmn_lines))

if __name__ == "__main__":
    xml_input_path = "daprecokb/gdpr/rioKB_GDPR.xml"
    target = "art_33"
    
    if os.path.exists(xml_input_path):
        extracted_tasks = extract_gdpr_ultimate(xml_input_path, target_article=target)
        generate_bpmn_ultimate(extracted_tasks, f"{target}_process_master.bpmn")
    else:
        print(f"FEHLER: Datei nicht gefunden.")