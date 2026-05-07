from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET


# Directory for the XML output
DEFAULT_MODEL_DIR = Path(r"test_results\test_results_batchsize_8_checkpoint_100")
REFERENCE_ATTRIBUTES = {"sourceRef","targetRef"}

@dataclass
class ValidationResult:
    """Collected validation outcome for one XML file."""

    path: Path
    parseable: bool = False
    single_root: bool = False
    errors: list[str] = field(default_factory=list)
    failing_lines: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """A file is valid if it passes all mandatory step-1 checks."""
        return self.parseable and self.single_root and not self.errors

def local_name(name: str) -> str:
    """Return the local part of an XML tag or attribute name.
    """
    if name.startswith("{"):
        return name.rsplit("}", 1)[-1]
    return name


def element_label(element: ET.Element) -> str:
    """Return a readable element label for diagnostics."""
    tag = local_name(element.tag)
    element_id = get_attribute(element, "id")
    if element_id is not None:
        return f"<{tag} id={element_id!r}>"
    return f"<{tag}>"


def get_attribute(element: ET.Element, attribute_name: str) -> str | None:
    """Get an attribute by local name, independent of XML namespace syntax."""
    for raw_name, value in element.attrib.items():
        if local_name(raw_name) == attribute_name:
            return value
    return None


def iter_attributes_by_local_name(
    element: ET.Element, attribute_names: set[str]
) -> Iterable[tuple[str, str]]:
    """Yield matching attributes as (local_name, value) pairs."""
    for raw_name, value in element.attrib.items():
        name = local_name(raw_name)
        if name in attribute_names:
            yield name, value


def parse_error_message(error: ET.ParseError) -> str:
    """Format ElementTree parse errors with line and column when available."""
    line, column = getattr(error, "position", (None, None))
    if line is not None and column is not None:
        return f"XML parse error at line {line}, column {column}: {error}"
    return f"XML parse error: {error}"


def parse_error_context(data: bytes, error: ET.ParseError) -> list[str]:
    """Return the XML line around a parse error with a column marker."""
    line, column = getattr(error, "position", (None, None))
    if line is None:
        return []

    text = data.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    if not lines:
        return [f"line {line}: <no content available>"]
    if line < 1:
        return []
    if line > len(lines):
        return [f"line {line}: <end of file>"]

    result: list[str] = []
    start = max(1, line - 1)
    end = min(len(lines), line + 1)

    for line_number in range(start, end + 1):
        prefix = f"line {line_number}: "
        result.append(f"{prefix}{lines[line_number - 1]}")
        if line_number == line and column is not None:
            result.append(" " * (len(prefix) + max(column, 0)) + "^")

    return result


def attribute_value_context(
    data: bytes, attribute_name: str, attribute_value: str
) -> list[str]:
    """Return XML lines that contain a specific attribute value."""
    text = data.decode("utf-8-sig", errors="replace")
    pattern = re.compile(
        rf"(?:^|[\s<])(?:[\w.-]+:)?{re.escape(attribute_name)}\s*=\s*"
        r"(['\"])(.*?)\1"
    )
    result: list[str] = []

    for line_number, line in enumerate(text.splitlines(), start=1):
        for match in pattern.finditer(line):
            if match.group(2).strip() != attribute_value.strip():
                continue

            prefix = f"line {line_number}: "
            result.append(f"{prefix}{line}")
            result.append(" " * (len(prefix) + match.start(2)) + "^")

    return result


def add_failing_lines(result: ValidationResult, lines: Iterable[str]) -> None:
    """Add diagnostic lines without repeating identical output."""
    for line in lines:
        if line not in result.failing_lines:
            result.failing_lines.append(line)


def validate_file(path: Path) -> ValidationResult:
    """Validate one XML file and collect errors without raising."""
    result = ValidationResult(path=path)

    try:

        data = path.read_bytes()
    except OSError as error:
        result.errors.append(f"Could not read file: {error}")
        return result
    
    try:
        root = ET.fromstring(data)
    except ET.ParseError as error:
        result.errors.append(parse_error_message(error))
        add_failing_lines(result, parse_error_context(data, error))
        return result

    result.parseable = True
    result.single_root = True

    ids_by_value: dict[str, ET.Element] = {}

    for element in root.iter():
        raw_id = get_attribute(element, "id")
        if raw_id is not None:
            normalized_id = raw_id.strip()
            if not normalized_id:
                result.errors.append(f"Empty id attribute on {element_label(element)}.")
                add_failing_lines(result, attribute_value_context(data, "id", raw_id))
            else:
                previous = ids_by_value.get(normalized_id)
                if previous is not None:
                    result.errors.append(
                        f"Duplicate id {normalized_id!r} on "
                        f"{element_label(element)}; first seen on "
                        f"{element_label(previous)}."
                    )
                    add_failing_lines(result, attribute_value_context(data, "id", raw_id))
                else:
                    ids_by_value[normalized_id] = element

    known_ids = set(ids_by_value)

    for element in root.iter():
        for attribute_name, raw_reference in iter_attributes_by_local_name(
            element, REFERENCE_ATTRIBUTES
        ):
            reference = raw_reference.strip()
            if not reference:
                result.errors.append(
                    f"Empty {attribute_name} reference on {element_label(element)}."
                )
                add_failing_lines(
                    result, attribute_value_context(data, attribute_name, raw_reference)
                )
                continue

            if reference not in known_ids:
                result.errors.append(
                    f"{attribute_name} reference {reference!r} on "
                    f"{element_label(element)} does not point to an existing id."
                )
                add_failing_lines(
                    result, attribute_value_context(data, attribute_name, raw_reference)
                )

    return result


def get_default_xml_files() -> list[Path]:
    """Return all XML files inside DEFAULT_MODEL_DIR."""
    if not DEFAULT_MODEL_DIR.exists() or not DEFAULT_MODEL_DIR.is_dir():
        return []

    return sorted(DEFAULT_MODEL_DIR.glob("*.xml"))


def print_file_report(result: ValidationResult) -> None:
    """Print a report for one file."""
    print(f"File: {result.path}")
    print(f"Parseable XML: {'yes' if result.parseable else 'no'}")
    print(f"Single root element: {'yes' if result.single_root else 'no'}")
    print(f"Valid: {'yes' if result.is_valid else 'no'}")
    print("Errors:")
    if result.errors:
        for error in result.errors:
            print(f"- {error}")
    else:
        print("- none")

    if result.failing_lines:
        print("Failing XML lines:")
        for line in result.failing_lines:
            print(line)

    print()


def print_summary(results: list[ValidationResult]) -> None:
    """Print aggregate validation counts."""
    total = len(results)
    valid = sum(1 for result in results if result.is_valid)
    invalid = total - valid

    print("Summary:")
    print(f"Total files checked: {total}")
    print(f"Valid XML files: {valid}")
    print(f"Invalid XML files: {invalid}")


def main() -> int:
    paths = get_default_xml_files()
    results = (
        [validate_file(path) for path in paths]
    )

    for result in results:
        print_file_report(result)

    print_summary(results)

    return 0 if all(result.is_valid for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
