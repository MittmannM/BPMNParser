import re
import uuid
import os

def generate_id(prefix=""):
    return f"{prefix}{uuid.uuid4().hex[:8]}"

def extract_gdpr_master(xml_path, target_article="art_33"):
    print(f"🚀 Starte MASTER-Extraktion (SendTasks, Gateways, Events) für '{target_article}'...\n")
    
    try:
        with open(xml_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"❌ Fehler beim Lesen: {e}")
        return []

    # =========================================================
    # HOP 1 & 2: Verknüpfungen auflösen
    # =========================================================
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

    # =========================================================
    # HOP 3: Pro Statement alle ruleml:Rule-Blöcke iterieren
    # =========================================================
    raw_tasks = []

    # Semantische Klassifizierung der Relationen
    # primary_action: bildet einen eigenen BPMN-Task
    # data_property:  wird als Datenobjekt an den letzten Task gehängt
    # event_trigger:  bildet ein intermediateCatchEvent vor dem Task
    # skip:           logisches Rauschen ohne juristische Bedeutung
    PRIMARY_ACTIONS = {
        "Communicate'", "Communicate", "LetterReasonFor", "ComplyWith",
        "Document'", "Document", "Verify"
    }
    DATA_PROPERTIES = {
        "natureOf", "Describe'", "Describe", "Contain'", "Contain",
        "dpoOrCP", "dpoOrCp", "Measure", "TakenToAddress", "ProposedToAddress",
        "imply", "contactDetails", "allInfoAbout", "LikelyConsequences",
        "feasible", "LetterReasonFor", "Define"
    }
    EVENT_TRIGGERS = {"DataBreach", "AwareOf", "PersonalDataProcessing", "AwareOf'", "PersonalDataProcessing'"}
    # SKIP: pure logical/syntactic operators with no legal content on their own
    SKIP = {"RexistAtTime", "atTime", "and'", "or'", "and", "or",
            "cause'", "cause", "relatedTo", "DataSubject", "PersonalData", "Risk'",
            "riskinessRightsFreedoms'", "likely'", "partOf", "possible'", "not'",
            "possible", "not"}
    # Obliged is NOT in SKIP — we resolve it below as a deontic wrapper
    actor_list = {'Controller', 'Processor', 'SupervisoryAuthority'}

    for stmt_id, human_ref in statement_ids.items():
        start_idx = content.find(f'<lrml:Statements key="{stmt_id}">')
        if start_idx == -1: continue
        end_idx = content.find('</lrml:Statements>', start_idx)
        stmt_block = content[start_idx:end_idx if end_idx != -1 else len(content)]


        # Alle ruleml:Rule Blöcke innerhalb des Statements iterieren
        rules = re.findall(r'<ruleml:Rule[^>]*>(.*?)</ruleml:Rule>', stmt_block, re.DOTALL | re.IGNORECASE)
        if not rules:
            rules = [stmt_block]  # fallback: ganzer Block als eine Regel

        for rule_block in rules:
            var_dict = {}
            events = []
            conditions = []
            gateway_type = "exclusive"
            has_time_bound = False
            time_bound_value = None
            or_alternatives = []

            # ---- IF-Block analysieren ----
            if_match = re.search(r'<ruleml:if>(.*?)</ruleml:if>', rule_block, re.DOTALL | re.IGNORECASE)
            if if_match:
                if_block = if_match.group(1)

                # Zeitgrenzen: swrlb:add(:t1, 72h)
                time_m = re.search(r'<ruleml:Fun\s+iri="swrlb:add"\s*/>.*?<ruleml:Ind>([^<]+)</ruleml:Ind>', if_block, re.DOTALL)
                if time_m:
                    has_time_bound = True
                    time_bound_value = time_m.group(1).strip()
                    conditions.append(f"> {time_bound_value} elapsed")

                # Gateway-Typ
                if re.search(r'iri="rioOnto:and"', if_block): gateway_type = "parallel"
                elif re.search(r'iri="rioOnto:or"', if_block): gateway_type = "exclusive"

                # Negation
                if re.search(r'iri="rioOnto:not"', if_block):
                    conditions.append("NOT Possible")

                # Atome im IF-Block
                for atom in re.findall(r'<ruleml:Atom[^>]*>(.*?)</ruleml:Atom>', if_block, re.DOTALL):
                    rel = re.search(r'<ruleml:Rel[^>]*iri="[^"]*:([^"]+)"', atom)
                    if not rel: continue
                    concept = rel.group(1)
                    # Map defining variables (key=) to their concept type
                    var = re.search(r'<ruleml:Var[^>]*key="([^"]+)"', atom)
                    if var: var_dict[var.group(1)] = concept
                    # ALSO map reference variables (keyref=) when they appear inside a PRIMARY_ACTION atom:
                    # This handles: possible'(:ep1, :en1) followed by Communicate'(:en1, ...)
                    # -> :en1 used in Communicate' atom means :en1 is a Communicate' event
                    if concept in PRIMARY_ACTIONS:
                        keyrefs = re.findall(r'<ruleml:Var[^>]*keyref="([^"]+)"', atom)
                        # Map event variable: override unless already mapped to another PRIMARY_ACTION
                        if keyrefs:
                            existing = var_dict.get(keyrefs[0])
                            if existing is None or existing not in PRIMARY_ACTIONS:
                                var_dict[keyrefs[0]] = concept
                    if concept in EVENT_TRIGGERS:
                        if concept not in events: events.append(concept)
                    elif concept not in SKIP and concept not in actor_list and concept not in DATA_PROPERTIES and concept not in PRIMARY_ACTIONS:
                        if concept not in conditions: conditions.append(concept)


            # ---- THEN-Block analysieren ----
            then_match = re.search(r'<ruleml:then>(.*?)</ruleml:then>', rule_block, re.DOTALL | re.IGNORECASE)
            if not then_match:
                continue

            then_block = then_match.group(1)

            # or' im then-Block → XOR-Alternativen
            if re.search(r'iri="rioOnto:or', then_block):
                if re.search(r'TakenToAddress', then_block): or_alternatives.append("Measures Already Taken")
                if re.search(r'ProposedToAddress', then_block): or_alternatives.append("Measures Proposed to Address")

            primary_task = None
            task_data_objects = []
            task_actor = "System"
            task_timer = None
            task_recipient = None

            # Extract recipient from Expr/Fun in the rule_block (across IF+THEN)
            # DAPRECO Communicate' atoms encode recipients as nested <ruleml:Expr><ruleml:Fun iri="...:SupervisoryAuthority"/>
            # We scan all Fun IRIs and pick the first actor-like one
            all_fun_iris = re.findall(r'<ruleml:Fun[^>]*iri="[^"]*:([^"]+)"', rule_block)
            for fun_name in all_fun_iris:
                if fun_name in {'SupervisoryAuthority', 'Controller', 'Processor'}:
                    task_recipient = fun_name
                    break
            # Fallback: for patterns like Communicate'(:en, :x, :y, info) where :y is an actor
            # The 3rd keyref in a Communicate' atom is typically the recipient
            if not task_recipient:
                for comm_atom in re.findall(r'<ruleml:Atom[^>]*>(.*?)</ruleml:Atom>', rule_block, re.DOTALL):
                    crel = re.search(r'<ruleml:Rel[^>]*iri="[^"]*:(Communicate[\'"]?)"', comm_atom)
                    if crel:
                        comm_refs = re.findall(r'<ruleml:Var[^>]*keyref="([^"]+)"', comm_atom)
                        # comm_refs[0] = event, [1] = sender, [2] = recipient
                        if len(comm_refs) >= 3 and comm_refs[2] in var_dict and var_dict[comm_refs[2]] in actor_list:
                            task_recipient = var_dict[comm_refs[2]]
                            break

            # Pre-pass: map THEN-block variables into var_dict so Obliged resolver works
            for atom in re.findall(r'<ruleml:Atom[^>]*>(.*?)</ruleml:Atom>', then_block, re.DOTALL):
                rel = re.search(r'<ruleml:Rel[^>]*iri="[^"]*:([^"]+)"', atom)
                if not rel: continue
                concept = rel.group(1)
                var_key = re.search(r'<ruleml:Var[^>]*key="([^"]+)"', atom)
                if var_key and var_key.group(1) not in var_dict:
                    var_dict[var_key.group(1)] = concept
                # Also map PRIMARY_ACTION keyrefs from THEN (e.g. Communicate'(:en,:y,...) in THEN)
                if concept in PRIMARY_ACTIONS:
                    keyrefs = re.findall(r'<ruleml:Var[^>]*keyref="([^"]+)"', atom)
                    if keyrefs:
                        existing = var_dict.get(keyrefs[0])
                        if existing is None or existing not in PRIMARY_ACTIONS:
                            var_dict[keyrefs[0]] = concept

            for atom in re.findall(r'<ruleml:Atom[^>]*>(.*?)</ruleml:Atom>', then_block, re.DOTALL):
                rel = re.search(r'<ruleml:Rel[^>]*iri="[^"]*:([^"]+)"', atom)
                if not rel: continue
                verb = rel.group(1)
                if verb in SKIP: continue

                refs = re.findall(r'<ruleml:Var[^>]*keyref="([^"]+)"', atom)
                actor_from_refs = next((var_dict[r] for r in refs if r in var_dict and var_dict[r] in actor_list), None)
                fun_iri = re.search(r'<ruleml:Fun[^>]*iri="[^"]*:([^"]+)"', atom)
                objects = [var_dict[r] for r in refs if r in var_dict and var_dict[r] not in actor_list and var_dict[r] not in PRIMARY_ACTIONS and var_dict[r] not in SKIP]
                if fun_iri and fun_iri.group(1) not in actor_list:
                    objects.append(fun_iri.group(1))

                if verb == "nonDelayed":
                    task_timer = "Without undue delay"
                    continue

                # ---- Deontic Wrapper Resolution ("Obliged" pattern) ----
                # DAPRECO encodes "Controller is obliged to do X" as:
                #   Obliged(:event_var, :time, :actor)
                # where :event_var was defined in the IF-block as Communicate'/Document' etc.
                # We resolve this by looking up the variable in var_dict.
                if verb == "Obliged":
                    # refs[0] is typically the event variable, refs[1] time, refs[2] actor
                    event_var = refs[0] if refs else None
                    if event_var and event_var in var_dict:
                        resolved = var_dict[event_var]
                        if resolved in PRIMARY_ACTIONS and primary_task is None:
                            primary_task = resolved
                            # Actor is the 3rd argument to Obliged
                            actor_var = refs[2] if len(refs) > 2 else None
                            if actor_var and actor_var in var_dict and var_dict[actor_var] in actor_list:
                                task_actor = var_dict[actor_var]
                            else:
                                task_actor = next((v for v in var_dict.values() if v in actor_list), "System")
                    continue

                if verb in PRIMARY_ACTIONS and primary_task is None:
                    primary_task = verb
                    task_actor = actor_from_refs if actor_from_refs else next((v for v in var_dict.values() if v in actor_list), "System")
                    time_inds = re.findall(r'<ruleml:Ind>([^<]+)</ruleml:Ind>', rule_block)
                    if any('h' in t or 'd' in t for t in time_inds):
                        task_timer = next((t for t in time_inds if 'h' in t or 'd' in t), None)
                    # Extract recipient from Fun tags (e.g. SupervisoryAuthority, Controller)
                    fun_recipients = re.findall(r'<ruleml:Fun[^>]*iri="[^"]*:([^"]+)"', atom)
                    for fr in fun_recipients:
                        if fr in actor_list or fr in {'SupervisoryAuthority', 'Controller', 'Processor'}:
                            task_recipient = fr
                            break
                elif verb in PRIMARY_ACTIONS and primary_task is not None:
                    # Additional primary action in the same THEN block (e.g. LetterReasonFor + Communicate')
                    # → create a separate task for it
                    extra_actor = actor_from_refs if actor_from_refs else next((v for v in var_dict.values() if v in actor_list), "System")
                    # Extract recipient for the extra action too
                    extra_recipient = None
                    efun = re.findall(r'<ruleml:Fun[^>]*iri="[^"]*:([^"]+)"', atom)
                    for fr in efun:
                        if fr in actor_list or fr in {'SupervisoryAuthority', 'Controller', 'Processor'}:
                            extra_recipient = fr
                            break
                    raw_tasks.append({
                        "actor": extra_actor,
                        "verb": verb,
                        "data_objects_raw": [],
                        "or_alternatives": [],
                        "timer": None,
                        "source": human_ref,
                        "conditions": list(conditions),
                        "events": [],
                        "gateway_type": gateway_type,
                        "has_time_bound": has_time_bound,
                        "time_bound_value": time_bound_value,
                        "recipient": extra_recipient or task_recipient,
                    })
                elif verb in DATA_PROPERTIES:
                    obj_str = " ".join(o for o in objects if o not in actor_list and o not in SKIP)
                    task_data_objects.append(verb if not obj_str else obj_str)


            # ---- Pattern B: possible' and partOf in IF-block are modal conditions, not SKIP ----
            # Detect these structural signals in IF to add semantic gateway conditions
            if if_match:
                if_block = if_match.group(1)

                # possible' = "it is possible that [action]" → gateway condition
                if re.search(r'iri="rioOnto:possible"', if_block) or re.search(r"iri=\"rioOnto:possible'\"", if_block):
                    conditions.append("Partial Information Available")

                # partOf = notification content is partial subset of all info
                if re.search(r'iri="rioOnto:partOf"', if_block) or re.search(r"iri=\"rioOnto:partOf\"", if_block):
                    if "Partial Information Available" not in conditions:
                        conditions.append("Partial Information Available")

            # ---- Pattern A: Detect if this rule describes CONTENT of an existing obligation ----
            # Signal: the IF-block references a PRIMARY_ACTION (e.g. Communicate') as a precondition,
            # AND the THEN-block contains only data-property verbs (Describe', Contain').
            # In this case, this rule is NOT a new task — it defines mandatory content of a prior task.
            if_refs_primary = if_match and any(
                verb in if_match.group(1)
                for verb in ["Communicate'", "Communicate", "Document'", "Document"]
            )
            then_has_only_data = primary_task is None and bool(task_data_objects)

            if if_refs_primary and then_has_only_data:
                # Find the most recent raw_task with the same PRIMARY VERB referenced in the IF.
                # We do this by finding which verb in if_block was referenced,
                # then look for the latest task with that same verb across the same article.
                article_key = re.search(r'GDPR:(art_\d+)', human_ref)
                article_prefix = article_key.group(1) if article_key else None
                # Determine which primary verb is referenced in IF
                ref_verb = next((v for v in ["Communicate'", "Communicate", "Document'", "Document"]
                                 if v in if_match.group(1)), None)
                ref_verb_humanized = {"Communicate'": "Notify", "Communicate": "Notify",
                                      "Document'": "Document", "Document": "Document"}.get(ref_verb)
                # Backwards search replaced with FORWARD search:
                # content rules in 33(3) should attach to the FIRST matching Notify/Document
                # of the same article (e.g., Controller Notify from 33(1)), not the last.
                for existing in raw_tasks:
                    ex_article = re.search(r'art_\d+', existing['source'])
                    ex_article_key = ex_article.group(0) if ex_article else None
                    ex_humanized = {"Communicate'": "Notify", "Communicate": "Notify",
                                    "Document'": "Document", "Document": "Document"}.get(existing['verb'], existing['verb'])
                    if ex_article_key == article_prefix and (ref_verb_humanized is None or ex_humanized == ref_verb_humanized):
                        for d in task_data_objects:
                            if d not in existing['data_objects_raw']:
                                existing['data_objects_raw'].append(d)
                        if or_alternatives:
                            for alt in or_alternatives:
                                if alt not in existing['or_alternatives']:
                                    existing['or_alternatives'].append(alt)
                        break
                # Do NOT add as a new raw_task

            elif primary_task:
                raw_tasks.append({
                    "actor": task_actor,
                    "verb": primary_task,
                    "data_objects_raw": task_data_objects,
                    "or_alternatives": or_alternatives,
                    "timer": task_timer,
                    "source": human_ref,
                    "conditions": conditions,
                    "events": events,
                    "gateway_type": gateway_type,
                    "has_time_bound": has_time_bound,
                    "time_bound_value": time_bound_value,
                    "recipient": task_recipient,
                })


    # =========================================================
    # HOP 4: Humanizer & Verschmelzung
    # =========================================================
    humanizer = {
        "Communicate'": "Notify", "Communicate": "Notify",
        "LetterReasonFor": "Provide Reason for Delay",
        "Document'": "Document", "Document": "Document",
        "ComplyWith": "Comply With Obligations",
        "Verify": "Verify",
        "DataBreach": "Data Breach Detected",
        "AwareOf": "Became Aware of Breach", "AwareOf'": "Became Aware of Breach",
        "PersonalDataProcessing": "Personal Data Processing",
        "PersonalDataProcessing'": "Personal Data Processing",
        "Measure": "Measures Taken/Proposed",
        "TakenToAddress": "Measures Already Taken",
        "ProposedToAddress": "Measures Proposed",
        "natureOf": "Nature of Breach",
        "dpoOrCP": "Contact Details (DPO/CP)", "dpoOrCp": "Contact Details (DPO/CP)",
        "imply": "Likely Consequences",
        "contactDetails": "Contact Details",
        "Risk": "High Risk to Individuals",
        "likely": "Likely to Result in Risk",
        "riskinessRightsFreedoms": "Risk to Rights and Freedoms",
        "feasible": "Feasible",
        "nominates": "Processor Nominates Controller",
        "allInfoAbout": "All Info About the Breach",
        "SupervisoryAuthority": "Supervisory Authority",
    }

    cond_humanizer = {
        "Risk": "High Risk to Individuals",
        "likely": "Likely to Cause Risk",
        "riskinessRightsFreedoms": "Risk to Rights & Freedoms",
        "Person": "Natural Person Affected",
        "nominates": "Processor Nominates Representative",
        "feasible": "Notification Feasible",
        "NOT Possible": "NOT all info available yet",
    }

    processed_tasks = []
    seen_events = set()
    current_actor = "Controller"

    for rt in raw_tasks:
        src = rt['source'].replace('GDPR:art_', 'Art. ').replace('__para_', ' Abs. ')
        src = re.sub(r'__content__list_\d+__point_([a-z])', r' lit. \1', src)

        if rt['actor'] != "System":
            current_actor = rt['actor']
        else:
            rt['actor'] = current_actor

        action = humanizer.get(rt['verb'], rt['verb'])
        # Humanize recipient
        recipient_humanizer = {
            'SupervisoryAuthority': 'Supervisory Authority',
            'Controller': 'Controller',
            'Processor': 'Processor',
        }
        recipient = recipient_humanizer.get(rt.get('recipient'), rt.get('recipient'))
        timer = rt.get('timer')
        bpmn_type = "bpmn:sendTask" if "Notify" in action or "Communicate" in rt['verb'] else "bpmn:task"

        gw_cond_str = None
        if rt['conditions']:
            translated = [cond_humanizer.get(c, humanizer.get(c, c)) for c in rt['conditions']]
            join_word = " AND " if rt['gateway_type'] == "parallel" else " OR "
            gw_cond_str = join_word.join(c for c in translated if c)

        trans_events = []
        for e in rt['events']:
            if e not in seen_events:
                seen_events.add(e)
                trans_events.append(humanizer.get(e, e))

        # Translate + deduplicate data_objects (preserve insertion order)
        data_objects_labeled = []
        seen_labels = set()
        raw_skip_labels = {
            'Describe', "Describe'", 'Contain', "Contain'", 'and', 'or', 'System', 'partOf',
            # Humanized action names must not appear as data objects
            'Notify', 'Document', 'Verify', 'Comply With Obligations', 'Provide Reason for Delay',
            # Raw verb names
            "Communicate'", "Communicate", "LetterReasonFor", "ComplyWith", "Document'", "Verify",
            'Define',
        }
        for d in rt.get('data_objects_raw', []):
            label = humanizer.get(d, d)
            if label and label not in raw_skip_labels and label not in seen_labels:
                seen_labels.add(label)
                data_objects_labeled.append(label)
        # or_alternatives are NO LONGER added as data objects — they become XOR gateways
        data_objects = data_objects_labeled


        processed_tasks.append({
            "id": generate_id("Task_"),
            "actor": rt['actor'],
            "action": action,
            "recipient": recipient,
            "source": src,
            "timer": timer,
            "bpmn_type": bpmn_type,
            "gateway_cond": gw_cond_str,
            "gateway_type": rt['gateway_type'],
            "events": trans_events,
            "data_objects": data_objects,
            "or_alternatives": [humanizer.get(a, a) for a in rt.get('or_alternatives', [])],
            "has_time_bound": rt.get('has_time_bound', False),
        })

    # Deduplicate: keep task with most data_objects for each (action, source) combo
    seen_key = {}
    for t in processed_tasks:
        key = (t['action'], t['source'])
        if key not in seen_key:
            seen_key[key] = t
        else:
            # Merge data_objects and keep richer entry
            existing = seen_key[key]
            merged_data = list(dict.fromkeys(existing['data_objects'] + t['data_objects']))
            existing['data_objects'] = merged_data
            # Keep the entry with a timer if either has one
            if t['timer'] and not existing['timer']:
                existing['timer'] = t['timer']
            # Keep the entry with events if either has them
            if t['events'] and not existing['events']:
                existing['events'] = t['events']

    processed_tasks = list(seen_key.values())

    print(f"✅ HOP 4: {len(processed_tasks)} hochdetaillierte Aufgaben generiert!")
    return processed_tasks


def generate_bpmn_master(tasks, output_file):
    if not tasks: return

    print("🏗️ Generiere BPMN 2.0 XML inkl. SendTasks, Gateways, Events & DataObjects...")
    
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
        gw_merge_id = None
        
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

        # --- XOR ALTERNATIVES (or' from DAPRECO) ---
        # Renders a proper XOR gateway with branches for each alternative
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
                alt_y = y_pos + (alt_idx * 100) - 50  # spread vertically

                # Flow from XOR split to alternative task
                bpmn_lines.append(f'    <bpmn:sequenceFlow id="{alt_flow}" name="{alt_label}" sourceRef="{xor_split_id}" targetRef="{alt_task_id}" />')
                bpmn_lines.append(f'    <bpmn:task id="{alt_task_id}" name="{alt_label}"><bpmn:incoming>{alt_flow}</bpmn:incoming></bpmn:task>')
                edges.append(f'      <bpmndi:BPMNEdge id="{alt_flow}_di" bpmnElement="{alt_flow}"><di:waypoint x="{x_xor_split+50}" y="{y_pos+25}" /><di:waypoint x="{x_alt_tasks}" y="{alt_y+30}" /></bpmndi:BPMNEdge>')
                shapes.append(f'      <bpmndi:BPMNShape id="{alt_task_id}_di" bpmnElement="{alt_task_id}"><dc:Bounds x="{x_alt_tasks}" y="{alt_y}" width="150" height="60" /></bpmndi:BPMNShape>')
                alt_end_ids.append((alt_task_id, alt_y))

            # XOR Merge
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

        # Path to Task (Yes branch or direct flow)
        flow_id = generate_id("Flow_Yes_" if has_gateway and not xor_split_id else "Flow_")
        flow_label = ' name="Yes"' if has_gateway and not xor_split_id else ''
        bpmn_lines.append(f'    <bpmn:sequenceFlow id="{flow_id}"{flow_label} sourceRef="{last_id}" targetRef="{task_id}" />')
        edges.append(f'      <bpmndi:BPMNEdge id="{flow_id}_di" bpmnElement="{flow_id}"><di:waypoint x="{last_out_x}" y="{last_out_y}" /><di:waypoint x="{x_task}" y="{y_pos+25}" /></bpmndi:BPMNEdge>')
        
        # Task label: include recipient if available
        recipient_str = f" to {task['recipient']}" if task.get('recipient') else ""
        task_label = f"{task['action']}{recipient_str}\n({task['source']})"
        
        task_tag = task['bpmn_type']
        task_block = f'    <{task_tag} id="{task_id}" name="{task_label}">'
        task_block += f'<bpmn:incoming>{flow_id}</bpmn:incoming>'
        
        # --- DATA OBJECTS (one per item, spread horizontally above the task) ---
        if task['data_objects']:
            for d_idx, doc_label in enumerate(task['data_objects']):
                data_id = generate_id("DataObj_")
                ref_id = generate_id("DataRef_")
                assoc_id = generate_id("Assoc_")
                
                task_block += f'<bpmn:dataOutputAssociation id="{assoc_id}"><bpmn:targetRef>{ref_id}</bpmn:targetRef></bpmn:dataOutputAssociation>'
                
                bpmn_lines.append(f'    <bpmn:dataObject id="{data_id}" />')
                bpmn_lines.append(f'    <bpmn:dataObjectReference id="{ref_id}" dataObjectRef="{data_id}" name="{doc_label}" />')
                
                doc_x = x_task + (d_idx * 65) - 20
                doc_y = y_pos - 100
                shapes.append(f'      <bpmndi:BPMNShape id="{ref_id}_di" bpmnElement="{ref_id}"><dc:Bounds x="{doc_x}" y="{doc_y}" width="36" height="50" /></bpmndi:BPMNShape>')
                edges.append(f'      <bpmndi:BPMNEdge id="{assoc_id}_di" bpmnElement="{assoc_id}"><di:waypoint x="{x_task+75}" y="{y_pos-15}" /><di:waypoint x="{doc_x+18}" y="{doc_y+50}" /></bpmndi:BPMNEdge>')

        task_block += f'</{task_tag}>'
        bpmn_lines.append(task_block)
            
        shapes.append(f'      <bpmndi:BPMNShape id="{task_id}_di" bpmnElement="{task_id}"><dc:Bounds x="{x_task}" y="{y_pos-15}" width="150" height="80" /></bpmndi:BPMNShape>')
        
        # --- TIMER ---

        if task['timer']:
            timer_id = generate_id("Timer_")
            bpmn_lines.append(f'    <bpmn:boundaryEvent id="{timer_id}" attachedToRef="{task_id}" cancelActivity="false"><bpmn:timerEventDefinition><bpmn:timeDuration xsi:type="bpmn:tFormalExpression">{task["timer"]}</bpmn:timeDuration></bpmn:timerEventDefinition></bpmn:boundaryEvent>')
            shapes.append(f'      <bpmndi:BPMNShape id="{timer_id}_di" bpmnElement="{timer_id}"><dc:Bounds x="{x_task+132}" y="{y_pos+47}" width="36" height="36" /></bpmndi:BPMNShape>')

        last_id = task_id
        last_out_x, last_out_y = x_task + 150, y_pos + 25

        # Merge Gateway Logic (condition split merge)
        if has_gateway:
            gw_merge_id = generate_id("Gateway_Merge_")
            flow_from_task = generate_id("Flow_")
            x_pos = x_task + 200
            
            # Flow from Task to Merge
            bpmn_lines.append(f'    <bpmn:sequenceFlow id="{flow_from_task}" sourceRef="{last_id}" targetRef="{gw_merge_id}" />')
            edges.append(f'      <bpmndi:BPMNEdge id="{flow_from_task}_di" bpmnElement="{flow_from_task}"><di:waypoint x="{last_out_x}" y="{last_out_y}" /><di:waypoint x="{x_pos}" y="{y_pos+25}" /></bpmndi:BPMNEdge>')
            
            # Flow NO: from Split Bypass to Merge
            flow_no = generate_id("Flow_No_")
            y_bypass = y_pos + 120
            bpmn_lines.append(f'    <bpmn:sequenceFlow id="{flow_no}" name="No" sourceRef="{gw_split_id}" targetRef="{gw_merge_id}" />')
            edges.append(f'      <bpmndi:BPMNEdge id="{flow_no}_di" bpmnElement="{flow_no}"><di:waypoint x="{gw_split_id}_x" y="{y_pos+50}" /><di:waypoint x="{gw_split_id}_x" y="{y_bypass}" /><di:waypoint x="{x_pos+25}" y="{y_bypass}" /><di:waypoint x="{x_pos+25}" y="{y_pos+50}" /></bpmndi:BPMNEdge>'.replace(f"{gw_split_id}_x", str(x_task-120+25)))
            
            # Merge Element
            bpmn_lines.append(f'    <{gw_tag} id="{gw_merge_id}"><bpmn:incoming>{flow_from_task}</bpmn:incoming><bpmn:incoming>{flow_no}</bpmn:incoming></{gw_tag}>')
            shapes.append(f'      <bpmndi:BPMNShape id="{gw_merge_id}_di" bpmnElement="{gw_merge_id}" isMarkerVisible="true"><dc:Bounds x="{x_pos}" y="{y_pos}" width="50" height="50" /></bpmndi:BPMNShape>')
            
            last_id = gw_merge_id
            last_out_x, last_out_y = x_pos + 50, y_pos + 25
        else:
            x_pos = x_task


    # --- END EVENT ---
    end_id, final_flow = generate_id("EndEvent_"), generate_id("Flow_")
    x_pos += 200
    bpmn_lines.append(f'    <bpmn:sequenceFlow id="{final_flow}" sourceRef="{last_id}" targetRef="{end_id}" />')
    bpmn_lines.append(f'    <bpmn:endEvent id="{end_id}" name="End"><bpmn:incoming>{final_flow}</bpmn:incoming></bpmn:endEvent>')
    
    shapes.append(f'      <bpmndi:BPMNShape id="{end_id}_di" bpmnElement="{end_id}"><dc:Bounds x="{x_pos}" y="{last_out_y-18}" width="36" height="36" /></bpmndi:BPMNShape>')
    edges.append(f'      <bpmndi:BPMNEdge id="{final_flow}_di" bpmnElement="{final_flow}"><di:waypoint x="{last_out_x}" y="{last_out_y}" /><di:waypoint x="{x_pos}" y="{last_out_y}" /></bpmndi:BPMNEdge>')

    bpmn_lines.append('  </bpmn:process>')
    
    # Diagramm rendern
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
        
    print(f"💾 Meisterwerk gespeichert unter: {output_file}")

# =========================================================
# DER MAIN BLOCK (Der Motor, der das Skript startet!)
# =========================================================
if __name__ == "__main__":
    if os.path.exists("rioKB_GDPR.xml"):
        xml_input_path = "rioKB_GDPR.xml"
    else:
        xml_input_path = "daprecokb/gdpr/rioKB_GDPR.xml"
        
    target = "art_33"
    
    if os.path.exists(xml_input_path):
        # 1. Extrahieren
        extracted_tasks = extract_gdpr_master(xml_input_path, target_article=target)
        # 2. XML Bauen
        generate_bpmn_master(extracted_tasks, f"{target}_process_final.bpmn")
    else:
        print(f"❌ FEHLER: Die Datei {xml_input_path} wurde nicht gefunden. Bitte überprüfe den Pfad.")