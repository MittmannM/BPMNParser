from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Iterable
import xml.etree.ElementTree as ET


BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"

TASK_TAGS = {
    "task",
    "userTask",
    "serviceTask",
    "manualTask",
    "sendTask",
    "receiveTask",
    "scriptTask",
    "businessRuleTask",
    "callActivity",
    "subProcess",
}
EVENT_TAGS = {
    "startEvent",
    "endEvent",
    "intermediateCatchEvent",
    "intermediateThrowEvent",
    "boundaryEvent",
}
GATEWAY_TAGS = {
    "exclusiveGateway",
    "parallelGateway",
    "inclusiveGateway",
    "eventBasedGateway",
}
EVENT_DEFINITION_TAGS = {
    "messageEventDefinition": "message",
    "timerEventDefinition": "timer",
    "errorEventDefinition": "error",
    "signalEventDefinition": "signal",
    "escalationEventDefinition": "escalation",
    "conditionalEventDefinition": "conditional",
    "terminateEventDefinition": "terminate",
    "compensateEventDefinition": "compensation",
    "linkEventDefinition": "link",
    "cancelEventDefinition": "cancel",
}
SECTION_ORDER = [
    "pools",
    "lanes",
    "tasks",
    "events",
    "gateways",
    "sequenceFlows",
    "messageFlows",
    "dataObjects",
    "dataStores",
    "dataAssociations",
    "annotations",
    "associations",
]

PROJECT_ROOT = Path(__file__).resolve().parent
INPUT_DIR = PROJECT_ROOT / "bpmn_models"
OUTPUT_DIR = PROJECT_ROOT / "gdpr_process_format"
INPUT_PATTERN = "*reviewed*.bpmn"


def local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def normalize_reference(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    collapsed = " ".join(value.split())
    return collapsed or None


def text_content(element: ET.Element) -> str | None:
    return normalize_text("".join(element.itertext()))


def ordered_attributes(*pairs: tuple[str, str | None]) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for key, value in pairs:
        if value is not None:
            attrs[key] = value
    return attrs


def nearest_ancestor(
    element: ET.Element,
    parent_map: dict[ET.Element, ET.Element],
    tag_name: str,
) -> ET.Element | None:
    current = parent_map.get(element)
    while current is not None:
        if local_name(current.tag) == tag_name:
            return current
        current = parent_map.get(current)
    return None


def lane_depth(element: ET.Element, parent_map: dict[ET.Element, ET.Element]) -> int:
    depth = 0
    current = parent_map.get(element)
    while current is not None:
        if local_name(current.tag) == "lane":
            depth += 1
        current = parent_map.get(current)
    return depth


def process_context_ref(
    element: ET.Element,
    parent_map: dict[ET.Element, ET.Element],
    process_to_participants: dict[str, list[str]],
) -> str | None:
    process = nearest_ancestor(element, parent_map, "process")
    if process is None:
        return None

    process_id = normalize_reference(process.get("id"))
    if process_id is None:
        return None

    participants = [participant_id for participant_id in process_to_participants.get(process_id, []) if participant_id]
    if len(participants) == 1:
        return participants[0]
    return process_id


def resolve_lane_ref(
    element: ET.Element,
    parent_map: dict[ET.Element, ET.Element],
    flow_node_to_lane: dict[str, tuple[str, int]],
) -> str | None:
    current: ET.Element | None = element
    while current is not None:
        element_id = normalize_reference(current.get("id"))
        if element_id and element_id in flow_node_to_lane:
            return flow_node_to_lane[element_id][0]
        if local_name(current.tag) == "process":
            break
        current = parent_map.get(current)
    return None


def detect_event_definition(event_element: ET.Element) -> str | None:
    found: list[str] = []
    for child in event_element:
        definition = EVENT_DEFINITION_TAGS.get(local_name(child.tag))
        if definition and definition not in found:
            found.append(definition)
    if not found:
        return None
    return " ".join(found)


def child_texts(element: ET.Element, child_tag_name: str) -> list[str]:
    values: list[str] = []
    for child in element:
        if local_name(child.tag) != child_tag_name:
            continue
        value = text_content(child)
        if value:
            values.append(value)
    return values


def sort_records(records: Iterable[tuple[str, dict[str, str]]]) -> list[tuple[str, dict[str, str]]]:
    def key(item: tuple[str, dict[str, str]]) -> tuple[str | int, ...]:
        tag_name, attrs = item
        element_id = attrs.get("id")
        if element_id is not None:
            return (0, element_id, tag_name)
        return (
            1,
            tag_name,
            attrs.get("name", ""),
            attrs.get("sourceRef", ""),
            attrs.get("targetRef", ""),
            attrs.get("dataObjectRef", ""),
            attrs.get("dataStoreRef", ""),
            attrs.get("text", ""),
        )

    return sorted(records, key=key)


def extract_semantic_sections(source_path: Path) -> dict[str, list[tuple[str, dict[str, str]]]]:
    tree = ET.parse(source_path)
    root = tree.getroot()
    parent_map = {child: parent for parent in root.iter() for child in parent}

    sections: dict[str, list[tuple[str, dict[str, str]]]] = {section: [] for section in SECTION_ORDER}
    process_to_participants: dict[str, list[str]] = defaultdict(list)
    process_ids: set[str] = set()

    for element in root.iter():
        if local_name(element.tag) != "process":
            continue
        process_id = normalize_reference(element.get("id"))
        if process_id:
            process_ids.add(process_id)

    for element in root.iter():
        if local_name(element.tag) != "participant":
            continue

        participant_id = normalize_reference(element.get("id"))
        process_ref = normalize_reference(element.get("processRef"))
        if process_ref and participant_id:
            process_to_participants[process_ref].append(participant_id)

        pool_type = "active" if process_ref else "passive"
        sections["pools"].append(
            (
                "pool",
                ordered_attributes(
                    ("id", participant_id),
                    ("name", element.get("name")),
                    ("poolType", pool_type),
                    ("processRef", process_ref),
                ),
            )
        )

    flow_node_to_lane: dict[str, tuple[str, int]] = {}
    for element in root.iter():
        if local_name(element.tag) != "lane":
            continue

        lane_id = normalize_reference(element.get("id"))
        parent_lane = nearest_ancestor(element, parent_map, "lane")
        parent_lane_ref = normalize_reference(parent_lane.get("id")) if parent_lane is not None else None
        pool_ref = process_context_ref(element, parent_map, process_to_participants)

        sections["lanes"].append(
            (
                "lane",
                ordered_attributes(
                    ("id", lane_id),
                    ("name", element.get("name")),
                    ("poolRef", pool_ref),
                    ("parentLaneRef", parent_lane_ref),
                ),
            )
        )

        if lane_id is None:
            continue

        depth = lane_depth(element, parent_map)
        for flow_node_ref in child_texts(element, "flowNodeRef"):
            existing = flow_node_to_lane.get(flow_node_ref)
            if existing is None or depth >= existing[1]:
                flow_node_to_lane[flow_node_ref] = (lane_id, depth)

    for element in root.iter():
        name = local_name(element.tag)
        element_id = normalize_reference(element.get("id"))

        if name in TASK_TAGS:
            sections["tasks"].append(
                (
                    "task",
                    ordered_attributes(
                        ("id", element_id),
                        ("name", element.get("name")),
                        ("type", name if name != "subProcess" else "subProcess"),
                        ("poolRef", process_context_ref(element, parent_map, process_to_participants)),
                        ("laneRef", resolve_lane_ref(element, parent_map, flow_node_to_lane)),
                        ("calledElement", normalize_reference(element.get("calledElement"))),
                    ),
                )
            )
            continue

        if name in EVENT_TAGS:
            cancel_activity = normalize_reference(element.get("cancelActivity"))
            if cancel_activity is not None:
                cancel_activity = cancel_activity.lower()

            sections["events"].append(
                (
                    "event",
                    ordered_attributes(
                        ("id", element_id),
                        ("name", element.get("name")),
                        ("type", name),
                        ("poolRef", process_context_ref(element, parent_map, process_to_participants)),
                        ("laneRef", resolve_lane_ref(element, parent_map, flow_node_to_lane)),
                        ("eventDefinition", detect_event_definition(element)),
                        ("attachedToRef", normalize_reference(element.get("attachedToRef"))),
                        ("cancelActivity", cancel_activity),
                    ),
                )
            )
            continue

        if name in GATEWAY_TAGS:
            sections["gateways"].append(
                (
                    "gateway",
                    ordered_attributes(
                        ("id", element_id),
                        ("name", element.get("name")),
                        ("type", name),
                        ("poolRef", process_context_ref(element, parent_map, process_to_participants)),
                        ("laneRef", resolve_lane_ref(element, parent_map, flow_node_to_lane)),
                        ("defaultFlowRef", normalize_reference(element.get("default"))),
                    ),
                )
            )
            continue

        if name == "sequenceFlow":
            condition = None
            for child in element:
                if local_name(child.tag) == "conditionExpression":
                    condition = text_content(child)
                    break

            sections["sequenceFlows"].append(
                (
                    "sequenceFlow",
                    ordered_attributes(
                        ("id", element_id),
                        ("name", element.get("name")),
                        ("sourceRef", normalize_reference(element.get("sourceRef"))),
                        ("targetRef", normalize_reference(element.get("targetRef"))),
                        ("condition", condition),
                    ),
                )
            )
            continue

        if name == "messageFlow":
            sections["messageFlows"].append(
                (
                    "messageFlow",
                    ordered_attributes(
                        ("id", element_id),
                        ("name", element.get("name")),
                        ("sourceRef", normalize_reference(element.get("sourceRef"))),
                        ("targetRef", normalize_reference(element.get("targetRef"))),
                    ),
                )
            )
            continue

        if name == "dataObject":
            sections["dataObjects"].append(
                (
                    "dataObject",
                    ordered_attributes(
                        ("id", element_id),
                        ("name", element.get("name")),
                    ),
                )
            )
            continue

        if name == "dataObjectReference":
            sections["dataObjects"].append(
                (
                    "dataObjectReference",
                    ordered_attributes(
                        ("id", element_id),
                        ("name", element.get("name")),
                        ("dataObjectRef", normalize_reference(element.get("dataObjectRef"))),
                    ),
                )
            )
            continue

        if name == "dataStore":
            sections["dataStores"].append(
                (
                    "dataStore",
                    ordered_attributes(
                        ("id", element_id),
                        ("name", element.get("name")),
                    ),
                )
            )
            continue

        if name == "dataStoreReference":
            sections["dataStores"].append(
                (
                    "dataStoreReference",
                    ordered_attributes(
                        ("id", element_id),
                        ("name", element.get("name")),
                        ("dataStoreRef", normalize_reference(element.get("dataStoreRef"))),
                    ),
                )
            )
            continue

        if name in {"dataInputAssociation", "dataOutputAssociation"}:
            source_refs = child_texts(element, "sourceRef")
            target_refs = child_texts(element, "targetRef")
            sections["dataAssociations"].append(
                (
                    name,
                    ordered_attributes(
                        ("id", element_id),
                        ("sourceRef", " ".join(source_refs) if source_refs else None),
                        ("targetRef", " ".join(target_refs) if target_refs else None),
                    ),
                )
            )
            continue

        if name == "textAnnotation":
            annotation_text = None
            for child in element:
                if local_name(child.tag) == "text":
                    annotation_text = text_content(child)
                    break

            sections["annotations"].append(
                (
                    "textAnnotation",
                    ordered_attributes(
                        ("id", element_id),
                        ("text", annotation_text),
                    ),
                )
            )
            continue

        if name == "association":
            sections["associations"].append(
                (
                    "association",
                    ordered_attributes(
                        ("id", element_id),
                        ("sourceRef", normalize_reference(element.get("sourceRef"))),
                        ("targetRef", normalize_reference(element.get("targetRef"))),
                        ("associationDirection", normalize_reference(element.get("associationDirection"))),
                    ),
                )
            )

    pool_ids = {
        attrs["id"]
        for _, attrs in sections["pools"]
        if "id" in attrs
    }
    lane_ids = {
        attrs["id"]
        for _, attrs in sections["lanes"]
        if "id" in attrs
    }
    flow_node_ids = {
        attrs["id"]
        for section_name in ("tasks", "events", "gateways")
        for _, attrs in sections[section_name]
        if "id" in attrs
    }
    data_object_ids = {
        attrs["id"]
        for tag_name, attrs in sections["dataObjects"]
        if tag_name == "dataObject" and "id" in attrs
    }
    data_store_ids = {
        attrs["id"]
        for tag_name, attrs in sections["dataStores"]
        if tag_name == "dataStore" and "id" in attrs
    }
    referenceable_ids = {
        attrs["id"]
        for section_name in ("pools", "lanes", "tasks", "events", "gateways", "dataObjects", "dataStores", "annotations")
        for _, attrs in sections[section_name]
        if "id" in attrs
    }

    cleaned_lanes: list[tuple[str, dict[str, str]]] = []
    for tag_name, attrs in sections["lanes"]:
        if attrs.get("poolRef") is not None and attrs["poolRef"] not in pool_ids and attrs["poolRef"] not in process_ids:
            attrs = dict(attrs)
            attrs.pop("poolRef", None)
        if attrs.get("parentLaneRef") is not None and attrs["parentLaneRef"] not in lane_ids:
            attrs = dict(attrs)
            attrs.pop("parentLaneRef", None)
        cleaned_lanes.append((tag_name, attrs))
    sections["lanes"] = cleaned_lanes

    for section_name in ("tasks", "events", "gateways"):
        cleaned_section: list[tuple[str, dict[str, str]]] = []
        for tag_name, attrs in sections[section_name]:
            cleaned = dict(attrs)
            pool_ref = cleaned.get("poolRef")
            if pool_ref is not None and pool_ref not in pool_ids and pool_ref not in process_ids:
                cleaned.pop("poolRef", None)

            lane_ref = cleaned.get("laneRef")
            if lane_ref is not None and lane_ref not in lane_ids:
                cleaned.pop("laneRef", None)

            if section_name == "events":
                attached_to_ref = cleaned.get("attachedToRef")
                if attached_to_ref is not None and attached_to_ref not in flow_node_ids:
                    cleaned.pop("attachedToRef", None)

            cleaned_section.append((tag_name, cleaned))
        sections[section_name] = cleaned_section

    sections["sequenceFlows"] = [
        (tag_name, attrs)
        for tag_name, attrs in sections["sequenceFlows"]
        if attrs.get("sourceRef") in flow_node_ids and attrs.get("targetRef") in flow_node_ids
    ]
    kept_sequence_flow_ids = {
        attrs["id"]
        for _, attrs in sections["sequenceFlows"]
        if "id" in attrs
    }

    cleaned_gateways: list[tuple[str, dict[str, str]]] = []
    for tag_name, attrs in sections["gateways"]:
        cleaned = dict(attrs)
        default_flow_ref = cleaned.get("defaultFlowRef")
        if default_flow_ref is not None and default_flow_ref not in kept_sequence_flow_ids:
            cleaned.pop("defaultFlowRef", None)
        cleaned_gateways.append((tag_name, cleaned))
    sections["gateways"] = cleaned_gateways

    sections["messageFlows"] = [
        (tag_name, attrs)
        for tag_name, attrs in sections["messageFlows"]
        if attrs.get("sourceRef") in referenceable_ids and attrs.get("targetRef") in referenceable_ids
    ]

    cleaned_data_objects: list[tuple[str, dict[str, str]]] = []
    for tag_name, attrs in sections["dataObjects"]:
        cleaned = dict(attrs)
        if tag_name == "dataObjectReference":
            data_object_ref = cleaned.get("dataObjectRef")
            if data_object_ref is not None and data_object_ref not in data_object_ids:
                cleaned.pop("dataObjectRef", None)
        cleaned_data_objects.append((tag_name, cleaned))
    sections["dataObjects"] = cleaned_data_objects

    cleaned_data_stores: list[tuple[str, dict[str, str]]] = []
    for tag_name, attrs in sections["dataStores"]:
        cleaned = dict(attrs)
        if tag_name == "dataStoreReference":
            data_store_ref = cleaned.get("dataStoreRef")
            if data_store_ref is not None and data_store_ref not in data_store_ids:
                cleaned.pop("dataStoreRef", None)
        cleaned_data_stores.append((tag_name, cleaned))
    sections["dataStores"] = cleaned_data_stores

    sections["associations"] = [
        (tag_name, attrs)
        for tag_name, attrs in sections["associations"]
        if attrs.get("sourceRef") in referenceable_ids and attrs.get("targetRef") in referenceable_ids
    ]

    return sections


def build_output_tree(sections: dict[str, list[tuple[str, dict[str, str]]]]) -> ET.ElementTree:
    root = ET.Element("processModel")
    for section_name in SECTION_ORDER:
        section_element = ET.SubElement(root, section_name)
        for tag_name, attrs in sort_records(sections[section_name]):
            ET.SubElement(section_element, tag_name, attrs)

    ET.indent(root, space="  ")
    return ET.ElementTree(root)


def convert_file(source_path: Path, output_path: Path) -> None:
    sections = extract_semantic_sections(source_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tree = build_output_tree(sections)
    tree.write(output_path, encoding="utf-8", xml_declaration=True, short_empty_elements=True)


def convert_directory(input_dir: Path, output_dir: Path, pattern: str) -> int:
    source_files = sorted(path for path in input_dir.glob(pattern) if path.is_file())
    if not source_files:
        raise FileNotFoundError(f"No files matched pattern '{pattern}' in {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    for source_path in source_files:
        output_path = output_dir / f"{source_path.stem}.xml"
        convert_file(source_path, output_path)

    return len(source_files)


def main() -> None:
    converted = convert_directory(INPUT_DIR, OUTPUT_DIR, INPUT_PATTERN)
    print(
        f"Converted {converted} BPMN files from {INPUT_DIR.resolve()} "
        f"to {OUTPUT_DIR.resolve()}"
    )


if __name__ == "__main__":
    main()
