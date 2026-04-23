from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import xml.etree.ElementTree as ET


NS = {
    "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
}


@dataclass
class BpmnValidationReport:
    path: str
    ok: bool
    warnings: list[str]
    stats: dict[str, int]

    def to_dict(self) -> dict:
        return asdict(self)


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def validate_bpmn_file(path: str | Path) -> BpmnValidationReport:
    file_path = Path(path)
    warnings: list[str] = []
    stats = {
        "participants": 0,
        "processes": 0,
        "tasks": 0,
        "events": 0,
        "gateways": 0,
        "message_flows": 0,
        "sequence_flows": 0,
    }

    try:
        tree = ET.parse(file_path)
    except ET.ParseError as exc:
        return BpmnValidationReport(
            path=str(file_path),
            ok=False,
            warnings=[f"XML parse error: {exc}"],
            stats=stats,
        )

    root = tree.getroot()
    definitions_name = _local_name(root.tag)
    if definitions_name != "definitions":
        warnings.append("Root element is not bpmn:definitions.")

    ids: set[str] = set()
    for elem in root.iter():
        elem_id = elem.get("id")
        if not elem_id:
            continue
        if elem_id in ids:
            warnings.append(f"Duplicate id detected: {elem_id}")
        ids.add(elem_id)

    participants = root.findall(".//bpmn:participant", NS)
    processes = root.findall(".//bpmn:process", NS)
    message_flows = root.findall(".//bpmn:messageFlow", NS)
    sequence_flows = root.findall(".//bpmn:sequenceFlow", NS)
    stats["participants"] = len(participants)
    stats["processes"] = len(processes)
    stats["message_flows"] = len(message_flows)
    stats["sequence_flows"] = len(sequence_flows)

    process_ids = {process.get("id") for process in processes if process.get("id")}
    for participant in participants:
        process_ref = participant.get("processRef")
        if process_ref and process_ref not in process_ids:
            warnings.append(
                f"Participant '{participant.get('name', participant.get('id', '?'))}' references missing process '{process_ref}'."
            )

    for process in processes:
        process_name = process.get("name") or process.get("id") or "unnamed process"

        start_events = [el for el in process if _local_name(el.tag).endswith("Event") and _local_name(el.tag) == "startEvent"]
        end_events = [el for el in process if _local_name(el.tag).endswith("Event") and _local_name(el.tag) == "endEvent"]
        if not start_events:
            warnings.append(f"{process_name}: no start event.")
        if not end_events:
            warnings.append(f"{process_name}: no end event.")

        flow_nodes = []
        gateways = []
        for elem in process:
            local = _local_name(elem.tag)
            if local.endswith("Task"):
                stats["tasks"] += 1
                flow_nodes.append(elem)
            elif local.endswith("Event"):
                stats["events"] += 1
                flow_nodes.append(elem)
            elif local.endswith("Gateway"):
                stats["gateways"] += 1
                gateways.append(elem)
                flow_nodes.append(elem)

        for node in flow_nodes:
            local = _local_name(node.tag)
            node_id = node.get("id", "?")
            name = (node.get("name") or "").strip()
            if local.endswith("Task") and not name:
                warnings.append(f"{process_name}: task '{node_id}' is unnamed.")
            if local in {"startEvent", "endEvent", "intermediateCatchEvent", "intermediateThrowEvent"} and not name:
                warnings.append(f"{process_name}: event '{node_id}' is unnamed.")

        outgoing_by_source: dict[str, list[ET.Element]] = {}
        incoming_by_target: dict[str, list[ET.Element]] = {}
        for flow in sequence_flows:
            source_ref = flow.get("sourceRef")
            target_ref = flow.get("targetRef")
            if source_ref:
                outgoing_by_source.setdefault(source_ref, []).append(flow)
            if target_ref:
                incoming_by_target.setdefault(target_ref, []).append(flow)

        for gateway in gateways:
            gateway_id = gateway.get("id", "?")
            gateway_name = (gateway.get("name") or "").strip()
            local = _local_name(gateway.tag)
            outgoing = outgoing_by_source.get(gateway_id, [])
            incoming = incoming_by_target.get(gateway_id, [])

            is_join = len(incoming) > 1 and len(outgoing) <= 1
            is_split = len(outgoing) > 1

            if local == "exclusiveGateway" and is_split:
                if not gateway_name:
                    warnings.append(f"{process_name}: diverging exclusive gateway '{gateway_id}' should be named as a question.")
                elif not gateway_name.endswith("?"):
                    warnings.append(f"{process_name}: exclusive gateway '{gateway_id}' should end with '?'.")
                for flow in outgoing:
                    if not (flow.get("name") or "").strip():
                        warnings.append(
                            f"{process_name}: outgoing flow '{flow.get('id', '?')}' from exclusive gateway '{gateway_id}' is unnamed."
                        )
            if local == "parallelGateway" and is_split and gateway_name:
                warnings.append(f"{process_name}: diverging parallel gateway '{gateway_id}' should usually stay unnamed.")
            if is_join and gateway_name:
                warnings.append(f"{process_name}: join gateway '{gateway_id}' should usually stay unnamed.")

    ok = not warnings
    return BpmnValidationReport(
        path=str(file_path),
        ok=ok,
        warnings=warnings,
        stats=stats,
    )
