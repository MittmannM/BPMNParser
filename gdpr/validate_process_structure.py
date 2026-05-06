from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET


# Directory for the XML output
DEFAULT_MODEL_DIR = Path(r"test_results\test_results_batchsize_4_checkpoint_150_ngram_32")


ERROR_RULE_TYPES = [
    "missing_start_event",
    "missing_end_event",
    "start_event_has_incoming",
    "end_event_has_outgoing",
    "node_not_reachable_from_start",
    "node_cannot_reach_end",
    "task_missing_incoming_or_outgoing",
    "gateway_missing_incoming_or_outgoing",
    "gateway_join_and_split",
    "edge_references_unknown_node",
    "task_multiple_outgoing",
    "task_multiple_incoming",
    "xor_split_not_closed",
    "and_split_not_closed",
    "xml_parse_error",
    "file_read_error",
    "node_missing_id",
    "model_directory_error",
]

WARNING_RULE_TYPES = [
    "edge_missing_id",
]

ALL_RULE_TYPES = ERROR_RULE_TYPES + WARNING_RULE_TYPES


@dataclass(frozen=True)
class Node:
    """A process node used in the directed control-flow graph."""

    id: str
    tag: str
    type: str
    kind: str
    gateway_kind: str | None = None


@dataclass(frozen=True)
class Edge:
    """A sequenceFlow edge between two process nodes."""

    id: str
    source: str
    target: str
    tag: str


@dataclass(frozen=True)
class ValidationIssue:
    """One structural validation issue."""

    severity: str
    rule_type: str
    message: str


@dataclass
class ProcessGraph:
    """Directed graph plus degree information."""

    outgoing: dict[str, list[str]] = field(default_factory=dict)
    incoming: dict[str, list[str]] = field(default_factory=dict)
    outgoing_edges: dict[str, list[Edge]] = field(default_factory=dict)
    incoming_edges: dict[str, list[Edge]] = field(default_factory=dict)


@dataclass
class FileReport:
    """Collected validation result for one XML file."""

    path: Path
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)
    issues: list[ValidationIssue] = field(default_factory=list)
    rule_violations_by_type: dict[str, int] = field(default_factory=dict)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def structural_valid(self) -> bool:
        return not self.errors

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)


def local_name(name: str) -> str:
    """Return the local XML name without an optional namespace."""
    if name.startswith("{"):
        return name.rsplit("}", 1)[-1]
    return name


def get_attribute(element: ET.Element, attribute_name: str) -> str | None:
    """Get an attribute by local name, independent of namespace syntax."""
    for raw_name, value in element.attrib.items():
        if local_name(raw_name) == attribute_name:
            return value
    return None


def issue(severity: str, rule_type: str, message: str) -> ValidationIssue:
    return ValidationIssue(severity=severity, rule_type=rule_type, message=message)


def parse_xml_file(path: Path) -> tuple[ET.Element | None, list[ValidationIssue]]:
    """Parse an XML file and return parse/read errors instead of raising."""
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as error:
        line, column = getattr(error, "position", (None, None))
        if line is not None and column is not None:
            message = f"XML parse error at line {line}, column {column}: {error}"
        else:
            message = f"XML parse error: {error}"
        return None, [issue("error", "xml_parse_error", message)]
    except OSError as error:
        return None, [issue("error", "file_read_error", f"Could not read file: {error}")]

    return root, []


def classify_node(element: ET.Element) -> tuple[str, str | None] | None:
    """Classify XML elements as task, start/end/intermediate event, or gateway."""
    tag = local_name(element.tag)
    lower_tag = tag.lower()
    raw_type = get_attribute(element, "type") or tag
    lower_type = raw_type.lower()

    if lower_tag == "task" or lower_type.endswith("task"):
        return "task", None

    if lower_tag == "event" or lower_type.endswith("event"):
        if "start" in lower_type or lower_tag == "startevent":
            return "start_event", None
        if "end" in lower_type or lower_tag == "endevent":
            return "end_event", None
        return "intermediate_event", None

    if lower_tag == "gateway" or lower_type.endswith("gateway"):
        if "exclusive" in lower_type or lower_type in {"xor", "xorgateway"}:
            return "gateway", "xor"
        if "parallel" in lower_type or lower_type in {"and", "andgateway"}:
            return "gateway", "and"
        if "inclusive" in lower_type or lower_type in {"or", "orgateway"}:
            return "gateway", "or"
        if "eventbased" in lower_type or "event_based" in lower_type:
            return "gateway", "event_based"
        return "gateway", "unknown"

    return None


def extract_nodes_and_edges(
    root: ET.Element,
) -> tuple[dict[str, Node], list[Edge], list[ValidationIssue]]:
    """Extract process nodes and sequenceFlow edges from the XML tree."""
    nodes: dict[str, Node] = {}
    edges: list[Edge] = []
    issues: list[ValidationIssue] = []

    for element in root.iter():
        classification = classify_node(element)
        if classification is None:
            continue

        node_id = (get_attribute(element, "id") or "").strip()
        tag = local_name(element.tag)
        node_type = get_attribute(element, "type") or tag

        if not node_id:
            issues.append(
                issue("error", "node_missing_id", f"{tag} node is missing an id.")
            )
            continue

        kind, gateway_kind = classification
        nodes[node_id] = Node(
            id=node_id,
            tag=tag,
            type=node_type,
            kind=kind,
            gateway_kind=gateway_kind,
        )

    for index, element in enumerate(root.iter(), start=1):
        tag = local_name(element.tag)
        if tag.lower() != "sequenceflow":
            continue

        edge_id = (get_attribute(element, "id") or "").strip()
        source = (
            get_attribute(element, "sourceRef")
            or get_attribute(element, "source")
            or ""
        ).strip()
        target = (
            get_attribute(element, "targetRef")
            or get_attribute(element, "target")
            or ""
        ).strip()

        if not edge_id:
            edge_id = f"<sequenceFlow #{index}>"
            issues.append(
                issue(
                    "warning",
                    "edge_missing_id",
                    f"{edge_id} is missing an id attribute.",
                )
            )

        edges.append(Edge(id=edge_id, source=source, target=target, tag=tag))

    return nodes, edges, issues


def build_graph(nodes: dict[str, Node], edges: list[Edge]) -> ProcessGraph:
    """Build adjacency lists and degree lists from known sequenceFlow endpoints."""
    graph = ProcessGraph(
        outgoing={node_id: [] for node_id in nodes},
        incoming={node_id: [] for node_id in nodes},
        outgoing_edges={node_id: [] for node_id in nodes},
        incoming_edges={node_id: [] for node_id in nodes},
    )

    for edge in edges:
        source_known = edge.source in nodes
        target_known = edge.target in nodes

        # Degree counts use every edge endpoint that points to a known node.
        if source_known:
            graph.outgoing[edge.source].append(edge.target)
            graph.outgoing_edges[edge.source].append(edge)
        if target_known:
            graph.incoming[edge.target].append(edge.source)
            graph.incoming_edges[edge.target].append(edge)

    return graph


def reachable_from(starts: Iterable[str], adjacency: dict[str, list[str]]) -> set[str]:
    """Return nodes reachable through known graph edges."""
    seen: set[str] = set()
    queue = deque(starts)

    while queue:
        current = queue.popleft()
        if current in seen:
            continue
        seen.add(current)

        for next_node in adjacency.get(current, []):
            if next_node not in seen and next_node in adjacency:
                queue.append(next_node)

    return seen


def check_edge_references(
    nodes: dict[str, Node], edges: list[Edge]
) -> list[ValidationIssue]:
    """Check whether every sequenceFlow source and target points to a known node."""
    issues: list[ValidationIssue] = []

    for edge in edges:
        if edge.source not in nodes:
            issues.append(
                issue(
                    "error",
                    "edge_references_unknown_node",
                    f"Edge {edge.id!r} references unknown source node {edge.source!r}.",
                )
            )
        if edge.target not in nodes:
            issues.append(
                issue(
                    "error",
                    "edge_references_unknown_node",
                    f"Edge {edge.id!r} references unknown target node {edge.target!r}.",
                )
            )

    return issues


def all_paths_end_in_end_event(
    start: str,
    nodes: dict[str, Node],
    graph: ProcessGraph,
    visited: set[str] | None = None,
) -> bool:
    """Heuristic check: every path from start must terminate in an EndEvent."""
    if visited is None:
        visited = set()

    node = nodes.get(start)
    if node is None:
        return False
    if node.kind == "end_event":
        return True
    if start in visited:
        return False

    successors = [target for target in graph.outgoing.get(start, []) if target in nodes]
    if not successors:
        return False

    next_visited = set(visited)
    next_visited.add(start)
    return all(
        all_paths_end_in_end_event(successor, nodes, graph, next_visited)
        for successor in successors
    )


def downstream_has_gateway_join(
    split_id: str,
    gateway_kind: str,
    nodes: dict[str, Node],
    graph: ProcessGraph,
) -> bool:
    """Check whether a same-kind join gateway is reachable after a split."""
    start_nodes = [target for target in graph.outgoing.get(split_id, []) if target in nodes]
    downstream = reachable_from(start_nodes, graph.outgoing)

    for node_id in downstream:
        node = nodes[node_id]
        incoming = len(graph.incoming.get(node_id, []))
        outgoing = len(graph.outgoing.get(node_id, []))
        if (
            node.kind == "gateway"
            and node.gateway_kind == gateway_kind
            and incoming > 1
            and outgoing == 1
        ):
            return True

    return False


def check_gateway_closing(
    nodes: dict[str, Node], graph: ProcessGraph
) -> list[ValidationIssue]:
    """Check XOR/AND split closing with a pragmatic downstream heuristic."""
    issues: list[ValidationIssue] = []

    for node in nodes.values():
        if node.kind != "gateway" or node.gateway_kind not in {"xor", "and"}:
            continue

        incoming = len(graph.incoming.get(node.id, []))
        outgoing = len(graph.outgoing.get(node.id, []))
        is_split = incoming == 1 and outgoing > 1
        if not is_split:
            continue

        if downstream_has_gateway_join(node.id, node.gateway_kind, nodes, graph):
            continue

        branch_starts = [target for target in graph.outgoing.get(node.id, []) if target in nodes]
        branches_end = branch_starts and all(
            all_paths_end_in_end_event(branch_start, nodes, graph)
            for branch_start in branch_starts
        )
        if branches_end:
            continue

        if node.gateway_kind == "xor":
            issues.append(
                issue(
                    "error",
                    "xor_split_not_closed",
                    f"XOR split {node.id!r} is not closed by XOR join.",
                )
            )
        else:
            issues.append(
                issue(
                    "error",
                    "and_split_not_closed",
                    f"AND split {node.id!r} is not closed by AND join.",
                )
            )

    return issues


def validate_structure(
    nodes: dict[str, Node], edges: list[Edge], graph: ProcessGraph
) -> list[ValidationIssue]:
    """Run structural process validation rules on the graph."""
    issues: list[ValidationIssue] = []

    start_events = [node for node in nodes.values() if node.kind == "start_event"]
    end_events = [node for node in nodes.values() if node.kind == "end_event"]

    if not start_events:
        issues.append(issue("error", "missing_start_event", "No StartEvent found."))
    if not end_events:
        issues.append(issue("error", "missing_end_event", "No EndEvent found."))

    issues.extend(check_edge_references(nodes, edges))

    for node in nodes.values():
        incoming = len(graph.incoming.get(node.id, []))
        outgoing = len(graph.outgoing.get(node.id, []))

        if node.kind == "start_event" and incoming > 0:
            issues.append(
                issue(
                    "error",
                    "start_event_has_incoming",
                    f"StartEvent {node.id!r} has {incoming} incoming edge(s).",
                )
            )

        if node.kind == "end_event" and outgoing > 0:
            issues.append(
                issue(
                    "error",
                    "end_event_has_outgoing",
                    f"EndEvent {node.id!r} has {outgoing} outgoing edge(s).",
                )
            )

        if node.kind == "task":
            if incoming == 0 or outgoing == 0:
                issues.append(
                    issue(
                        "error",
                        "task_missing_incoming_or_outgoing",
                        f"Task {node.id!r} has incoming={incoming}, outgoing={outgoing}.",
                    )
                )
            if outgoing > 1:
                issues.append(
                    issue(
                        "error",
                        "task_multiple_outgoing",
                        f"Task {node.id!r} has {outgoing} outgoing edge(s).",
                    )
                )
            if incoming > 1:
                issues.append(
                    issue(
                        "error",
                        "task_multiple_incoming",
                        f"Task {node.id!r} has {incoming} incoming edge(s).",
                    )
                )

        if node.kind == "gateway":
            if incoming == 0 or outgoing == 0:
                issues.append(
                    issue(
                        "error",
                        "gateway_missing_incoming_or_outgoing",
                        f"Gateway {node.id!r} has incoming={incoming}, outgoing={outgoing}.",
                    )
                )
            if incoming > 1 and outgoing > 1:
                issues.append(
                    issue(
                        "error",
                        "gateway_join_and_split",
                        f"Gateway {node.id!r} is both join and split "
                        f"(incoming={incoming}, outgoing={outgoing}).",
                    )
                )

    if start_events:
        reachable = reachable_from((node.id for node in start_events), graph.outgoing)
        for node_id in sorted(set(nodes) - reachable):
            issues.append(
                issue(
                    "error",
                    "node_not_reachable_from_start",
                    f"Node {node_id!r} is not reachable from any StartEvent.",
                )
            )

    if end_events:
        can_reach_end = reachable_from((node.id for node in end_events), graph.incoming)
        for node_id in sorted(set(nodes) - can_reach_end):
            issues.append(
                issue(
                    "error",
                    "node_cannot_reach_end",
                    f"Node {node_id!r} cannot reach any EndEvent.",
                )
            )

    issues.extend(check_gateway_closing(nodes, graph))
    return issues


def count_rule_violations(issues: list[ValidationIssue]) -> dict[str, int]:
    """Count issues by rule type and include zero entries for known rules."""
    counts = Counter(issue.rule_type for issue in issues)
    return {rule_type: counts.get(rule_type, 0) for rule_type in ALL_RULE_TYPES}


def validate_file(path: Path) -> FileReport:
    """Validate one XML file without letting errors abort the full run."""
    report = FileReport(path=path)
    root, parse_issues = parse_xml_file(path)
    if root is None:
        report.issues.extend(parse_issues)
        report.rule_violations_by_type = count_rule_violations(report.issues)
        return report

    nodes, edges, extraction_issues = extract_nodes_and_edges(root)
    graph = build_graph(nodes, edges)

    report.nodes = nodes
    report.edges = edges
    report.issues.extend(extraction_issues)
    report.issues.extend(validate_structure(nodes, edges, graph))
    report.rule_violations_by_type = count_rule_violations(report.issues)
    return report


def get_default_xml_files() -> list[Path]:
    """Return all XML files directly inside DEFAULT_MODEL_DIR."""
    if not DEFAULT_MODEL_DIR.exists() or not DEFAULT_MODEL_DIR.is_dir():
        return []
    return sorted(DEFAULT_MODEL_DIR.glob("*.xml"))


def model_directory_error_report() -> FileReport:
    """Create a report when the configured model directory cannot be evaluated."""
    report = FileReport(path=DEFAULT_MODEL_DIR)
    if not DEFAULT_MODEL_DIR.exists():
        message = "Configured model directory does not exist."
    elif not DEFAULT_MODEL_DIR.is_dir():
        message = "Configured model path exists but is not a directory."
    else:
        message = "No XML files found in configured model directory."

    report.issues.append(issue("error", "model_directory_error", message))
    report.rule_violations_by_type = count_rule_violations(report.issues)
    return report


def print_report(report: FileReport) -> None:
    """Print a readable report for one file."""
    print(f"File: {report.path}")
    print(f"Structural valid: {'true' if report.structural_valid else 'false'}")
    print(f"Error count: {report.error_count}")
    print(f"Warning count: {report.warning_count}")

    print("Errors:")
    if report.errors:
        for item in report.errors:
            print(f"- [{item.rule_type}] {item.message}")
    else:
        print("- none")

    print("Warnings:")
    if report.warnings:
        for item in report.warnings:
            print(f"- [{item.rule_type}] {item.message}")
    else:
        print("- none")

    print("Rule violations by type:")
    for rule_type, count in report.rule_violations_by_type.items():
        print(f"- {rule_type}: {count}")
    print()


def print_summary(reports: list[FileReport]) -> None:
    """Print aggregate validation metrics over all files."""
    total = len(reports)
    valid = sum(1 for report in reports if report.structural_valid)
    invalid = total - valid
    total_errors = sum(report.error_count for report in reports)
    total_warnings = sum(report.warning_count for report in reports)

    print("Summary:")
    print(f"Total files checked: {total}")
    print(f"Structurally valid files: {valid}")
    print(f"Structurally invalid files: {invalid}")
    print(f"Total errors: {total_errors}")
    print(f"Total warnings: {total_warnings}")


def main() -> int:
    paths = get_default_xml_files()
    reports = (
        [validate_file(path) for path in paths]
        if paths
        else [model_directory_error_report()]
    )

    for report in reports:
        print_report(report)
    print_summary(reports)

    return 0 if all(report.structural_valid for report in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
