import copy
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


LRML_NS = 'http://docs.oasis-open.org/legalruleml/ns/v1.0/'


def L(local: str) -> str:
    return f'{{{LRML_NS}}}{local}'


def extract_article_token(ref_id: str) -> str | None:
    match = re.search(r'art_(\d+)', ref_id.lower())
    if not match:
        return None
    return f"art_{int(match.group(1))}"


def local_name(tag: str) -> str:
    return tag.rsplit('}', 1)[-1] if '}' in tag else tag


@dataclass
class NodeMeta:
    element: ET.Element
    kind: str
    self_ids: set[str]
    ref_ids: set[str]


def collect_namespaces(xml_path: Path) -> dict[str, str]:
    namespaces: dict[str, str] = {}
    for _, data in ET.iterparse(xml_path, events=('start-ns',)):
        prefix, uri = data
        if prefix not in namespaces:
            namespaces[prefix] = uri
            ET.register_namespace(prefix, uri)
    return namespaces


def collect_ids(element: ET.Element) -> tuple[set[str], set[str]]:
    self_ids: set[str] = set()
    ref_ids: set[str] = set()
    for elem in element.iter():
        key = elem.get('key')
        if key:
            self_ids.add(key.lstrip('#'))
        keyref = elem.get('keyref')
        if keyref:
            ref_ids.add(keyref.lstrip('#'))
    if local_name(element.tag) == 'LegalReference':
        refers_to = element.get('refersTo')
        if refers_to:
            self_ids.add(refers_to.lstrip('#'))
    return self_ids, ref_ids


def build_node_metadata(root: ET.Element) -> tuple[list[ET.Element], list[NodeMeta], list[NodeMeta], list[NodeMeta], list[NodeMeta]]:
    prefixes = [copy.deepcopy(child) for child in list(root) if local_name(child.tag) == 'Prefix']

    legal_ref_nodes: list[NodeMeta] = []
    legal_refs_wrapper = root.find(L('LegalReferences'))
    if legal_refs_wrapper is not None:
        for legal_ref in list(legal_refs_wrapper):
            self_ids, ref_ids = collect_ids(legal_ref)
            legal_ref_nodes.append(NodeMeta(legal_ref, 'LegalReference', self_ids, ref_ids))

    association_nodes: list[NodeMeta] = []
    associations_wrapper = root.find(L('Associations'))
    if associations_wrapper is not None:
        for association in list(associations_wrapper):
            self_ids, ref_ids = collect_ids(association)
            association_nodes.append(NodeMeta(association, 'Association', self_ids, ref_ids))

    context_nodes: list[NodeMeta] = []
    statement_nodes: list[NodeMeta] = []
    for child in list(root):
        kind = local_name(child.tag)
        if kind == 'Context':
            self_ids, ref_ids = collect_ids(child)
            context_nodes.append(NodeMeta(child, kind, self_ids, ref_ids))
        elif kind == 'Statements':
            self_ids, ref_ids = collect_ids(child)
            statement_nodes.append(NodeMeta(child, kind, self_ids, ref_ids))

    return prefixes, legal_ref_nodes, association_nodes, context_nodes, statement_nodes


def included_formula_ids(statement_elements: list[ET.Element]) -> set[str]:
    formula_ids: set[str] = set()
    for stmt in statement_elements:
        for elem in stmt.iter():
            key = elem.get('key')
            if key and key.startswith('statements'):
                formula_ids.add(key)
    return formula_ids


def clone_context_for_formulas(context_el: ET.Element, formula_ids: set[str]) -> ET.Element | None:
    cloned = copy.deepcopy(context_el)
    keep_any = False
    for in_scope in list(cloned):
        if local_name(in_scope.tag) != 'inScope':
            continue
        keyref = in_scope.get('keyref', '').lstrip('#')
        if keyref not in formula_ids:
            cloned.remove(in_scope)
        else:
            keep_any = True
    return cloned if keep_any else None


def extract_article_file(
    root: ET.Element,
    prefixes: list[ET.Element],
    legal_ref_nodes: list[NodeMeta],
    association_nodes: list[NodeMeta],
    context_nodes: list[NodeMeta],
    statement_nodes: list[NodeMeta],
    article_token: str,
    output_dir: Path,
):
    seed_nodes = [
        meta
        for meta in legal_ref_nodes
        if extract_article_token(meta.element.get('refID', '')) == article_token
    ]
    if not seed_nodes:
        return

    included_legal_refs: list[NodeMeta] = list(seed_nodes)
    legal_ref_ids: set[str] = set()
    for meta in seed_nodes:
        legal_ref_ids.update(meta.self_ids)

    included_associations = [
        meta for meta in association_nodes if meta.ref_ids & legal_ref_ids
    ]
    statement_ids: set[str] = set()
    for meta in included_associations:
        statement_ids.update(meta.ref_ids)

    included_statements = [
        meta for meta in statement_nodes if meta.self_ids & statement_ids
    ]

    statement_elements = [meta.element for meta in included_statements]
    formula_ids = included_formula_ids(statement_elements)
    included_contexts = [
        meta for meta in context_nodes if meta.ref_ids & formula_ids
    ]

    article_root = ET.Element(root.tag, root.attrib)
    for prefix in prefixes:
        article_root.append(copy.deepcopy(prefix))

    refs_wrapper = ET.Element(L('LegalReferences'))
    for meta in legal_ref_nodes:
        if meta in included_legal_refs:
            refs_wrapper.append(copy.deepcopy(meta.element))
    if len(refs_wrapper):
        article_root.append(refs_wrapper)

    assoc_wrapper = ET.Element(L('Associations'))
    for meta in association_nodes:
        if meta in included_associations:
            assoc_wrapper.append(copy.deepcopy(meta.element))
    if len(assoc_wrapper):
        article_root.append(assoc_wrapper)

    for meta in context_nodes:
        if meta not in included_contexts:
            continue
        cloned_context = clone_context_for_formulas(meta.element, formula_ids)
        if cloned_context is not None:
            article_root.append(cloned_context)

    for meta in statement_nodes:
        if meta in included_statements:
            article_root.append(copy.deepcopy(meta.element))

    output_path = output_dir / f'{article_token}.xml'
    ET.ElementTree(article_root).write(output_path, encoding='utf-8', xml_declaration=True)


def main():
    base_dir = Path(__file__).resolve().parent
    source_path = base_dir / 'rioKB_GDPR.xml'
    output_dir = base_dir / 'artikel'
    output_dir.mkdir(exist_ok=True)

    collect_namespaces(source_path)
    tree = ET.parse(source_path)
    root = tree.getroot()
    prefixes, legal_ref_nodes, association_nodes, context_nodes, statement_nodes = build_node_metadata(root)

    article_tokens = sorted(
        {
            token
            for meta in legal_ref_nodes
            if (token := extract_article_token(meta.element.get('refID', '')))
        },
        key=lambda token: int(token.split('_')[1]),
    )

    for article_token in article_tokens:
        extract_article_file(
            root,
            prefixes,
            legal_ref_nodes,
            association_nodes,
            context_nodes,
            statement_nodes,
            article_token,
            output_dir,
        )

    print(f'Created {len(article_tokens)} article XML files in {output_dir}')


if __name__ == '__main__':
    main()
