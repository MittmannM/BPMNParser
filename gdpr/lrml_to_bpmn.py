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

    # NEW: We no longer need static lists. We use the namespace approach.
    actor_list = {'Controller', 'Processor', 'SupervisoryAuthority', 'DataSubject', 'MemberState'}
    STRUCTURAL_NS = {'rioOnto', 'swrlb', 'rdfs', 'ruleml'}
    DEONTIC_WRAPPERS = {'Obliged', 'Permitted', 'Right', 'Prohibited'}
    # MODAL_HELPERS: domain verbs that qualify another verb but are NOT primary tasks
    MODAL_HELPERS = {'AbleTo', 'nonDelayed', 'possible', 'responsible', 'feasible', 'reasonable'}
    # CONTENT_VERBS: verbs that describe WHAT a document/record must contain — never primary tasks
    # These become DataObjects attached to the enclosing obligation's primary task
    CONTENT_VERBS = {'Contain', 'Describe', 'CategoryOf', 'allInfoAbout', 'imply'}
    # RELATION_VERBS: structural relations in the ontology — skip as data objects (not user-facing)
    RELATION_VERBS = {'isRepresentedBy', 'ResponsibleFor', 'Transmit', 'nominates',
                      'isBasedOn', 'RelatedTo', 'partOf', 'cause', 'imply', 'Hold',
                      'Execute', 'Request', 'LegalRequirement', 'Marketing', 'publicPowers',
                      'Purpose', 'PersonalDataProcessing'}
    # True process-triggering events (initiate the process / are start conditions)
    EVENT_TRIGGERS = {'DataBreach', 'AwareOf', 'Request', 'PersonalDataProcessing',
                      'Complaint', 'ReceiveFrom', 'Execute', 'Lodge'}

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
            
            # Map ALL variable definitions in the rule block (IF + THEN)
            for atom in re.findall(r'<ruleml:Atom[^>]*>(.*?)</ruleml:Atom>', rule_block, re.DOTALL):
                rel = re.search(r'<ruleml:Rel[^>]*iri="([^:]+):([^"]+)"', atom)
                if not rel: continue
                ns, concept = rel.group(1), rel.group(2)
                # Map key= variables
                var_key = re.search(r'<ruleml:Var[^>]*key="([^"]+)"', atom)
                if var_key:
                    var_dict[var_key.group(1)] = (ns, concept)
                # Also capture Fun tags within atoms: they are named constants (e.g. dapreco:contactDetails)
                # and help us label the 3rd argument of Contain atoms
                fun_in_atom = re.findall(r'<ruleml:Fun[^>]*iri="([^:]+):([^"]+)"', atom)
                keyrefs_in_atom = re.findall(r'<ruleml:Var[^>]* keyref="([^"]+)"', atom)
                # If this is a Contain(:event, :record, :content_var) atom,
                # the 3rd keyref's concept tells us what is contained.
                # We store Fun tags within the atom as content labels for the content_var.
                if concept == 'Contain' and len(keyrefs_in_atom) >= 3 and fun_in_atom:
                    content_var = keyrefs_in_atom[2]
                    # Fun tags name the content — use last segment of their IRI
                    fun_label = fun_in_atom[-1][1]  # (ns, concept) -> concept
                    if content_var not in var_dict:
                        var_dict[content_var] = ('dapreco', fun_label)

            # ---- IF-Block analysieren ----
            if_match = re.search(r'<ruleml:if>(.*?)</ruleml:if>', rule_block, re.DOTALL | re.IGNORECASE)
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

                # Domain events vs. gateway conditions — separate by semantic role
                for atom in re.findall(r'<ruleml:Atom[^>]*>(.*?)</ruleml:Atom>', if_block, re.DOTALL):
                    rel = re.search(r'<ruleml:Rel[^>]*iri="([^:]+):([^"]+)"', atom)
                    if not rel: continue
                    ns, concept = rel.group(1), rel.group(2)
                    clean_c = concept.replace("'", "")
                    if ns in STRUCTURAL_NS or concept in actor_list: continue
                    if clean_c in EVENT_TRIGGERS:
                        # True process-initiating event
                        if clean_c not in events:
                            events.append(clean_c)
                    else:
                        # Context/condition — goes to Gateway label, not as intermediate event
                        if clean_c not in conditions:
                            conditions.append(clean_c)

            # ---- THEN-Block: Reified I/O Logic analysis ----
            # PAPER INSIGHT: All atoms use keyref= only. The reification pattern is:
            #   Obliged(:eo, :t, :actor)  <- deontic wrapper; :eo is the obligation eventuality
            #   Action'(:eo, args...)      <- atom where keyrefs[0] == :eo; this IS the primary action
            #   and'(:eo, :e1, :e2)        <- if :eo is a compound; decompose into :e1, :e2 sub-events
            #   or'(:eo, :e1, :e2)         <- XOR alternative sub-events

            then_match = re.search(r'<ruleml:then>(.*?)</ruleml:then>', rule_block, re.DOTALL | re.IGNORECASE)
            if not then_match: continue
            then_block = then_match.group(1)

            if re.search(r'iri="rioOnto:or', then_block):
                if re.search(r'TakenToAddress', then_block): or_alternatives.append("Measures Already Taken")
                if re.search(r'ProposedToAddress', then_block): or_alternatives.append("Measures Proposed to Address")

            # Build an atom lookup: first_keyref -> (concept, full_atom)  
            # This enables O(1) traversal of the eventuality graph
            then_atoms = re.findall(r'<ruleml:Atom[^>]*>(.*?)</ruleml:Atom>', then_block, re.DOTALL)
            atom_by_first_ref = {}  # first_keyref -> list of (ns, concept, atom, all_keyrefs, funs)
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
            
            # Structures namespace concepts that are not domain actions
            STRUCTURAL_THEN = STRUCTURAL_NS | {'nonDelayed', 'LetterReasonFor', 'Define',
                                                'RexistAtTime', 'AbleTo', 'writtenForm', 'electronicForm'}
            
            def resolve_eventuality(ev_var, depth=0):
                """Recursively resolve an eventuality variable to action tuples.
                Paper insight: and'(rioOnto)/or'(rioOnto) MUST be traversed before namespace filter!
                Returns list of (concept, data_objs, recipient, has_right)."""
                if depth > 6 or ev_var not in atom_by_first_ref:
                    return []
                results = []
                for ns, concept, atom, keyrefs, funs in atom_by_first_ref.get(ev_var, []):
                    clean = concept.replace("'", "")

                    # 1. Explicit skips that are never informative
                    if clean in {'RexistAtTime', 'nonDelayed', 'LetterReasonFor',
                                 'Define', 'AbleTo', 'writtenForm', 'electronicForm'}:
                        continue
                    if clean in DEONTIC_WRAPPERS:
                        continue

                    # 2. and/or decomposition — MUST happen before namespace check!
                    # (and', or' live in rioOnto but carry the full obligation structure)
                    if clean in ('and', 'or'):
                        for sv in keyrefs[1:]:  # keyrefs[0] is the compound var itself
                            results.extend(resolve_eventuality(sv, depth+1))
                        continue

                    # 3. Now namespace filter for everything else
                    if ns in STRUCTURAL_NS:
                        continue

                    # 4. Content verbs: extract what they contain
                    if clean in CONTENT_VERBS:
                        content_label = None
                        if funs:
                            content_label = funs[-1].replace("'", "")
                        elif len(keyrefs) >= 3:
                            cv = keyrefs[2]
                            if cv in if_var_concepts \
                               and if_var_concepts[cv] not in RELATION_VERBS \
                               and if_var_concepts[cv] not in CONTENT_VERBS \
                               and if_var_concepts[cv] not in actor_list:
                                content_label = if_var_concepts[cv].replace("'", "")
                        if content_label and content_label not in RELATION_VERBS \
                           and content_label not in actor_list:
                            results.append(('__content__', [content_label], None, False))
                        continue

                    # 5. Relation/modal verbs: skip
                    if clean in RELATION_VERBS or clean in MODAL_HELPERS:
                        continue

                    # 6. This IS the primary action
                    recipient = None
                    for f in funs:
                        if f in actor_list:
                            recipient = f
                            break
                    if not recipient and len(keyrefs) >= 3 \
                       and keyrefs[2] in if_var_concepts \
                       and if_var_concepts[keyrefs[2]] in actor_list:
                        recipient = if_var_concepts[keyrefs[2]]
                    results.append((clean, [], recipient, False))
                return results


            # --- Build IF-block variable concept map ---
            # Must be built BEFORE resolve_eventuality is called
            if_var_concepts = {}  # var_keyref -> concept_name
            if if_match:
                for atom in re.findall(r'<ruleml:Atom[^>]*>(.*?)</ruleml:Atom>', if_match.group(1), re.DOTALL):
                    rel = re.search(r'<ruleml:Rel[^>]*iri="([^:]+):([^"]+)"', atom)
                    if not rel: continue
                    a_concept = rel.group(2).replace("'", "")
                    a_keyrefs = re.findall(r'<ruleml:Var[^>]* keyref="([^"]+)"', atom)
                    if a_keyrefs and a_concept not in STRUCTURAL_NS:
                        if_var_concepts[a_keyrefs[0]] = a_concept
                    # Map ALL args to actor type when concept IS an actor class
                    if a_concept in actor_list:
                        for kr in a_keyrefs:
                            if_var_concepts[kr] = a_concept

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
                    # Actor: 3rd keyref looked up in IF-block, or direct Fun tag
                    if len(keyrefs) > 2:
                        av = keyrefs[2]
                        if av in if_var_concepts and if_var_concepts[av] in actor_list:
                            task_actor = if_var_concepts[av]
                    for f in funs:
                        if f in actor_list:
                            task_actor = f; break
                    if concept in {'Permitted', 'Right'}:
                        has_right = True
                elif concept == 'Right':
                    has_right = True
                    if len(keyrefs) > 1:
                        deontic_action_var = keyrefs[1]
                    if keyrefs[0] in if_var_concepts and if_var_concepts[keyrefs[0]] in actor_list:
                        task_actor = if_var_concepts[keyrefs[0]]
                break  # Only first deontic wrapper per rule


            # --- AbleTo modal redirect: Obliged(:eat) AbleTo(:eat, :actor, :sub_event) ---
            if deontic_action_var:
                for ns, concept, atom, keyrefs, funs in atom_by_first_ref.get(deontic_action_var, []):
                    if concept.replace("'", "") == 'AbleTo' and len(keyrefs) >= 3:
                        deontic_action_var = keyrefs[2]
                        for f in funs:
                            if f in actor_list:
                                task_recipient = f
                                break
                        break

            # --- Recipient from Fun tags (global scan) ---
            all_fun_iris = re.findall(r'<ruleml:Fun[^>]*iri="[^"]*:([^"]+)"', rule_block)
            if not task_recipient:
                for fun_name in all_fun_iris:
                    if fun_name in actor_list:
                        task_recipient = fun_name
                        break

            # --- Resolve the obligation via eventuality graph traversal ---
            resolved_actions = []
            content_data_objects = []
            
            if deontic_action_var:
                resolved = resolve_eventuality(deontic_action_var)
                for concept, data_objs, recipient, is_rgt in resolved:
                    if concept == '__content__':
                        content_data_objects.extend(data_objs)
                    else:
                        resolved_actions.append((concept, recipient, is_rgt))
            
            # --- Also extract Contain/content atoms from entire THEN block ---
            # These appear in THEN blocks that are pure content rules (no primary)
            # OR alongside the primary action
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
                    if cv in if_var_concepts and if_var_concepts[cv] not in RELATION_VERBS \
                       and if_var_concepts[cv] not in CONTENT_VERBS \
                       and if_var_concepts[cv] not in actor_list:
                        content_label = if_var_concepts[cv].replace("'", "")
                if content_label and content_label not in RELATION_VERBS \
                   and content_label not in actor_list:
                    all_then_contain.append(content_label)

            # --- writtenForm / electronicForm ---
            if re.search(r'dapreco:writtenForm|dapreco:electronicForm', then_block):
                if re.search(r'writtenForm', then_block):
                    all_then_contain.append('Written Form Required')
                if re.search(r'electronicForm', then_block):
                    all_then_contain.append('Electronic Form')

            # Deduplicate content
            for lbl in content_data_objects + all_then_contain:
                if lbl not in task_data_objects:
                    task_data_objects.append(lbl)

            # Assign primary task from resolved actions
            if resolved_actions:
                primary_task = resolved_actions[0][0].replace("'", "")
                r_recipient, r_right = resolved_actions[0][1], resolved_actions[0][2]
                if r_recipient and not task_recipient:
                    task_recipient = r_recipient
                if r_right:
                    has_right = True
            elif content_data_objects or all_then_contain:
                primary_task = None  # Pure content rule
            else:
                primary_task = None

            if primary_task:
                primary_task = primary_task.replace("'", "")

            
            # Content Rule Association
            is_content_rule = not primary_task and bool(task_data_objects)
            if is_content_rule:
                # Append the data objects to the FIRST backwards matching task for this article.
                # Content rules should attach to existing generated tasks.
                article_key = re.search(r'GDPR:(art_\d+)', human_ref)
                article_prefix = article_key.group(1) if article_key else None
                for existing in raw_tasks: # Forward search since 33(3) attaches to 33(1)
                    ex_article = re.search(r'art_\d+', existing['source'])
                    ex_article_key = ex_article.group(0) if ex_article else None
                    if ex_article_key == article_prefix:
                        for d in task_data_objects:
                            if d not in existing['data_objects_raw']:
                                existing['data_objects_raw'].append(d)
                        if or_alternatives:
                            existing['or_alternatives'].extend([a for a in or_alternatives if a not in existing['or_alternatives']])
                        # We can just attach to the first task found for this article for simplicity
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
        "Delete": "Erase Personal Data",
        "Rectify": "Rectify Data",
        "Access": "Provide Data Access",
        "Lodge": "Lodge Complaint",
        "ReceiveFrom": "Receive Communication",
        "Charge": "Charge Fee",
        "WithdrawConsent": "Withdraw Consent",
        "Register": "Maintain Processing Record",
        "WriteIn": "Record Processing Activity",
        "Implement": "Implement Measure",
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
        if rt.get('has_right'):
            action = f"Can {action}"
            
        # Humanize recipient
        recipient_humanizer = {
            'SupervisoryAuthority': 'Supervisory Authority',
            'Controller': 'Controller',
            'Processor': 'Processor',
            'DataSubject': 'Data Subject',
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