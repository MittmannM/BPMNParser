from __future__ import annotations

import copy
import re
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Optional

from constants_v2 import (
    COND_HUMANIZER,
    CONTEXT_PREDICATES,
    HUMANIZER,
    RAW_SKIP_LABELS,
    RECIPIENT_HUMANIZER,
    RELATION_VERBS,
)
from utils import generate_id

LRML = 'http://docs.oasis-open.org/legalruleml/ns/v1.0/'
RULEML = 'http://ruleml.org/spec'


def _t(ns: str, local: str) -> str:
    return f'{{{ns}}}{local}'


L = lambda local: _t(LRML, local)
R = lambda local: _t(RULEML, local)


STRUCTURAL_IRIS: set[str] = {
    'rioOnto:RexistAtTime',
    'rioOnto:atTime',
    'rioOnto:and', "rioOnto:and'",
    'rioOnto:or', "rioOnto:or'",
    'rioOnto:not', "rioOnto:not'",
    'rioOnto:AbleTo',
    'rioOnto:possible', "rioOnto:possible'",
    'rioOnto:partOf',
    'rioOnto:cause',
    'rioOnto:nonDelayed',
    'swrlb:add', 'swrlb:subtract',
    'After', 'Before', 'Equal',
}

ACTOR_IRIS: set[str] = {
    'prOnto:Controller', 'prOnto:Processor',
    'prOnto:DataSubject', 'prOnto:SupervisoryAuthority',
    'prOnto:MemberState',
}

ACTOR_CONCEPTS: set[str] = {
    'Controller', 'Processor', 'DataSubject', 'SupervisoryAuthority', 'MemberState',
}

DEONTIC_IRIS: set[str] = {
    'rioOnto:Obliged', 'rioOnto:Permitted', 'rioOnto:Right', 'rioOnto:Prohibited',
}

TYPE_ASSERTION_CONCEPTS: set[str] = {
    'PersonalData', 'PersonalDataRecord', 'PersonalDataProcessing',
}

FORM_IRIS: set[str] = {
    'dapreco:writtenForm', 'dapreco:electronicForm',
    "dapreco:writtenForm'", "dapreco:electronicForm'",
}

FORM_LABELS: dict[str, str] = {
    'writtenForm': 'Written Form Required',
    'electronicForm': 'Electronic Form Required',
}

CONTENT_CONCEPTS: set[str] = {'Contain', 'CategoryOf', 'allInfoAbout'}

ACTION_SKIP_CONCEPTS: set[str] = {
    'AbleTo', 'RexistAtTime', 'atTime', 'nonDelayed',
    'writtenForm', 'electronicForm', 'Document',
    'DPO', 'Recipient', 'CategoryOf', 'Representative',
    'Complaint', 'Fee', 'ThePublic',
    'Consent', 'GiveConsent', 'ContactPointFor', 'public',
    'DataProtectionPolicies',
    'lawfulness', 'fairness', 'transparency', 'specified',
    'CompatibleWith', 'AdequateWith', 'RelevantTo', 'LimitedTo',
    'accurate', 'upToDate', 'security', 'IdentifiableFrom',
    'EasyAs', 'Icon', 'NotForProfitBody',
}

TERM_DATA_FUNS: set[str] = {
    'allInfoAbout', 'natureOf', 'contactDetails', 'dpoOrCP', 'dpoOrCp',
    'copyOf', 'legalBasisOf', 'numberOfDSConcerned', 'numberOfPDRConcerned',
    'progressOf', 'draftOf', 'highestManagementLevel', 'countryOf',
    'minAgeForConsent', 'ageOf', 'rightsAndFreedoms', 'legitimateInterest',
}

NOTE_ONLY_CONCEPTS: set[str] = {'nonDelayed', 'reasonable', 'Document', 'Verify'}

ACTION_SIGNATURES: dict[str, dict[str, object]] = {
    'Communicate': {'actor': 1, 'recipient': 2, 'content': (3,)},
    'Request': {'actor': 1, 'content': (2,)},
    'ReceiveFrom': {'actor': 1, 'content': (2,), 'recipient': 3},
    'Access': {'actor': 1, 'content': (2,)},
    'Delete': {'actor': 1, 'content': (2,)},
    'Rectify': {'actor': 1, 'content': (2,)},
    'Lodge': {'actor': 1, 'content': (2,), 'recipient': 3},
    'PayFor': {'actor': 1, 'content': (2,)},
    'Charge': {'actor': 1, 'recipient': 2, 'content': (3,)},
    'Execute': {'actor': 1, 'content': (2,)},
    'Transmit': {'actor': 1, 'recipient': 2, 'content': (3,)},
    'ComplyWith': {'actor': 1, 'content': (2,)},
    'Hold': {'actor': 1, 'content': (2,)},
    'Store': {'actor': 1, 'content': (2,)},
    'TakeIntoAccount': {'actor': 1, 'content': (2,)},
    'Identify': {'actor': 1, 'recipient': 2},
}

CONDITION_KEEP_CONCEPTS: set[str] = {
    'DataBreach', 'AwareOf', 'HasBeenDamaged', 'ViolationOf',
    'Risk', 'likely', 'riskinessRightsFreedoms', 'Person',
    'lawfulness', 'WithdrawConsent', 'GiveConsent', 'Consent',
    'public', 'publicInterest', 'Marketing', 'requireTooMuchEffort',
    'accurate', 'Store', 'feasible', 'Partial Information Available',
    'NOT Possible',
}

CONDITION_DROP_CONCEPTS: set[str] = (
    CONTEXT_PREDICATES
    | RELATION_VERBS
    | {
        'nominates', 'AuthorizedBy', 'LegalRequirement', 'Purpose',
        'isBasedOn', 'RepresentedBy', 'Representative',
        'Communicate', 'Request', 'ReceiveFrom', 'PayFor',
        'ResponsibleFor', 'Delete', 'Define', 'Verify', 'Document',
        'TakenToAddress', 'ProposedToAddress', 'Measure',
        'Execute', 'Hold', 'RelatedTo', 'partOf', 'allInfoAbout',
        'ComplyWith', 'SupervisoryAuthority', 'Controller',
        'Processor', 'DataSubject', 'MemberState',
        'PersonalData', 'PersonalDataProcessing', 'ThirdParty',
        'Public_Body', 'publicPowers', 'DPO', 'CategoryOf',
        'Recipient', 'designates', 'ReachableFrom',
        'Identify', 'IdentifiableFrom', 'Fee', 'Refuse', 'AbleTo',
    }
)

CONDITION_PRIORITY: dict[str, int] = {
    'DataBreach': 10,
    'AwareOf': 20,
    'HasBeenDamaged': 30,
    'ViolationOf': 40,
    'Risk': 50,
    'riskinessRightsFreedoms': 60,
    'Person': 70,
    'WithdrawConsent': 80,
    'public': 90,
    'publicInterest': 100,
    'Marketing': 110,
    'lawfulness': 120,
    'Consent': 130,
    'GiveConsent': 140,
    'requireTooMuchEffort': 150,
    'accurate': 160,
    'Store': 170,
    'feasible': 180,
    'Partial Information Available': 190,
    'NOT Possible': 200,
}


@dataclass
class VarRecord:
    key: str
    concept: str = ''
    ns: str = ''
    is_actor: bool = False


@dataclass
class ActionRecord:
    verb: str
    actor: Optional[str] = None
    recipient: Optional[str] = None
    refs: tuple[str, ...] = ()
    data_objects: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    note: Optional[str] = None
    negated: bool = False


@dataclass
class BranchRecord:
    label: str
    actions: list[ActionRecord] = field(default_factory=list)


@dataclass
class RawTask:
    actor: str
    deontic: str
    verb: str
    data_objects: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    gateway_type: str = 'exclusive'
    recipient: Optional[str] = None
    has_right: bool = False
    or_alts: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    time_t1: Optional[str] = None
    time_t2: Optional[str] = None
    timer: Optional[str] = None
    post_actions: list[ActionRecord] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    source: str = ''
    negated: bool = False
    branches: list[BranchRecord] = field(default_factory=list)


def _iri_parts(iri: str) -> tuple[str, str]:
    if ':' in iri:
        return iri.split(':', 1)
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


def _extract_article_token(ref_id: str) -> Optional[str]:
    match = re.search(r'art_(\d+)', ref_id)
    if not match:
        return None
    return f"art_{int(match.group(1))}"


def _append_unique(target: list[str], value: Optional[str]):
    if value and value not in target:
        target.append(value)


def _duration_to_iso(duration_text: str) -> str:
    clean = duration_text.strip().lower()
    if clean.endswith('h') and clean[:-1].isdigit():
        return f"PT{clean[:-1]}H"
    if clean.endswith('d') and clean[:-1].isdigit():
        return f"P{clean[:-1]}D"
    if clean.endswith('m') and clean[:-1].isdigit():
        return f"P{clean[:-1]}M"
    if clean.endswith('y') and clean[:-1].isdigit():
        return f"P{clean[:-1]}Y"
    return duration_text.strip()


def _expr_fun(expr: ET.Element) -> Optional[str]:
    fun = expr.find(R('Fun'))
    return fun.get('iri', '') if fun is not None else None


def _expr_label(expr: ET.Element, var_registry: dict[str, VarRecord]) -> Optional[str]:
    fun_iri = _expr_fun(expr)
    if not fun_iri:
        return None
    _, concept = _iri_parts(fun_iri)
    clean = concept.replace("'", "")
    if clean == 'SupervisoryAuthority':
        return 'Competent Supervisory Authority'
    if clean == 'MemberState':
        return 'Member State'
    if clean in TERM_DATA_FUNS:
        return _humanize(clean)
    return _humanize(clean)


def _atom_arguments(atom: ET.Element) -> list[ET.Element]:
    return [child for child in atom if child.tag != R('Rel')]


def _arg_var_key(arg: ET.Element) -> Optional[str]:
    if arg.tag != R('Var'):
        return None
    return arg.get('keyref') or arg.get('key')


def _arg_actor_label(arg: ET.Element, var_registry: dict[str, VarRecord]) -> Optional[str]:
    if arg.tag == R('Var'):
        key = _arg_var_key(arg)
        if key and key in var_registry and var_registry[key].is_actor:
            return var_registry[key].concept
    if arg.tag == R('Expr'):
        fun_iri = _expr_fun(arg)
        if fun_iri:
            _, concept = _iri_parts(fun_iri)
            clean = concept.replace("'", "")
            if clean == 'SupervisoryAuthority':
                return 'SupervisoryAuthority'
            if clean in ACTOR_CONCEPTS:
                return clean
    return None


def _arg_data_label(arg: ET.Element, var_registry: dict[str, VarRecord]) -> Optional[str]:
    if arg.tag == R('Expr'):
        return _expr_label(arg, var_registry)
    if arg.tag == R('Ind'):
        text = (arg.text or '').strip()
        return text or None
    if arg.tag == R('Var'):
        key = _arg_var_key(arg)
        if key and key in var_registry:
            record = var_registry[key]
            if record.concept and not record.is_actor:
                label = _humanize(record.concept)
                if label not in RAW_SKIP_LABELS:
                    return label
    return None


def _comparison_label(atom: ET.Element, var_registry: dict[str, VarRecord], negated: bool = False) -> Optional[str]:
    iri = _atom_iri(atom)
    _, concept = _iri_parts(iri)
    clean = concept.replace("'", "")
    args = _atom_arguments(atom)
    labels = [label for label in (_arg_data_label(arg, var_registry) for arg in args) if label]
    if not labels:
        return None
    if clean == 'lessThanOrEqual' and labels[:2] == ['Age of Data Subject', 'Minimum Consent Age']:
        return 'Age at or below minimum consent age'
    if clean == 'equal' and labels[:2] == ['Country', 'Country']:
        return 'Same Country' if not negated else 'Different Country'
    joiner = 'equals' if clean == 'equal' else 'is at or below'
    if len(labels) >= 2:
        prefix = 'NOT ' if negated else ''
        return f"{prefix}{labels[0]} {joiner} {labels[1]}"
    return None


def _condition_label_from_atom(atom: ET.Element, var_registry: dict[str, VarRecord]) -> Optional[str]:
    iri = _atom_iri(atom)
    _, concept = _iri_parts(iri)
    clean = concept.replace("'", "")
    if clean in {'equal', 'lessThanOrEqual'}:
        return _comparison_label(atom, var_registry)
    if clean == 'Override':
        labels = [label for label in (_arg_data_label(arg, var_registry) for arg in _atom_arguments(atom)) if label]
        if len(labels) >= 2:
            return f"{labels[0]} overridden by {labels[1]}"
    if clean == 'Hold':
        labels = [label for label in (_arg_data_label(arg, var_registry) for arg in _atom_arguments(atom)) if label]
        if 'Legitimate Interest' in labels:
            return 'Legitimate Interest'
    if clean == 'ThirdCountry':
        return 'Transfer to Third Country'
    if clean == 'InternationalOrganization':
        return 'Transfer to International Organization'
    if not _is_meaningful_condition(clean):
        return None
    return _humanize_cond(clean)


def _extract_fun_labels(atom: ET.Element) -> list[str]:
    labels: list[str] = []
    for fun_iri in _atom_funs(atom):
        _, concept = _iri_parts(fun_iri)
        clean = concept.replace("'", "")
        if clean in TERM_DATA_FUNS:
            _append_unique(labels, _humanize(clean))
    return labels


def _extract_action_notes(atom: ET.Element) -> list[str]:
    notes: list[str] = []
    fun_labels = [iri.split(':', 1)[1].replace("'", "") for iri in _atom_funs(atom) if ':' in iri]
    if 'SupervisoryAuthority' in fun_labels and 'MemberState' in fun_labels:
        _append_unique(notes, 'Notify the competent supervisory authority')

    inds = [(ind.text or '').strip() for ind in atom.iter(R('Ind')) if (ind.text or '').strip()]
    for ind in inds:
        if ind.startswith('Article'):
            _append_unique(notes, f"Relates to {ind.replace('Article', 'Article ')}")
        elif ind == 'GDPR':
            _append_unique(notes, 'Under the GDPR')
    return notes


def _collect_action_data_labels(atom: ET.Element, var_registry: dict[str, VarRecord], concept: str) -> list[str]:
    labels: list[str] = []
    signature = ACTION_SIGNATURES.get(concept, {})
    for idx in signature.get('content', ()):
        args = _atom_arguments(atom)
        if idx < len(args):
            _append_unique(labels, _arg_data_label(args[idx], var_registry))
    for label in _extract_fun_labels(atom):
        _append_unique(labels, label)
    return labels


def _extract_action_recipient(atom: ET.Element, var_registry: dict[str, VarRecord], concept: str) -> Optional[str]:
    args = _atom_arguments(atom)
    signature = ACTION_SIGNATURES.get(concept, {})
    recipient_idx = signature.get('recipient')
    if isinstance(recipient_idx, int) and recipient_idx < len(args):
        recipient = _arg_actor_label(args[recipient_idx], var_registry)
        if recipient:
            return recipient
    if concept in ACTION_SIGNATURES:
        return None
    for arg in args[2:]:
        recipient = _arg_actor_label(arg, var_registry)
        if recipient:
            return recipient
    return None


def _extract_timer(rule: ET.Element, time_target: Optional[str]) -> Optional[str]:
    for atom in rule.iter(R('Atom')):
        before = atom.find(R('Before'))
        if before is None:
            continue
        children = list(before)
        if len(children) < 2 or children[0].tag != R('Var') or children[1].tag != R('Expr'):
            continue
        target_ref = children[0].get('keyref') or children[0].get('key')
        if time_target and target_ref != time_target:
            continue
        fun_iri = _expr_fun(children[1])
        if fun_iri != 'swrlb:add':
            continue
        for ind in children[1].findall(R('Ind')):
            text = (ind.text or '').strip()
            if text:
                return _duration_to_iso(text)
    return None


def _iter_atoms_no_naf(el: ET.Element):
    for child in el:
        if child.tag == R('Naf'):
            continue
        if child.tag == R('Atom'):
            yield child
        else:
            yield from _iter_atoms_no_naf(child)


def _iter_naf_atoms(el: ET.Element):
    for naf in el.iter(R('Naf')):
        for atom in naf.iter(R('Atom')):
            yield atom


def _extract_exception_note(atom: ET.Element) -> Optional[str]:
    iri = _atom_iri(atom)
    if 'exception' not in iri:
        return None
    _, concept = _iri_parts(iri)
    return _humanize_exception_reference(concept, negate=True)


def _extract_article_note(rule: ET.Element, source_ref: str) -> Optional[str]:
    then_el = rule.find(R('then'))
    if then_el is None:
        return None
    for atom in then_el.iter(R('Atom')):
        if 'exception' in _atom_iri(atom):
            return f"Check exception in {source_ref}"
    return None


def _humanize_exception_reference(token: str, negate: bool = False) -> str:
    text = token.replace("'", "")
    match = re.match(
        r'exceptionCha(?P<chapter>\d+)(?:Sec(?P<section>\d+))?Art(?P<article>\d+)Par(?P<paragraph>\d+)(?:Point(?P<point>[A-Za-z0-9]+))?(?P<suffix>[A-Za-z]*)',
        text,
    )
    if not match:
        prefix = "No exception under" if negate else "Exception under"
        return f"{prefix} {text}"

    article = f"Art. {match.group('article')}"
    paragraph = f" Abs. {match.group('paragraph')}"
    point = match.group('point')
    point_text = f", point {point}" if point else ""
    prefix = "No exception under" if negate else "Exception under"
    return f"{prefix} {article}{paragraph}{point_text}"


def _note_for_concept(concept: str) -> Optional[str]:
    clean = concept.replace("'", "")
    notes = {
        'nonDelayed': 'Perform without undue delay',
        'reasonable': 'Use reasonable effort',
        'Verify': 'Outcome should be verifiable',
        'Document': 'Document the resulting information',
    }
    return notes.get(clean)


def _is_low_value_post_action(concept: str) -> bool:
    clean = concept.replace("'", "")
    return clean in {
        'Communicate', 'Consent', 'GiveConsent', 'ContactPointFor',
        'public', 'DataProtectionPolicies', 'Complaint', 'Fee',
        'HighRiskToIndividuals',
    }


def _is_meaningful_condition(concept: str) -> bool:
    clean = concept.replace("'", "")
    if clean in CONDITION_KEEP_CONCEPTS:
        return True
    if clean in CONDITION_DROP_CONCEPTS:
        return False
    if clean.startswith('exception'):
        return False
    return clean not in ACTOR_CONCEPTS and clean not in TYPE_ASSERTION_CONCEPTS


def _simplify_conditions(conditions: list[str], gateway_type: str) -> list[str]:
    kept: list[str] = []
    seen: set[str] = set()
    for condition in conditions:
        clean = condition.strip()
        if not clean:
            continue
        if clean not in seen:
            seen.add(clean)
            kept.append(clean)
    return kept[:4]


def _resolve_actor_from_var(var_key: Optional[str], var_registry: dict[str, VarRecord]) -> Optional[str]:
    if var_key and var_key in var_registry and var_registry[var_key].is_actor:
        return var_registry[var_key].concept
    return None


def _expand_action_vars(action_var: Optional[str], atom_by_first_ref: dict[str, list[ET.Element]]) -> list[str]:
    if not action_var:
        return []
    ordered: list[str] = []
    seen: set[str] = set()
    queue = deque([action_var])
    while queue:
        current = queue.popleft()
        if current in seen:
            continue
        seen.add(current)
        ordered.append(current)
        for atom in atom_by_first_ref.get(current, []):
            _, concept = _iri_parts(_atom_iri(atom))
            clean = concept.replace("'", "")
            if clean in ('AbleTo', 'and', 'or'):
                for ref in _atom_keyrefs(atom)[1:]:
                    if ref not in seen:
                        queue.append(ref)
    return ordered


def _atom_to_action(atom: ET.Element, var_registry: dict[str, VarRecord]) -> Optional[ActionRecord]:
    iri = _atom_iri(atom)
    ns, concept = _iri_parts(iri)
    clean = concept.replace("'", "")
    if not clean:
        return None
    if iri in STRUCTURAL_IRIS or iri in DEONTIC_IRIS:
        return None
    if ns in ('rioOnto', 'swrlb', 'rdfs', 'ruleml'):
        return None
    if clean in ACTION_SKIP_CONCEPTS or clean in ACTOR_CONCEPTS or clean in CONTENT_CONCEPTS or clean in TYPE_ASSERTION_CONCEPTS:
        return None

    refs = tuple(_atom_keyrefs(atom))
    actor = _resolve_actor_from_var(refs[1] if len(refs) > 1 else None, var_registry)
    recipient = _extract_action_recipient(atom, var_registry, clean)
    data_objects = _collect_action_data_labels(atom, var_registry, clean)
    note = _note_for_concept(clean)
    return ActionRecord(clean, actor, recipient, refs, data_objects, _extract_action_notes(atom), note)


def _synthetic_action_from_atom(atom: ET.Element, var_registry: dict[str, VarRecord]) -> Optional[ActionRecord]:
    iri = _atom_iri(atom)
    _, concept = _iri_parts(iri)
    clean = concept.replace("'", "")
    refs = tuple(_atom_keyrefs(atom))
    args = _atom_arguments(atom)
    if clean == 'PersonalDataProcessing':
        actor = _resolve_actor_from_var(refs[1] if len(refs) > 1 else None, var_registry)
        data_objects: list[str] = []
        if len(args) > 2:
            _append_unique(data_objects, _arg_data_label(args[2], var_registry))
        return ActionRecord('Process', actor, None, refs, data_objects)
    return None


def _collect_action_records(atoms: list[ET.Element], var_registry: dict[str, VarRecord]) -> list[ActionRecord]:
    records: list[ActionRecord] = []
    for atom in atoms:
        action = _atom_to_action(atom, var_registry)
        if action is None:
            action = _synthetic_action_from_atom(atom, var_registry)
        if action is not None:
            records.append(action)
    return records


def _find_action_by_refs(
    refs: list[str],
    action_records: list[ActionRecord],
    atom_by_first_ref: dict[str, list[ET.Element]],
    var_registry: dict[str, VarRecord],
) -> Optional[ActionRecord]:
    for ref in refs:
        for action in action_records:
            if action.refs and action.refs[0] == ref and action.verb not in NOTE_ONLY_CONCEPTS:
                return copy.deepcopy(action)
        for atom in atom_by_first_ref.get(ref, []):
            synthetic = _synthetic_action_from_atom(atom, var_registry)
            if synthetic is not None and synthetic.verb not in NOTE_ONLY_CONCEPTS:
                return synthetic
    return None


def _resolve_negated_action(
    primary_refs: list[str],
    atoms: list[ET.Element],
    action_records: list[ActionRecord],
    atom_by_first_ref: dict[str, list[ET.Element]],
    var_registry: dict[str, VarRecord],
) -> Optional[ActionRecord]:
    for atom in atoms:
        if _atom_iri(atom) not in {'rioOnto:not', "rioOnto:not'"}:
            continue
        refs = _atom_keyrefs(atom)
        if len(refs) < 2 or refs[0] not in primary_refs:
            continue
        negated = _find_action_by_refs([refs[1]], action_records, atom_by_first_ref, var_registry)
        if negated is None:
            continue
        negated.negated = True
        return negated
    return None


def _expand_branch_refs(root_ref: str, atom_by_first_ref: dict[str, list[ET.Element]]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    queue = deque([root_ref])
    while queue:
        current = queue.popleft()
        if current in seen:
            continue
        seen.add(current)
        ordered.append(current)
        for atom in atom_by_first_ref.get(current, []):
            _, concept = _iri_parts(_atom_iri(atom))
            clean = concept.replace("'", "")
            if clean in {'AbleTo', 'and', 'or', 'cause'}:
                for ref in _atom_keyrefs(atom)[1:]:
                    if ref not in seen:
                        queue.append(ref)
    return ordered


def _extract_branch_records(
    primary_refs: list[str],
    atom_by_first_ref: dict[str, list[ET.Element]],
    action_records: list[ActionRecord],
    var_registry: dict[str, VarRecord],
) -> tuple[Optional[str], list[BranchRecord]]:
    seen_signatures: set[tuple[str, tuple[str, ...]]] = set()
    for ref in primary_refs:
        for atom in atom_by_first_ref.get(ref, []):
            _, concept = _iri_parts(_atom_iri(atom))
            clean = concept.replace("'", "")
            if clean not in {'and', 'or'}:
                continue
            branch_type = 'parallel' if clean == 'and' else 'exclusive'
            branches: list[BranchRecord] = []
            for child_ref in _atom_keyrefs(atom)[1:]:
                action = _find_action_by_refs(
                    _expand_branch_refs(child_ref, atom_by_first_ref),
                    action_records,
                    atom_by_first_ref,
                    var_registry,
                )
                if action is None or action.verb in NOTE_ONLY_CONCEPTS:
                    continue
                signature = (action.verb, action.refs)
                if signature in seen_signatures:
                    continue
                seen_signatures.add(signature)
                label = _humanize(action.verb)
                if action.verb == 'Describe':
                    for ref in action.refs[1:]:
                        for related_atom in atom_by_first_ref.get(ref, []):
                            _, related_concept = _iri_parts(_atom_iri(related_atom))
                            related_clean = related_concept.replace("'", "")
                            if related_clean in {'TakenToAddress', 'ProposedToAddress'}:
                                label = _humanize(related_clean)
                                action = copy.deepcopy(action)
                                if label not in action.data_objects:
                                    action.data_objects.append(label)
                                break
                        if label != _humanize(action.verb):
                            break
                if action.data_objects:
                    label = ', '.join(_humanize(item) for item in action.data_objects if item) or label
                branches.append(BranchRecord(label=label, actions=[copy.deepcopy(action)]))
            if len(branches) >= 2:
                return branch_type, branches
    return None, []


def _collect_data_object_from_content(atom: ET.Element, var_registry: dict[str, VarRecord]) -> list[str]:
    labels: list[str] = []
    _, concept = _iri_parts(_atom_iri(atom))
    clean = concept.replace("'", "")
    if clean in CONTENT_CONCEPTS:
        funs = _atom_funs(atom)
        refs = _atom_keyrefs(atom)
        if funs:
            _, label_concept = _iri_parts(funs[-1])
            _append_unique(labels, _humanize(label_concept.replace("'", "")))
        elif len(refs) >= 3:
            ref = refs[2]
            if ref in var_registry:
                _append_unique(labels, _humanize(var_registry[ref].concept))
    if clean == 'partOf':
        for label in _extract_fun_labels(atom):
            _append_unique(labels, label)
    return [label for label in labels if label and label not in RAW_SKIP_LABELS]


class LRMLIndex:
    def __init__(self, xml_path: str):
        print("  [v2] Parsing XML into index...")
        self.tree = ET.parse(xml_path)
        self.root = self.tree.getroot()
        self.statements: dict[str, ET.Element] = {}
        for stmt in self.root.iter(L('Statements')):
            key = stmt.get('key')
            if key:
                self.statements[key] = stmt
        self.legal_refs: dict[str, str] = {}
        for lr in self.root.iter(L('LegalReference')):
            rt = lr.get('refersTo')
            ri = lr.get('refID')
            if rt and ri:
                self.legal_refs[rt] = ri
        self.associations: dict[str, list[str]] = defaultdict(list)
        for assoc in self.root.iter(L('Association')):
            src_el = assoc.find(L('appliesSource'))
            tgt_el = assoc.find(L('toTarget'))
            if src_el is None or tgt_el is None:
                continue
            src = src_el.get('keyref', '').lstrip('#')
            tgt = tgt_el.get('keyref', '').lstrip('#')
            if src and tgt:
                self.associations[src].append(tgt)
        self.formula_contexts: dict[str, str] = {}
        for context in self.root.iter(L('Context')):
            context_type = context.get('type', '')
            for in_scope in context.findall(L('inScope')):
                formula_key = in_scope.get('keyref', '').lstrip('#')
                if formula_key:
                    self.formula_contexts[formula_key] = context_type
        print(
            f"  [v2] Index built: {len(self.statements)} statements, "
            f"{len(self.legal_refs)} legal refs, "
            f"{sum(len(targets) for targets in self.associations.values())} associations"
        )


def _parse_rule(rule: ET.Element, source_ref: str, context_type: Optional[str] = None) -> Optional[RawTask]:
    if_el = rule.find(R('if'))
    then_el = rule.find(R('then'))
    if then_el is None:
        return None

    if_atoms = list(_iter_atoms_no_naf(if_el)) if if_el is not None else []
    then_atoms = list(then_el.iter(R('Atom')))

    deontic_atom = None
    deontic_iri = ''
    for atom in then_atoms:
        iri = _atom_iri(atom)
        if iri in DEONTIC_IRIS:
            deontic_atom = atom
            deontic_iri = iri
            break

    deontic_concept = ''
    keyrefs_d: list[str] = []
    funs_d: list[str] = []
    action_var: Optional[str] = None
    time_t2: Optional[str] = None
    actor_var: Optional[str] = None

    if deontic_atom is not None:
        _, deontic_concept = _iri_parts(deontic_iri)
        keyrefs_d = _atom_keyrefs(deontic_atom)
        funs_d = _atom_funs(deontic_atom)
        action_var = keyrefs_d[0] if len(keyrefs_d) > 0 else None
        time_t2 = keyrefs_d[1] if len(keyrefs_d) > 1 else None
        actor_var = keyrefs_d[2] if len(keyrefs_d) > 2 else None
    elif context_type in {'rioOnto:obligationRule', 'rioOnto:permissionRule'}:
        for atom in then_atoms:
            if _atom_iri(atom) != 'rioOnto:RexistAtTime':
                continue
            refs = _atom_keyrefs(atom)
            if not refs:
                continue
            action_var = refs[0]
            time_t2 = refs[1] if len(refs) > 1 else None
            deontic_concept = 'Obliged' if context_type == 'rioOnto:obligationRule' else 'Permitted'
            break
        if not action_var:
            return None
    else:
        return None

    has_right = deontic_concept in ('Permitted', 'Right')

    var_registry: dict[str, VarRecord] = {}
    conditions: list[str] = []
    notes: list[str] = []
    time_t1: Optional[str] = None
    gateway_type = 'annotation'

    if if_el is not None:
        for var in if_el.iter(R('Var')):
            key = var.get('key')
            if key:
                var_registry[key] = VarRecord(key=key)

        for atom in if_atoms:
            iri = _atom_iri(atom)
            ns, concept = _iri_parts(iri)
            clean = concept.replace("'", "")

            if iri == 'rioOnto:RexistAtTime':
                keys = _atom_keys(atom)
                if keys:
                    time_t1 = keys[0]
                continue
            if iri in ('rioOnto:and', "rioOnto:and'", 'rioOnto:or', "rioOnto:or'"):
                for var in atom.iter(R('Var')):
                    key = var.get('key')
                    if key and key not in var_registry:
                        var_registry[key] = VarRecord(key=key)
                continue
            if iri in STRUCTURAL_IRIS or ns in ('rioOnto', 'swrlb', 'rdfs', 'ruleml'):
                continue

            if iri in ACTOR_IRIS or clean in ACTOR_CONCEPTS:
                for var in atom.iter(R('Var')):
                    key = var.get('key') or var.get('keyref')
                    if key:
                        if key not in var_registry:
                            var_registry[key] = VarRecord(key=key)
                        var_registry[key].concept = clean
                        var_registry[key].ns = ns
                        var_registry[key].is_actor = True
                continue

            if clean in TYPE_ASSERTION_CONCEPTS:
                for var in atom.iter(R('Var')):
                    key = var.get('key') or var.get('keyref')
                    if key and key in var_registry and not var_registry[key].concept:
                        var_registry[key].concept = clean
                        var_registry[key].ns = ns
                continue

            for var in atom.iter(R('Var')):
                key = var.get('key') or var.get('keyref')
                if key and key in var_registry and not var_registry[key].concept:
                    var_registry[key].concept = clean
                    var_registry[key].ns = ns
            _append_unique(conditions, _condition_label_from_atom(atom, var_registry))

        raw_if = ET.tostring(if_el, encoding='unicode')
        if 'rioOnto:possible' in raw_if:
            _append_unique(notes, 'Further information may be provided later')
        for neg in if_el.iter(R('Neg')):
            equal = neg.find(R('Equal'))
            if equal is None:
                continue
            fake_atom = ET.Element(R('Atom'))
            rel = ET.SubElement(fake_atom, R('Rel'))
            rel.set('iri', 'equal')
            for child in list(equal):
                fake_atom.append(copy.deepcopy(child))
            _append_unique(conditions, _comparison_label(fake_atom, var_registry, negated=True))
        for naf_atom in _iter_naf_atoms(if_el):
            _append_unique(notes, _extract_exception_note(naf_atom))

    actor = _resolve_actor_from_var(actor_var, var_registry) or 'System'
    if actor == 'System':
        for fun_iri in funs_d:
            _, concept = _iri_parts(fun_iri)
            if concept in ACTOR_CONCEPTS:
                actor = concept
                break

    if deontic_concept == 'Right':
        right_actor_var = keyrefs_d[0] if keyrefs_d else None
        action_var = keyrefs_d[1] if len(keyrefs_d) > 1 else None
        actor = _resolve_actor_from_var(right_actor_var, var_registry) or actor

    atom_by_first_ref: dict[str, list[ET.Element]] = defaultdict(list)
    for atom in [*if_atoms, *then_atoms]:
        refs = _atom_keyrefs(atom)
        if refs:
            atom_by_first_ref[refs[0]].append(atom)

    then_action_records = _collect_action_records(then_atoms, var_registry)
    if_action_records = _collect_action_records(if_atoms, var_registry)
    action_records = then_action_records + [
        action
        for action in if_action_records
        if action.refs not in {existing.refs for existing in then_action_records}
    ]
    primary_refs = _expand_action_vars(action_var, atom_by_first_ref)
    primary_action = _find_action_by_refs(primary_refs, action_records, atom_by_first_ref, var_registry)
    if primary_action is None:
        primary_action = _resolve_negated_action(
            primary_refs,
            [*then_atoms, *if_atoms],
            action_records,
            atom_by_first_ref,
            var_registry,
        )
    if primary_action is None and action_records:
        primary_action = copy.deepcopy(action_records[0])
    if primary_action is None:
        return None
    if actor == 'System' and primary_action.actor:
        actor = primary_action.actor
    for action_note in primary_action.notes:
        _append_unique(notes, action_note)

    data_objects: list[str] = []
    for label in primary_action.data_objects:
        _append_unique(data_objects, label)

    or_alts: list[str] = []
    for atom in then_atoms:
        iri = _atom_iri(atom)
        _, concept = _iri_parts(iri)
        clean = concept.replace("'", "")
        if iri in FORM_IRIS or clean in FORM_LABELS:
            _append_unique(data_objects, FORM_LABELS.get(clean, clean))
        for label in _collect_data_object_from_content(atom, var_registry):
            _append_unique(data_objects, label)
        for label in _extract_fun_labels(atom):
            _append_unique(data_objects, label)
        if clean == 'TakenToAddress':
            _append_unique(or_alts, 'Measures Already Taken')
            _append_unique(data_objects, 'Measures Already Taken')
        if clean == 'ProposedToAddress':
            _append_unique(or_alts, 'Measures Proposed to Address')
            _append_unique(data_objects, 'Measures Proposed to Address')
        if clean == 'nonDelayed':
            _append_unique(notes, _note_for_concept(clean))
        if clean == 'reasonable':
            _append_unique(notes, _note_for_concept(clean))
        if clean == 'Verify':
            _append_unique(notes, _note_for_concept(clean))

    raw_then = ET.tostring(then_el, encoding='unicode')
    if 'writtenForm' in raw_then:
        _append_unique(data_objects, 'Written Form Required')
    if 'electronicForm' in raw_then:
        _append_unique(data_objects, 'Electronic Form Required')

    for atom in then_atoms:
        if _atom_iri(atom) == 'After':
            refs = _atom_keyrefs(atom)
            if len(refs) >= 2 and time_t1 is None:
                time_t1 = refs[1]
            break

    post_actions: list[ActionRecord] = []
    primary_signature = (primary_action.verb, primary_action.refs)
    seen_actions: set[tuple[str, tuple[str, ...]]] = set()
    for action in then_action_records:
        signature = (action.verb, action.refs)
        if signature == primary_signature or signature in seen_actions:
            continue
        seen_actions.add(signature)
        for action_note in action.notes:
            _append_unique(notes, action_note)
        if action.verb in NOTE_ONLY_CONCEPTS:
            _append_unique(notes, action.note or _note_for_concept(action.verb) or _humanize(action.verb))
            continue
        if _humanize(action.verb) == _humanize(primary_action.verb):
            continue
        if action.verb in {'TakenToAddress', 'ProposedToAddress', 'Measure'}:
            continue
        if _is_low_value_post_action(action.verb):
            continue
        post_actions.append(action)

    branch_gateway_type, branches = _extract_branch_records(
        primary_refs,
        atom_by_first_ref,
        action_records,
        var_registry,
    )
    if branch_gateway_type and branches:
        gateway_type = branch_gateway_type

    conditions = _simplify_conditions(conditions, gateway_type)
    notes = [note for note in notes if note]
    if context_type == 'rioOnto:obligationRule' and deontic_concept != 'Obliged':
        _append_unique(notes, 'Context type expects an obligation mapping')
    if context_type == 'rioOnto:permissionRule' and deontic_concept not in {'Permitted', 'Right'}:
        _append_unique(notes, 'Context type expects a permission mapping')
    if len(or_alts) >= 2:
        _append_unique(notes, 'Include measures already taken or proposed to address the breach')
        or_alts = []

    return RawTask(
        actor=actor,
        deontic=deontic_concept,
        verb=primary_action.verb,
        data_objects=data_objects,
        conditions=conditions,
        gateway_type=gateway_type,
        recipient=primary_action.recipient,
        has_right=has_right,
        or_alts=or_alts,
        events=[],
        time_t1=time_t1,
        time_t2=time_t2,
        timer=_extract_timer(rule, time_t2),
        post_actions=post_actions,
        notes=notes,
        source=source_ref,
        negated=primary_action.negated,
        branches=branches,
    )


_INDEX_CACHE: dict[str, LRMLIndex] = {}


def extract_gdpr_structural(xml_path: str, target_article: str) -> list[dict]:
    print(f"[v2] Strukturelle Extraktion fuer '{target_article}'...")
    if xml_path not in _INDEX_CACHE:
        _INDEX_CACHE[xml_path] = LRMLIndex(xml_path)
    idx = _INDEX_CACHE[xml_path]

    target_token = _extract_article_token(target_article.lower()) or target_article.lower()
    source_ids = {
        refers_to: ref_id
        for refers_to, ref_id in idx.legal_refs.items()
        if _extract_article_token(ref_id.lower()) == target_token
    }
    statement_ids = {
        tgt_key: source_ids[src_key]
        for src_key, tgt_keys in idx.associations.items()
        if src_key in source_ids
        for tgt_key in tgt_keys
        if tgt_key in idx.statements
    }
    if not statement_ids:
        print(f"[v2] Keine Statements fuer '{target_article}' gefunden.")
        return []

    raw_tasks: list[RawTask] = []
    article_notes: list[str] = []

    for stmt_key, ref_id in statement_ids.items():
        stmt_el = idx.statements[stmt_key]
        human_ref = re.sub(r'GDPR:art_(\d+)', r'Art. \1', ref_id)
        human_ref = re.sub(r'__para_(\d+)', r' Abs. \1', human_ref)
        human_ref = re.sub(r'__content__list_\d+__point_([a-z])', r' lit. \1', human_ref)
        for formula_el in stmt_el.findall(L('ConstitutiveStatement')):
            formula_key = formula_el.get('key', '')
            context_type = idx.formula_contexts.get(formula_key)
            rule = formula_el.find(R('Rule'))
            if rule is None:
                continue
            parsed = _parse_rule(rule, human_ref, context_type=context_type)
            if parsed is not None:
                raw_tasks.append(parsed)
                continue
            _append_unique(article_notes, _extract_article_note(rule, human_ref))

    seen_key: dict[tuple, RawTask] = {}
    for task in raw_tasks:
        post_sig = tuple((action.verb, action.actor, action.recipient, action.refs) for action in task.post_actions)
        branch_sig = tuple(
            (branch.label, tuple((action.verb, action.actor, action.recipient, action.refs) for action in branch.actions))
            for branch in task.branches
        )
        key = (
            task.verb,
            task.negated,
            task.source,
            task.actor,
            task.recipient,
            task.timer,
            tuple(task.conditions),
            post_sig,
            task.gateway_type,
            branch_sig,
        )
        if key not in seen_key:
            seen_key[key] = task
            continue
        existing = seen_key[key]
        for value in task.data_objects:
            _append_unique(existing.data_objects, value)
        for value in task.conditions:
            _append_unique(existing.conditions, value)
        for value in task.notes:
            _append_unique(existing.notes, value)
        for value in task.or_alts:
            _append_unique(existing.or_alts, value)
        for branch in task.branches:
            if not any(existing_branch.label == branch.label for existing_branch in existing.branches):
                existing.branches.append(branch)

    ordered = _topological_sort(list(seen_key.values()))
    processed: list[dict] = []
    current_actor = 'Controller'

    for task in ordered:
        action = _humanize(task.verb)
        if task.negated or task.deontic == 'Prohibited':
            action = f'Do Not {action}'
        if task.has_right or task.deontic in ('Permitted', 'Right'):
            action = f'Can {action}'

        recipient = RECIPIENT_HUMANIZER.get(task.recipient, task.recipient)
        bpmn_type = 'bpmn:sendTask' if 'Notify' in action or task.verb == 'Communicate' else 'bpmn:task'

        if task.actor not in ('System', ''):
            current_actor = task.actor
        actor = current_actor if task.actor in ('System', '') else task.actor

        display_conditions = _simplify_conditions(task.conditions, task.gateway_type)
        notes = list(task.notes)
        if display_conditions:
            _append_unique(notes, f"Applies when: {' AND '.join(display_conditions)}")

        seen_do: set[str] = set()
        data_objects = []
        for item in task.data_objects:
            label = _humanize(item)
            if label and label not in RAW_SKIP_LABELS and label not in seen_do:
                seen_do.add(label)
                data_objects.append(label)

        post_actions = []
        for post_action in task.post_actions:
            post_label = _humanize(post_action.verb)
            if task.has_right or task.deontic in ('Permitted', 'Right'):
                post_label = f'Can {post_label}'
            post_actions.append({
                'action': post_label,
                'actor': post_action.actor or actor,
                'recipient': RECIPIENT_HUMANIZER.get(post_action.recipient, post_action.recipient),
                'data_objects': [_humanize(item) for item in post_action.data_objects if item],
                'bpmn_type': 'bpmn:sendTask' if 'Notify' in post_label or post_action.verb == 'Communicate' else 'bpmn:task',
            })

        if task.timer and any(action.verb == 'LetterReasonFor' for action in task.post_actions):
            base_task = {
                'id': generate_id('Task_'),
                'actor': actor,
                'action': action,
                'recipient': recipient,
                'source': task.source,
                'timer': task.timer,
                'bpmn_type': bpmn_type,
                'data_objects': list(data_objects),
                'notes': [],
            }
            delayed_task = dict(base_task)
            delayed_task['id'] = generate_id('Task_')
            delayed_task['timer'] = None
            delayed_task['notes'] = []
            delayed_followups = []
            for post_action in post_actions:
                if post_action['action'] == 'Provide Reason for Delay':
                    delayed_followups.append({
                        'id': generate_id('Task_'),
                        'actor': post_action['actor'] or actor,
                        'action': post_action['action'],
                        'recipient': post_action.get('recipient'),
                        'source': task.source,
                        'timer': None,
                        'bpmn_type': post_action.get('bpmn_type', 'bpmn:task'),
                        'data_objects': list(post_action.get('data_objects', [])),
                        'notes': [],
                    })
            processed.append({
                'id': generate_id('GatewayTask_'),
                'actor': actor,
                'action': action,
                'recipient': recipient,
                'source': task.source,
                'timer': task.timer,
                'bpmn_type': bpmn_type,
                'gateway_cond': None,
                'gateway_type': 'exclusive',
                'events': [],
                'data_objects': [],
                'or_alternatives': [],
                'post_actions': [],
                'notes': notes,
                'article_notes': [],
                'has_time_bound': True,
                'use_gateway': False,
                'branches': [
                    {'label': _iso_to_deadline_label(task.timer, delayed=False), 'tasks': [base_task]},
                    {'label': _iso_to_deadline_label(task.timer, delayed=True), 'tasks': [delayed_task, *delayed_followups]},
                ],
            })
            continue

        if task.branches:
            branch_specs = []
            for branch in task.branches:
                branch_tasks = []
                for branch_action in branch.actions:
                    branch_label = _humanize(branch_action.verb)
                    branch_tasks.append({
                        'id': generate_id('Task_'),
                        'actor': branch_action.actor or actor,
                        'action': branch_label,
                        'recipient': RECIPIENT_HUMANIZER.get(branch_action.recipient, branch_action.recipient),
                        'source': task.source,
                        'timer': None,
                        'bpmn_type': 'bpmn:sendTask' if 'Notify' in branch_label or branch_action.verb == 'Communicate' else 'bpmn:task',
                        'data_objects': [_humanize(item) for item in branch_action.data_objects if item],
                        'notes': [],
                    })
                if branch_tasks:
                    branch_specs.append({'label': branch.label, 'tasks': branch_tasks})
            if len(branch_specs) >= 2:
                processed.append({
                    'id': generate_id('GatewayTask_'),
                    'actor': actor,
                    'action': action,
                    'recipient': recipient,
                    'source': task.source,
                    'timer': task.timer,
                    'bpmn_type': bpmn_type,
                    'gateway_cond': None,
                    'gateway_type': task.gateway_type,
                    'events': [],
                    'data_objects': data_objects,
                    'or_alternatives': [],
                    'post_actions': post_actions,
                    'notes': notes,
                    'article_notes': [],
                    'has_time_bound': bool(task.timer),
                    'use_gateway': False,
                    'branches': branch_specs,
                })
                continue

        processed.append({
            'id': generate_id('Task_'),
            'actor': actor,
            'action': action,
            'recipient': recipient,
            'source': task.source,
            'timer': task.timer,
            'bpmn_type': bpmn_type,
            'gateway_cond': None,
            'gateway_type': task.gateway_type,
            'events': [],
            'data_objects': data_objects,
            'or_alternatives': [_humanize(item) for item in task.or_alts],
            'post_actions': post_actions,
            'notes': notes,
            'article_notes': [],
            'has_time_bound': bool(task.timer),
            'use_gateway': False,
            'branches': [],
        })

    if processed and article_notes:
        processed[0]['article_notes'] = article_notes

    dedup_processed: dict[tuple, dict] = {}
    for item in processed:
        branch_sig = tuple(
            (branch.get('label'), tuple((task.get('action'), task.get('actor'), task.get('recipient')) for task in branch.get('tasks', [])))
            for branch in item.get('branches', [])
        )
        key = (
            item.get('action'),
            item.get('actor'),
            item.get('recipient'),
            item.get('source'),
            item.get('timer'),
            tuple(item.get('notes', [])),
            branch_sig,
        )
        if key not in dedup_processed:
            dedup_processed[key] = item
            continue
        existing = dedup_processed[key]
        for value in item.get('data_objects', []):
            _append_unique(existing['data_objects'], value)
        for value in item.get('article_notes', []):
            _append_unique(existing['article_notes'], value)
        for value in item.get('or_alternatives', []):
            _append_unique(existing['or_alternatives'], value)

    processed = list(dedup_processed.values())
    if target_article == 'art_33':
        processed = _normalize_article_33(processed)

    print(f"[v2] {len(processed)} Aufgaben extrahiert.")
    return processed


def _topological_sort(tasks: list[RawTask]) -> list[RawTask]:
    if not tasks:
        return tasks
    t2_to_indices: dict[str, list[int]] = defaultdict(list)
    for i, task in enumerate(tasks):
        if task.time_t2:
            t2_to_indices[task.time_t2].append(i)

    in_degree = [0] * len(tasks)
    adj: list[list[int]] = [[] for _ in tasks]
    for i, task in enumerate(tasks):
        if task.time_t1 and task.time_t1 in t2_to_indices:
            for predecessor in t2_to_indices[task.time_t1]:
                if predecessor != i:
                    adj[predecessor].append(i)
                    in_degree[i] += 1

    queue = deque(i for i, degree in enumerate(in_degree) if degree == 0)
    result: list[RawTask] = []
    while queue:
        index = queue.popleft()
        result.append(tasks[index])
        for successor in adj[index]:
            in_degree[successor] -= 1
            if in_degree[successor] == 0:
                queue.append(successor)

    reached = {id(task) for task in result}
    for task in tasks:
        if id(task) not in reached:
            result.append(task)
    return result


def _iso_to_deadline_label(timer: Optional[str], delayed: bool = False) -> str:
    if not timer:
        return 'Delayed' if delayed else 'On Time'
    timer = timer.strip()
    if timer.startswith('PT') and timer.endswith('H'):
        value = timer[2:-1]
        return f"After {value}h" if delayed else f"Within {value}h"
    if timer.startswith('P') and timer.endswith('D'):
        value = timer[1:-1]
        return f"After {value} day(s)" if delayed else f"Within {value} day(s)"
    if timer.startswith('P') and timer.endswith('M'):
        value = timer[1:-1]
        return f"After {value} month(s)" if delayed else f"Within {value} month(s)"
    if timer.startswith('P') and timer.endswith('Y'):
        value = timer[1:-1]
        return f"After {value} year(s)" if delayed else f"Within {value} year(s)"
    return f"After {timer}" if delayed else f"Within {timer}"


def _merge_processed_task(into: dict, other: dict):
    for value in other.get('data_objects', []):
        _append_unique(into['data_objects'], value)
    for value in other.get('notes', []):
        _append_unique(into['notes'], value)
    for value in other.get('article_notes', []):
        _append_unique(into['article_notes'], value)
    for value in other.get('or_alternatives', []):
        _append_unique(into['or_alternatives'], value)


def _normalize_article_33(processed: list[dict]) -> list[dict]:
    remaining: list[dict] = []

    abs1_gateway = next(
        (
            item
            for item in processed
            if item.get('source') == 'Art. 33 Abs. 1' and item.get('branches')
        ),
        None,
    )
    if abs1_gateway is not None:
        absorbed: set[str] = set()
        for item in processed:
            if item is abs1_gateway:
                continue
            if item.get('source') != 'Art. 33 Abs. 1':
                continue
            if item.get('action') != 'Notify' or item.get('recipient') != abs1_gateway.get('recipient'):
                continue
            _merge_processed_task(abs1_gateway, item)
            absorbed.add(item['id'])

        for branch in abs1_gateway.get('branches', []):
            for branch_task in branch.get('tasks', []):
                branch_task['timer'] = None
                for value in abs1_gateway.get('data_objects', []):
                    _append_unique(branch_task['data_objects'], value)
        abs1_gateway['action'] = 'Notify within 72h?'
        abs1_gateway['timer'] = None

        for item in processed:
            if item.get('id') not in absorbed:
                remaining.append(item)
    else:
        remaining = list(processed)

    lit_a_group = [
        item
        for item in remaining
        if item.get('source') == 'Art. 33 Abs. 3 lit. a' and item.get('action') == 'Describe' and not item.get('branches')
    ]
    if len(lit_a_group) > 1:
        merged = lit_a_group[0]
        for item in lit_a_group[1:]:
            _merge_processed_task(merged, item)
        merged['notes'] = [note for note in merged['notes'] if 'AND Describe' not in note]
        remaining = [item for item in remaining if item not in lit_a_group[1:]]

    lit_d_gateway = next(
        (
            item
            for item in remaining
            if item.get('source') == 'Art. 33 Abs. 3 lit. d' and item.get('branches')
        ),
        None,
    )
    if lit_d_gateway is not None:
        absorbed_ids: set[str] = set()
        for item in remaining:
            if item is lit_d_gateway:
                continue
            if item.get('source') != 'Art. 33 Abs. 3 lit. d':
                continue
            if item.get('action') != 'Describe':
                continue
            _merge_processed_task(lit_d_gateway, item)
            absorbed_ids.add(item['id'])
        lit_d_gateway['action'] = 'Describe Measures'
        for branch in lit_d_gateway.get('branches', []):
            label = branch.get('label')
            for branch_task in branch.get('tasks', []):
                branch_task['action'] = f'Describe {label}'
        remaining = [item for item in remaining if item.get('id') not in absorbed_ids]

    return remaining
