"""
parser_v2.py — Structural LegalRuleML → BPMN extractor.

Replaces the regex-based parser.py with a proper xml.etree.ElementTree parse
that follows the actual encoding of the DAPRECO Knowledge Base:

  • No CONTEXT_PREDICATES / RELATION_VERBS blacklists.
  • Statement type determined by deontic Rel in THEN (not by XML tag).
  • Temporal ordering via After :t2 :t1 atoms.
  • Actor detection via variable registry built from IF-block actor atoms.
  • Conditions = every IF-block domain predicate that is not structural,
    not an actor declaration, and not a background type assertion.

The output dict format is identical to parser.py so generator.py is unchanged.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from utils import generate_id
from constants import HUMANIZER, COND_HUMANIZER, RECIPIENT_HUMANIZER, RAW_SKIP_LABELS

# ── Namespace URIs ─────────────────────────────────────────────────────────────
LRML   = 'http://docs.oasis-open.org/legalruleml/ns/v1.0/'
RULEML = 'http://ruleml.org/spec'

def _t(ns: str, local: str) -> str:
    return f'{{{ns}}}{local}'

# Shorthand tag builders
L = lambda local: _t(LRML,   local)
R = lambda local: _t(RULEML, local)

# ── Domain classification ──────────────────────────────────────────────────────

# Full IRI strings that are always structural (never tasks or conditions)
STRUCTURAL_IRIS: set[str] = {
    'rioOnto:RexistAtTime',
    'rioOnto:and', "rioOnto:and'",
    'rioOnto:or',  "rioOnto:or'",
    'rioOnto:not', "rioOnto:not'",
    'rioOnto:AbleTo',
    'rioOnto:possible', "rioOnto:possible'",
    'rioOnto:partOf',
    'rioOnto:cause',
    'rioOnto:nonDelayed',
    'swrlb:add', 'swrlb:subtract',
    'After', 'Before', 'Equal',
}

# Actor role IRIs — atoms whose Rel matches these are actor declarations
ACTOR_IRIS: set[str] = {
    'prOnto:Controller', 'prOnto:Processor',
    'prOnto:DataSubject', 'prOnto:SupervisoryAuthority',
    'prOnto:MemberState',
}

# Actor concept names (without namespace prefix, without prime)
ACTOR_CONCEPTS: set[str] = {
    'Controller', 'Processor', 'DataSubject', 'SupervisoryAuthority', 'MemberState',
}

# Deontic wrapper IRIs
DEONTIC_IRIS: set[str] = {
    'rioOnto:Obliged', 'rioOnto:Permitted', 'rioOnto:Right', 'rioOnto:Prohibited',
}

# Background type-assertion concepts (non-reified, classify a var as a type)
TYPE_ASSERTION_CONCEPTS: set[str] = {
    'PersonalData', 'PersonalDataRecord', 'PersonalDataProcessing',
}

# Form-marker IRIs that encode data-object requirements
FORM_IRIS: set[str] = {
    'dapreco:writtenForm', 'dapreco:electronicForm',
    "dapreco:writtenForm'", "dapreco:electronicForm'",
}
FORM_LABELS: dict[str, str] = {
    'writtenForm':  'Written Form Required',
    'electronicForm': 'Electronic Form Required',
}

# Content-verb concepts (Contain/Describe chains → data objects)
CONTENT_CONCEPTS: set[str] = {'Contain', 'Describe', 'CategoryOf', 'allInfoAbout'}


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class VarRecord:
    """Tracks what we know about a named variable from the IF block."""
    key:     str
    concept: str  = ''   # e.g. 'Controller', 'HasBeenDamaged'
    ns:      str  = ''   # e.g. 'prOnto', 'dapreco'
    is_actor: bool = False


@dataclass
class RawTask:
    actor:        str
    deontic:      str            # 'Obliged' | 'Permitted' | 'Right' | 'Prohibited'
    verb:         str            # primary action concept
    data_objects: list[str]      = field(default_factory=list)
    conditions:   list[str]      = field(default_factory=list)
    gateway_type: str            = 'exclusive'
    recipient:    Optional[str]  = None
    has_right:    bool           = False
    or_alts:      list[str]      = field(default_factory=list)
    events:       list[str]      = field(default_factory=list)
    time_t1:      Optional[str]  = None   # IF time-context var
    time_t2:      Optional[str]  = None   # THEN obligation time var
    source:       str            = ''


# ── Helpers ────────────────────────────────────────────────────────────────────

def _iri_parts(iri: str) -> tuple[str, str]:
    """Split 'ns:concept' → ('ns', 'concept')."""
    if ':' in iri:
        ns, concept = iri.split(':', 1)
        return ns, concept
    return '', iri


def _atom_iri(atom: ET.Element) -> str:
    rel = atom.find(R('Rel'))
    return rel.get('iri', '') if rel is not None else ''


def _atom_keyrefs(atom: ET.Element) -> list[str]:
    return [v.get('keyref') for v in atom.iter(R('Var')) if v.get('keyref')]


def _atom_keys(atom: ET.Element) -> list[str]:
    return [v.get('key') for v in atom.iter(R('Var')) if v.get('key')]


def _atom_funs(atom: ET.Element) -> list[str]:
    return [f.get('iri', '') for f in atom.iter(R('Fun'))]


def _humanize(concept: str) -> str:
    clean = concept.replace("'", "")
    return HUMANIZER.get(clean, HUMANIZER.get(concept, clean))


def _humanize_cond(concept: str) -> str:
    clean = concept.replace("'", "")
    return COND_HUMANIZER.get(clean, HUMANIZER.get(clean, clean))


# ── Index builder (whole-file, one-time) ──────────────────────────────────────

class LRMLIndex:
    """Pre-parsed index of the entire XML so per-article extraction is fast."""

    def __init__(self, xml_path: str):
        print(f"  [v2] Parsing XML into index…")
        self.tree = ET.parse(xml_path)
        self.root = self.tree.getroot()

        # stmt_key → Statements element
        self.statements: dict[str, ET.Element] = {}
        for stmt in self.root.iter(L('Statements')):
            key = stmt.get('key')
            if key:
                self.statements[key] = stmt

        # refersTo → refID  (legal reference)
        self.legal_refs: dict[str, str] = {}
        for lr in self.root.iter(L('LegalReference')):
            rt = lr.get('refersTo')
            ri = lr.get('refID')
            if rt and ri:
                self.legal_refs[rt] = ri

        # source_keyref → set of target_keyrefs  (association)
        self.associations: dict[str, str] = {}
        for assoc in self.root.iter(L('Association')):
            src_el = assoc.find(L('appliesSource'))
            tgt_el = assoc.find(L('toTarget'))
            if src_el is None or tgt_el is None:
                continue
            src = src_el.get('keyref', '').lstrip('#')
            tgt = tgt_el.get('keyref', '').lstrip('#')
            if src and tgt:
                self.associations[src] = tgt

        print(f"  [v2] Index built: {len(self.statements)} statements, "
              f"{len(self.legal_refs)} legal refs, {len(self.associations)} associations")


# ── Core rule parser ───────────────────────────────────────────────────────────

def _parse_rule(rule: ET.Element, source_ref: str) -> Optional[RawTask]:
    """
    Parse one <ruleml:Rule> element into a RawTask, or return None if the
    rule has no deontic wrapper (= constitutive/entailment, not a task rule).
    """
    if_el   = rule.find(R('if'))
    then_el = rule.find(R('then'))
    if then_el is None:
        return None

    # ── THEN: find deontic wrapper ─────────────────────────────────────────
    deontic_atom = None
    deontic_iri  = ''
    for atom in then_el.iter(R('Atom')):
        iri = _atom_iri(atom)
        if iri in DEONTIC_IRIS:
            deontic_atom = atom
            deontic_iri  = iri
            break
    if deontic_atom is None:
        return None   # no deontic → constitutive/entailment rule, skip

    _, deontic_concept = _iri_parts(deontic_iri)
    keyrefs_d = _atom_keyrefs(deontic_atom)
    funs_d    = _atom_funs(deontic_atom)

    # Deontic signature: Obliged(:action_var, :time_var, :actor_var)
    action_var = keyrefs_d[0] if len(keyrefs_d) > 0 else None
    time_t2    = keyrefs_d[1] if len(keyrefs_d) > 1 else None
    actor_var  = keyrefs_d[2] if len(keyrefs_d) > 2 else None

    has_right = deontic_concept in ('Permitted', 'Right')

    # ── IF: build variable registry & collect conditions ──────────────────
    var_registry: dict[str, VarRecord] = {}   # key_str → VarRecord
    conditions:   list[str]            = []
    time_t1:      Optional[str]        = None
    gateway_type  = 'exclusive'        # default; 'parallel' if rioOnto:and in IF

    if if_el is not None:
        # First pass: register all Var key= definitions
        for var in if_el.iter(R('Var')):
            k = var.get('key')
            if k:
                var_registry[k] = VarRecord(key=k)

        # Second pass: classify each Atom (skipping those inside Naf)
        for atom in _iter_atoms_no_naf(if_el):
            iri  = _atom_iri(atom)
            ns, concept = _iri_parts(iri)
            clean_c = concept.replace("'", "")

            # Time anchors
            if iri == 'rioOnto:RexistAtTime':
                refs = _atom_keyrefs(atom)
                keys = _atom_keys(atom)
                if keys:   # t1 defined here
                    time_t1 = keys[0]
                continue

            # Gateway-type signals
            if iri in ('rioOnto:and', "rioOnto:and'"):
                gateway_type = 'parallel'
                # Register all newly keyed vars introduced here
                for v in atom.iter(R('Var')):
                    k = v.get('key')
                    if k and k not in var_registry:
                        var_registry[k] = VarRecord(key=k)
                continue
            if iri in ('rioOnto:or', "rioOnto:or'"):
                gateway_type = 'exclusive'
                continue

            # Skip all other structural IRIs
            if iri in STRUCTURAL_IRIS or ns in ('rioOnto', 'swrlb', 'rdfs', 'ruleml'):
                continue

            # Actor declarations → register var → actor
            if iri in ACTOR_IRIS or clean_c in ACTOR_CONCEPTS:
                for v in atom.iter(R('Var')):
                    k = v.get('key') or v.get('keyref')
                    if k:
                        if k not in var_registry:
                            var_registry[k] = VarRecord(key=k)
                        var_registry[k].concept  = clean_c
                        var_registry[k].ns       = ns
                        var_registry[k].is_actor = True
                continue

            # Background type assertions → skip
            if clean_c in TYPE_ASSERTION_CONCEPTS:
                continue

            # Everything else → meaningful condition
            if clean_c and clean_c not in conditions:
                conditions.append(clean_c)

    # ── IF: detect NOT Possible / time-bound ──────────────────────────────
    if if_el is not None:
        raw_if = ET.tostring(if_el, encoding='unicode')
        if 'rioOnto:not' in raw_if:
            if 'NOT Possible' not in conditions:
                conditions.insert(0, 'NOT Possible')
        if 'rioOnto:possible' in raw_if:
            if 'Partial Information Available' not in conditions:
                conditions.append('Partial Information Available')
        # Time bound from swrlb:add
        time_m = re.search(
            r'<[^>]+Fun[^>]+iri="swrlb:add"[^/]*/?>.*?<[^>]+Ind[^>]*>([^<]+)</[^>]+Ind>',
            raw_if, re.DOTALL
        )
        if time_m:
            conditions.append(f'> {time_m.group(1).strip()} elapsed')

    # ── Resolve actor from registry ────────────────────────────────────────
    actor = 'System'
    if actor_var and actor_var in var_registry and var_registry[actor_var].is_actor:
        actor = var_registry[actor_var].concept
    elif funs_d:
        for f_iri in funs_d:
            _, fc = _iri_parts(f_iri)
            if fc in ACTOR_CONCEPTS:
                actor = fc
                break

    # For Right deontic: actor is first keyref (not third)
    if deontic_concept == 'Right':
        right_actor_var = keyrefs_d[0] if keyrefs_d else None
        action_var      = keyrefs_d[1] if len(keyrefs_d) > 1 else None
        if right_actor_var and right_actor_var in var_registry and var_registry[right_actor_var].is_actor:
            actor = var_registry[right_actor_var].concept

    # ── THEN: find primary task via action_var ────────────────────────────
    then_atoms = list(then_el.iter(R('Atom')))

    # Build atom_by_first_keyref index
    atom_by_first_ref: dict[str, list[ET.Element]] = defaultdict(list)
    for atom in then_atoms:
        refs = _atom_keyrefs(atom)
        if refs:
            atom_by_first_ref[refs[0]].append(atom)

    # AbleTo unwrapping: if action_var points to AbleTo(:t, :actor, :real_action_var)
    if action_var and action_var in atom_by_first_ref:
        for atom in atom_by_first_ref[action_var]:
            iri = _atom_iri(atom)
            _, c = _iri_parts(iri)
            if c.replace("'", "") == 'AbleTo':
                refs = _atom_keyrefs(atom)
                if len(refs) >= 3:
                    action_var = refs[2]
                break

    # Find primary task atom
    primary_verb = ''
    recipient    = None
    data_objects: list[str] = []
    or_alts:      list[str] = []
    events:       list[str] = []

    if action_var and action_var in atom_by_first_ref:
        for atom in atom_by_first_ref[action_var]:
            iri = _atom_iri(atom)
            ns_a, concept_a = _iri_parts(iri)
            clean_a = concept_a.replace("'", "")

            if iri in STRUCTURAL_IRIS: continue
            if iri in DEONTIC_IRIS: continue
            if clean_a in ('AbleTo', 'nonDelayed', 'RexistAtTime', 'writtenForm', 'electronicForm'):
                continue
            if iri in FORM_IRIS:
                concept_key = clean_a
                label = FORM_LABELS.get(concept_key, concept_key)
                if label not in data_objects:
                    data_objects.append(label)
                continue
            if clean_a in ACTOR_CONCEPTS: continue

            # Handle and/or composition: follow sub-vars
            if clean_a in ('and', 'or'):
                sub_vars = _atom_keyrefs(atom)[1:]
                for sv in sub_vars:
                    if sv in atom_by_first_ref:
                        for sub_atom in atom_by_first_ref[sv]:
                            sub_iri = _atom_iri(sub_atom)
                            _, sub_c = _iri_parts(sub_iri)
                            sub_clean = sub_c.replace("'", "")
                            if sub_iri in STRUCTURAL_IRIS or sub_clean in ACTOR_CONCEPTS:
                                continue
                            if not primary_verb:
                                primary_verb = sub_clean
                continue

            # Found primary verb
            if not primary_verb:
                primary_verb = clean_a
                # Detect recipient from fun or further keyrefs
                funs_a = _atom_funs(atom)
                for f_iri in funs_a:
                    _, fc = _iri_parts(f_iri)
                    if fc in ACTOR_CONCEPTS:
                        recipient = fc
                        break

    # ── THEN: scan all atoms for data objects (form + content) ────────────
    for atom in then_atoms:
        iri = _atom_iri(atom)
        ns_a, concept_a = _iri_parts(iri)
        clean_a = concept_a.replace("'", "")

        # Form markers anywhere in THEN
        if iri in FORM_IRIS or clean_a in FORM_LABELS:
            label = FORM_LABELS.get(clean_a, clean_a)
            if label not in data_objects:
                data_objects.append(label)
            continue

        # Contain/Describe → extract content label
        if clean_a in CONTENT_CONCEPTS:
            refs = _atom_keyrefs(atom)
            funs = _atom_funs(atom)
            content_label = None
            if funs:
                _, fl = _iri_parts(funs[-1])
                content_label = fl.replace("'", "")
            elif len(refs) >= 3:
                cv = refs[2]
                if cv in var_registry:
                    vr = var_registry[cv]
                    cvc = vr.concept.replace("'", "")
                    if cvc and cvc not in ACTOR_CONCEPTS and cvc not in CONTENT_CONCEPTS:
                        content_label = cvc
            if content_label and content_label not in RAW_SKIP_LABELS:
                label = _humanize(content_label)
                if label not in data_objects and label not in RAW_SKIP_LABELS:
                    data_objects.append(label)

        # or-alternatives (TakenToAddress / ProposedToAddress)
        if clean_a == 'TakenToAddress' and 'Measures Already Taken' not in or_alts:
            or_alts.append('Measures Already Taken')
        if clean_a == 'ProposedToAddress' and 'Measures Proposed to Address' not in or_alts:
            or_alts.append('Measures Proposed to Address')

    # Also scan raw THEN XML for writtenForm / electronicForm (may be in Fun attrs)
    raw_then = ET.tostring(then_el, encoding='unicode')
    if 'writtenForm'  in raw_then and 'Written Form Required'    not in data_objects:
        data_objects.append('Written Form Required')
    if 'electronicForm' in raw_then and 'Electronic Form Required' not in data_objects:
        data_objects.append('Electronic Form Required')

    # ── After atom in THEN → get t1 reference ─────────────────────────────
    for atom in then_atoms:
        iri = _atom_iri(atom)
        if iri == 'After':
            refs = _atom_keyrefs(atom)
            if len(refs) >= 2 and time_t1 is None:
                time_t1 = refs[1]   # After :t2 :t1 → t1 is the second arg
            break

    if not primary_verb:
        return None

    return RawTask(
        actor        = actor,
        deontic      = deontic_concept,
        verb         = primary_verb,
        data_objects = data_objects,
        conditions   = conditions,
        gateway_type = gateway_type,
        recipient    = recipient,
        has_right    = has_right,
        or_alts      = or_alts,
        events       = events,
        time_t1      = time_t1,
        time_t2      = time_t2,
        source       = source_ref,
    )


def _iter_atoms_no_naf(el: ET.Element):
    """Yield all Atom children recursively, but skip those inside Naf blocks."""
    for child in el:
        if child.tag == R('Naf'):
            continue   # skip entirely — exception guard
        if child.tag == R('Atom'):
            yield child
        else:
            yield from _iter_atoms_no_naf(child)


# ── Main extraction function ───────────────────────────────────────────────────

# Module-level cache so the index is built only once per process
_INDEX_CACHE: dict[str, LRMLIndex] = {}


def extract_gdpr_structural(xml_path: str, target_article: str) -> list[dict]:
    """
    Main entry point — mirrors the signature of parser.extract_gdpr_master().
    Returns a list of task dicts compatible with generator.generate_bpmn_master().
    """
    print(f"[v2] Strukturelle Extraktion für '{target_article}'…")

    # Build or reuse index
    if xml_path not in _INDEX_CACHE:
        _INDEX_CACHE[xml_path] = LRMLIndex(xml_path)
    idx = _INDEX_CACHE[xml_path]

    # HOP 1-2: find statement IDs for this article
    source_ids: dict[str, str] = {}   # refersTo → refID
    for refers_to, ref_id in idx.legal_refs.items():
        if target_article.lower() in ref_id.lower():
            source_ids[refers_to] = ref_id

    statement_ids: dict[str, str] = {}   # stmt_key → refID
    for src_key, tgt_key in idx.associations.items():
        if src_key in source_ids and tgt_key in idx.statements:
            statement_ids[tgt_key] = source_ids[src_key]

    if not statement_ids:
        print(f"[v2] Keine Statements für '{target_article}' gefunden.")
        return []

    # HOP 3: parse each rule
    raw_tasks: list[RawTask] = []
    seen_events: set[str] = set()

    for stmt_key, ref_id in statement_ids.items():
        stmt_el = idx.statements[stmt_key]

        # Human-readable source label
        human_ref = ref_id
        human_ref = re.sub(r'GDPR:art_(\d+)', r'Art. \1', human_ref)
        human_ref = re.sub(r'__para_(\d+)',   r' Abs. \1', human_ref)
        human_ref = re.sub(r'__content__list_\d+__point_([a-z])', r' lit. \1', human_ref)

        for rule in stmt_el.iter(R('Rule')):
            rt = _parse_rule(rule, human_ref)
            if rt is None:
                continue
            raw_tasks.append(rt)

    # HOP 4: deduplicate, humanize, build output dicts
    # Collect content-only rules (no primary verb but data objects) → merge into earlier task
    content_only: list[RawTask] = []
    final_raw:    list[RawTask] = []

    for rt in raw_tasks:
        final_raw.append(rt)

    # Deduplicate by (verb, source)
    seen_key: dict[tuple, RawTask] = {}
    for rt in final_raw:
        key = (rt.verb.replace("'", ""), rt.source)
        if key not in seen_key:
            seen_key[key] = rt
        else:
            existing = seen_key[key]
            for d in rt.data_objects:
                if d not in existing.data_objects:
                    existing.data_objects.append(d)
            if rt.or_alts:
                for a in rt.or_alts:
                    if a not in existing.or_alts:
                        existing.or_alts.append(a)

    deduped = list(seen_key.values())

    # Build temporal ordering: chain by t1→t2
    # Rules whose t2 matches another rule's t1 come before it
    t2_to_idx = {rt.time_t2: i for i, rt in enumerate(deduped) if rt.time_t2}
    ordered = _topological_sort(deduped)

    # Infer current actor via carry-forward (same as before)
    current_actor = 'Controller'
    processed: list[dict] = []
    seen_ev_labels: set[str] = set()

    for rt in ordered:
        action = _humanize(rt.verb)
        if rt.has_right or rt.deontic in ('Permitted', 'Right'):
            action = f'Can {action}'

        recipient = RECIPIENT_HUMANIZER.get(rt.recipient, rt.recipient)
        bpmn_type = ('bpmn:sendTask'
                     if 'Notify' in action or rt.verb.replace("'", "") == 'Communicate'
                     else 'bpmn:task')

        # Actor: carry forward if still 'System'
        if rt.actor not in ('System', ''):
            current_actor = rt.actor
        actor = current_actor if rt.actor in ('System', '') else rt.actor

        # Gateway condition string
        gw_cond_str = None
        if rt.conditions:
            translated  = [_humanize_cond(c) for c in rt.conditions if c]
            join_word   = ' AND ' if rt.gateway_type == 'parallel' else ' OR '
            gw_cond_str = join_word.join(t for t in translated if t)

        # Events (first appearance only)
        trans_events = []
        for ev in rt.events:
            ev_label = _humanize(ev)
            if ev_label not in seen_ev_labels:
                seen_ev_labels.add(ev_label)
                trans_events.append(ev_label)

        # Data objects: humanize + filter
        data_objects_out = []
        seen_do: set[str] = set()
        for d in rt.data_objects:
            label = _humanize(d) if d not in HUMANIZER else HUMANIZER[d]
            if label and label not in RAW_SKIP_LABELS and label not in seen_do:
                seen_do.add(label)
                data_objects_out.append(label)

        processed.append({
            'id':           generate_id('Task_'),
            'actor':        actor,
            'action':       action,
            'recipient':    recipient,
            'source':       rt.source,
            'timer':        None,
            'bpmn_type':    bpmn_type,
            'gateway_cond': gw_cond_str,
            'gateway_type': rt.gateway_type,
            'events':       trans_events,
            'data_objects': data_objects_out,
            'or_alternatives': [_humanize(a) for a in rt.or_alts],
            'has_time_bound': any('elapsed' in c for c in rt.conditions),
        })

    print(f"[v2] {len(processed)} Aufgaben extrahiert.")
    return processed


def _topological_sort(tasks: list[RawTask]) -> list[RawTask]:
    """
    Sort tasks by temporal dependency: if task A's t2 == task B's t1,
    A comes before B. Falls back to original order where no edge exists.
    """
    n = len(tasks)
    if n == 0:
        return tasks

    # Build adjacency: index i → list of indices j that must come after i
    t2_to_indices: dict[str, list[int]] = defaultdict(list)
    for i, rt in enumerate(tasks):
        if rt.time_t2:
            t2_to_indices[rt.time_t2].append(i)

    in_degree  = [0] * n
    adj: list[list[int]] = [[] for _ in range(n)]

    for i, rt in enumerate(tasks):
        if rt.time_t1 and rt.time_t1 in t2_to_indices:
            for pred in t2_to_indices[rt.time_t1]:
                if pred != i:
                    adj[pred].append(i)
                    in_degree[i] += 1

    # Kahn's algorithm
    from collections import deque
    queue = deque(i for i in range(n) if in_degree[i] == 0)
    result: list[RawTask] = []
    while queue:
        i = queue.popleft()
        result.append(tasks[i])
        for j in adj[i]:
            in_degree[j] -= 1
            if in_degree[j] == 0:
                queue.append(j)

    # Append any stragglers not reached (cycles or isolated)
    reached = {id(t) for t in result}
    for t in tasks:
        if id(t) not in reached:
            result.append(t)

    return result
