import re
import os
from utils import generate_id
from constants import (
    ACTOR_LIST, STRUCTURAL_NS, DEONTIC_WRAPPERS, MODAL_HELPERS,
    CONTENT_VERBS, RELATION_VERBS, EVENT_TRIGGERS, HUMANIZER,
    COND_HUMANIZER, RECIPIENT_HUMANIZER, RAW_SKIP_LABELS
)

def extract_gdpr_master(xml_path, target_article="art_33"):
    print(f"Starte MASTER-Extraktion (SendTasks, Gateways, Events) für '{target_article}'...\n")
    
    try:
        with open(xml_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Fehler beim Lesen: {e}")
        return []

    # HOP 1 & 2: Verknüpfungen auflösen
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

    # HOP 3: Pro Statement alle ruleml:Rule-Blöcke iterieren
    raw_tasks = []

    for stmt_id, human_ref in statement_ids.items():
        start_idx = content.find(f'<lrml:Statements key="{stmt_id}">')
        if start_idx == -1: continue
        end_idx = content.find('</lrml:Statements>', start_idx)
        stmt_block = content[start_idx:end_idx if end_idx != -1 else len(content)]

        rules = re.findall(r'<ruleml:Rule[^>]*>(.*?)</ruleml:Rule>', stmt_block, re.DOTALL | re.IGNORECASE)
        if not rules:
            rules = [stmt_block]

        for rule_block in rules:
            var_dict = {}
            events = []
            conditions = []
            gateway_type = "exclusive"
            has_time_bound = False
            time_bound_value = None
            or_alternatives = []
            
            task_actor = "System"
            task_recipient = None
            task_timer = None
            primary_task = None
            task_data_objects = []
            has_right = False
            
            # Map ALL variable definitions
            for atom in re.findall(r'<ruleml:Atom[^>]*>(.*?)</ruleml:Atom>', rule_block, re.DOTALL):
                rel = re.search(r'<ruleml:Rel[^>]*iri="([^:]+):([^"]+)"', atom)
                if not rel: continue
                ns, concept = rel.group(1), rel.group(2)
                var_key = re.search(r'<ruleml:Var[^>]*key="([^"]+)"', atom)
                if var_key:
                    var_dict[var_key.group(1)] = (ns, concept)
                
                fun_in_atom = re.findall(r'<ruleml:Fun[^>]*iri="([^:]+):([^"]+)"', atom)
                keyrefs_in_atom = re.findall(r'<ruleml:Var[^>]* keyref="([^"]+)"', atom)
                if concept == 'Contain' and len(keyrefs_in_atom) >= 3 and fun_in_atom:
                    content_var = keyrefs_in_atom[2]
                    fun_label = fun_in_atom[-1][1]
                    if content_var not in var_dict:
                        var_dict[content_var] = ('dapreco', fun_label)

            # --- IF-Block analysieren ---
            if_match = re.search(r'<ruleml:if>(.*?)</ruleml:if>', rule_block, re.DOTALL | re.IGNORECASE)
            if_var_concepts = {}
            if if_match:
                if_block = if_match.group(1)

                # Time bounds
                time_m = re.search(r'<ruleml:Fun\s+iri="swrlb:add"\s*/>.*?<ruleml:Ind>([^<]+)</ruleml:Ind>', if_block, re.DOTALL)
                if time_m:
                    has_time_bound = True
                    time_bound_value = time_m.group(1).strip()
                    conditions.append(f"> {time_bound_value} elapsed")

                # Structural signals
                if re.search(r'iri="rioOnto:and"', if_block): gateway_type = "parallel"
                elif re.search(r'iri="rioOnto:or"', if_block): gateway_type = "exclusive"
                if re.search(r'iri="rioOnto:not"', if_block): conditions.append("NOT Possible")
                if re.search(r'iri="rioOnto:possible"', if_block) or re.search(r"iri=\"rioOnto:possible'\"", if_block) or re.search(r'iri="rioOnto:partOf"', if_block):
                    conditions.append("Partial Information Available")

                # Domain events vs. gateway conditions
                for atom in re.findall(r'<ruleml:Atom[^>]*>(.*?)</ruleml:Atom>', if_block, re.DOTALL):
                    rel = re.search(r'<ruleml:Rel[^>]*iri="([^:]+):([^"]+)"', atom)
                    if not rel: continue
                    ns, concept = rel.group(1), rel.group(2)
                    clean_c = concept.replace("'", "")
                    
                    a_keyrefs = re.findall(r'<ruleml:Var[^>]* keyref="([^"]+)"', atom)
                    if a_keyrefs and concept not in STRUCTURAL_NS:
                        if_var_concepts[a_keyrefs[0]] = clean_c
                    if clean_c in ACTOR_LIST:
                        for kr in a_keyrefs:
                            if_var_concepts[kr] = clean_c

                    if ns in STRUCTURAL_NS or concept in ACTOR_LIST: continue
                    if clean_c in EVENT_TRIGGERS:
                        if clean_c not in events:
                            events.append(clean_c)
                    else:
                        if clean_c not in conditions:
                            conditions.append(clean_c)

            # --- THEN-Block analysis ---
            then_match = re.search(r'<ruleml:then>(.*?)</ruleml:then>', rule_block, re.DOTALL | re.IGNORECASE)
            if not then_match: continue
            then_block = then_match.group(1)

            if re.search(r'iri="rioOnto:or', then_block):
                if re.search(r'TakenToAddress', then_block): or_alternatives.append("Measures Already Taken")
                if re.search(r'ProposedToAddress', then_block): or_alternatives.append("Measures Proposed to Address")

            then_atoms = re.findall(r'<ruleml:Atom[^>]*>(.*?)</ruleml:Atom>', then_block, re.DOTALL)
            atom_by_first_ref = {}
            for atom in then_atoms:
                rel = re.search(r'<ruleml:Rel[^>]*iri="([^:]+):([^"]+)"', atom)
                if not rel: continue
                ns, concept = rel.group(1), rel.group(2)
                keyrefs = re.findall(r'<ruleml:Var[^>]*keyref="([^"]+)"', atom)
                funs = re.findall(r'<ruleml:Fun[^>]*iri="[^:]+:([^"]+)"', atom)
                if keyrefs:
                    first_ref = keyrefs[0]
                    if first_ref not in atom_by_first_ref:
                        atom_by_first_ref[first_ref] = []
                    atom_by_first_ref[first_ref].append((ns, concept, atom, keyrefs, funs))

            def resolve_eventuality(ev_var, depth=0):
                if depth > 6 or ev_var not in atom_by_first_ref:
                    return []
                results = []
                for ns, concept, atom, keyrefs, funs in atom_by_first_ref.get(ev_var, []):
                    clean = concept.replace("'", "")
                    if clean in {'RexistAtTime', 'nonDelayed', 'LetterReasonFor', 'Define', 'AbleTo', 'writtenForm', 'electronicForm'}:
                        continue
                    if clean in DEONTIC_WRAPPERS:
                        continue
                    if clean in ('and', 'or'):
                        for sv in keyrefs[1:]:
                            results.extend(resolve_eventuality(sv, depth+1))
                        continue
                    if ns in STRUCTURAL_NS:
                        continue
                    if clean in CONTENT_VERBS:
                        content_label = None
                        if funs:
                            content_label = funs[-1].replace("'", "")
                        elif len(keyrefs) >= 3:
                            cv = keyrefs[2]
                            if cv in if_var_concepts and if_var_concepts[cv] not in RELATION_VERBS and if_var_concepts[cv] not in CONTENT_VERBS and if_var_concepts[cv] not in ACTOR_LIST:
                                content_label = if_var_concepts[cv].replace("'", "")
                        if content_label and content_label not in RELATION_VERBS and content_label not in ACTOR_LIST:
                            results.append(('__content__', [content_label], None, False))
                        continue
                    if clean in RELATION_VERBS or clean in MODAL_HELPERS:
                        continue
                    
                    recipient = None
                    for f in funs:
                        if f in ACTOR_LIST:
                            recipient = f
                            break
                    if not recipient and len(keyrefs) >= 3 and keyrefs[2] in if_var_concepts and if_var_concepts[keyrefs[2]] in ACTOR_LIST:
                        recipient = if_var_concepts[keyrefs[2]]
                    results.append((clean, [], recipient, False))
                return results

            # --- Find Deontic Wrapper ---
            deontic_action_var = None
            for atom in then_atoms:
                rel = re.search(r'<ruleml:Rel[^>]*iri="([^:]+):([^"]+)"', atom)
                if not rel: continue
                concept = rel.group(2)
                if concept not in DEONTIC_WRAPPERS: continue
                keyrefs = re.findall(r'<ruleml:Var[^>]*keyref="([^"]+)"', atom)
                funs = re.findall(r'<ruleml:Fun[^>]*iri="[^:]+:([^"]+)"', atom)
                if not keyrefs: continue

                if concept in {'Obliged', 'Permitted', 'Prohibited'}:
                    deontic_action_var = keyrefs[0]
                    if len(keyrefs) > 2:
                        av = keyrefs[2]
                        if av in if_var_concepts and if_var_concepts[av] in ACTOR_LIST:
                            task_actor = if_var_concepts[av]
                    for f in funs:
                        if f in ACTOR_LIST:
                            task_actor = f; break
                    if concept in {'Permitted', 'Right'}:
                        has_right = True
                elif concept == 'Right':
                    has_right = True
                    if len(keyrefs) > 1:
                        deontic_action_var = keyrefs[1]
                    if keyrefs[0] in if_var_concepts and if_var_concepts[keyrefs[0]] in ACTOR_LIST:
                        task_actor = if_var_concepts[keyrefs[0]]
                break

            if deontic_action_var:
                for ns, concept, atom, keyrefs, funs in atom_by_first_ref.get(deontic_action_var, []):
                    if concept.replace("'", "") == 'AbleTo' and len(keyrefs) >= 3:
                        deontic_action_var = keyrefs[2]
                        for f in funs:
                            if f in ACTOR_LIST:
                                task_recipient = f; break
                        break

            all_fun_iris = re.findall(r'<ruleml:Fun[^>]*iri="[^"]*:([^"]+)"', rule_block)
            if not task_recipient:
                for fun_name in all_fun_iris:
                    if fun_name in ACTOR_LIST:
                        task_recipient = fun_name; break

            resolved_actions = []
            content_data_objects = []
            if deontic_action_var:
                resolved = resolve_eventuality(deontic_action_var)
                for concept, data_objs, recipient, is_rgt in resolved:
                    if concept == '__content__':
                        content_data_objects.extend(data_objs)
                    else:
                        resolved_actions.append((concept, recipient, is_rgt))
            
            all_then_contain = []
            for atom in then_atoms:
                rel = re.search(r'<ruleml:Rel[^>]*iri="([^:]+):([^"]+)"', atom)
                if not rel: continue
                concept = rel.group(2).replace("'", "")
                if concept not in CONTENT_VERBS: continue
                keyrefs = re.findall(r'<ruleml:Var[^>]*keyref="([^"]+)"', atom)
                funs = re.findall(r'<ruleml:Fun[^>]*iri="[^:]+:([^"]+)"', atom)
                content_label = None
                if funs:
                    content_label = funs[-1].replace("'", "")
                elif len(keyrefs) >= 3:
                    cv = keyrefs[2]
                    if cv in if_var_concepts and if_var_concepts[cv] not in RELATION_VERBS and if_var_concepts[cv] not in CONTENT_VERBS and if_var_concepts[cv] not in ACTOR_LIST:
                        content_label = if_var_concepts[cv].replace("'", "")
                if content_label and content_label not in RELATION_VERBS and content_label not in ACTOR_LIST:
                    all_then_contain.append(content_label)

            if re.search(r'dapreco:writtenForm|dapreco:electronicForm', then_block):
                if re.search(r'writtenForm', then_block): all_then_contain.append('Written Form Required')
                if re.search(r'electronicForm', then_block): all_then_contain.append('Electronic Form')

            for lbl in content_data_objects + all_then_contain:
                if lbl not in task_data_objects: task_data_objects.append(lbl)

            if resolved_actions:
                primary_task = resolved_actions[0][0].replace("'", "")
                r_recipient, r_right = resolved_actions[0][1], resolved_actions[0][2]
                if r_recipient and not task_recipient: task_recipient = r_recipient
                if r_right: has_right = True
            
            if primary_task: primary_task = primary_task.replace("'", "")

            is_content_rule = not primary_task and bool(task_data_objects)
            if is_content_rule:
                article_key = re.search(r'GDPR:(art_\d+)', human_ref)
                article_prefix = article_key.group(1) if article_key else None
                for existing in raw_tasks:
                    ex_article = re.search(r'art_\d+', existing['source'])
                    ex_article_key = ex_article.group(0) if ex_article else None
                    if ex_article_key == article_prefix:
                        for d in task_data_objects:
                            if d not in existing['data_objects_raw']: existing['data_objects_raw'].append(d)
                        if or_alternatives:
                            existing['or_alternatives'].extend([a for a in or_alternatives if a not in existing['or_alternatives']])
                        break
                continue

            if primary_task:
                raw_tasks.append({
                    "actor": task_actor,
                    "verb": primary_task,
                    "data_objects_raw": task_data_objects,
                    "or_alternatives": or_alternatives,
                    "timer": task_timer,
                    "source": human_ref,
                    "conditions": conditions,
                    "events": [e.replace("'", "") for e in events],
                    "gateway_type": gateway_type,
                    "has_time_bound": has_time_bound,
                    "time_bound_value": time_bound_value,
                    "recipient": task_recipient,
                    "has_right": has_right
                })

    # HOP 4: Humanizer & Verschmelzung
    processed_tasks = []
    seen_events = set()
    current_actor = "Controller"

    for rt in raw_tasks:
        src = rt['source'].replace('GDPR:art_', 'Art. ').replace('__para_', ' Abs. ')
        src = re.sub(r'__content__list_\d+__point_([a-z])', r' lit. \1', src)

        if rt['actor'] != "System": current_actor = rt['actor']
        else: rt['actor'] = current_actor

        action = HUMANIZER.get(rt['verb'], rt['verb'])
        if rt.get('has_right'): action = f"Can {action}"
            
        recipient = RECIPIENT_HUMANIZER.get(rt.get('recipient'), rt.get('recipient'))
        timer = rt.get('timer')
        bpmn_type = "bpmn:sendTask" if "Notify" in action or "Communicate" in rt['verb'] else "bpmn:task"

        gw_cond_str = None
        if rt['conditions']:
            translated = [COND_HUMANIZER.get(c, HUMANIZER.get(c, c)) for c in rt['conditions']]
            join_word = " AND " if rt['gateway_type'] == "parallel" else " OR "
            gw_cond_str = join_word.join(c for c in translated if c)

        trans_events = []
        for e in rt['events']:
            if e not in seen_events:
                seen_events.add(e)
                trans_events.append(HUMANIZER.get(e, e))

        data_objects_labeled = []
        seen_labels = set()
        for d in rt.get('data_objects_raw', []):
            label = HUMANIZER.get(d, d)
            if label and label not in RAW_SKIP_LABELS and label not in seen_labels:
                seen_labels.add(label)
                data_objects_labeled.append(label)

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
            "data_objects": data_objects_labeled,
            "or_alternatives": [HUMANIZER.get(a, a) for a in rt.get('or_alternatives', [])],
            "has_time_bound": rt.get('has_time_bound', False),
        })

    # Deduplicate
    seen_key = {}
    for t in processed_tasks:
        key = (t['action'], t['source'])
        if key not in seen_key:
            seen_key[key] = t
        else:
            existing = seen_key[key]
            existing['data_objects'] = list(dict.fromkeys(existing['data_objects'] + t['data_objects']))
            if t['timer'] and not existing['timer']: existing['timer'] = t['timer']
            if t['events'] and not existing['events']: existing['events'] = t['events']

    processed_tasks = list(seen_key.values())
    print(f"HOP 4: {len(processed_tasks)} hochdetaillierte Aufgaben generiert!")
    return processed_tasks
