from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from transformers import AutoTokenizer


SYSTEM_PROMPT = """Convert one legal article into a faithful XML process model.
Use only the provided legal text.
Do not invent legal logic.
Output only valid XML with root <processModel>."""


USER_PROMPT = """Generate process-structure XML from this legal text.
Model only process-relevant legal logic.
Use short task names, question-style exclusive gateways, and labeled exclusive branches.
Use this exact top-level order:
<pools><lanes /><tasks><events><gateways><sequenceFlows><messageFlows><dataObjects /><dataStores /><dataAssociations /><annotations /><associations />
Text:"""


DEFAULT_TOKENIZER_ID = "google/gemma-4-e2b-it"


def parse_args() -> argparse.Namespace:
    script_path = Path(__file__).resolve()
    project_root = script_path.parents[1]

    parser = argparse.ArgumentParser(
        description=(
            "Converts GDPR-Articles and XML-Process Models into a properly formatted Prompt-Completion-JSONL for Gemma 4 2B."
        )
    )
    parser.add_argument(
        "--articles-dir",
        type=Path,
        default=project_root / "gdpr_articles",
        help="Folder with the GDPR article texts.",
    )
    parser.add_argument(
        "--process-dir",
        type=Path,
        default=project_root / "gdpr_process_format",
        help="Folder with the XML-process models.",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=project_root / "training_data_LLM_format",
        help="Target file for the preprocessed JSONL.",
    )
    parser.add_argument(
        "--tokenizer-id",
        type=str,
        default=DEFAULT_TOKENIZER_ID,
        help="Gemma-4-2B-Tokenizer for the official Chat-Template-Formating.",
    )
    parser.add_argument(
        "--local-files-only",
        action="store_true",
        help="Loads the tokenizer only from the local cache.",
    )
    return parser.parse_args()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def extract_article_id(filename: str) -> str | None:
    patterns = [
        r"article_(\d+)",
        r"art_(\d+)",
    ]

    lower_name = filename.lower()
    for pattern in patterns:
        match = re.search(pattern, lower_name)
        if match:
            return match.group(1)

    return None


def collect_files(directory: Path, suffix: str) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for path in sorted(directory.glob(f"*{suffix}")):
        article_id = extract_article_id(path.name)
        if article_id is None:
            print(f"Warning: Could not extract article ID from '{path.name}'. Skipping.")
            continue

        if article_id in files:
            print(f"Warning: Duplicate article ID '{article_id}' in '{path.name}'. Skipping.")
            continue

        files[article_id] = path

    return files


def normalize_xml(xml_text: str) -> str:
    xml_text = xml_text.strip()
    if not xml_text:
        raise ValueError("XML output is empty.")

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ValueError(f"Invalid XML encountered: {exc}") from exc

    if root.tag != "processModel":
        raise ValueError(f"Expected XML root <processModel>, got <{root.tag}>.")

    return xml_text


def build_messages(article_text: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT.strip()},
        {"role": "user", "content": USER_PROMPT.strip() + "\n\n" + article_text.strip()},
        {"role": "assistant", "content": ""},
    ]


def render_prompt_completion(tokenizer, source_messages: list[dict[str, str]], assistant_text: str) -> tuple[str, str, str]:
    full_messages = [*source_messages[:-1], {"role": "assistant", "content": assistant_text}]

    prompt_text = tokenizer.apply_chat_template(
        source_messages[:-1],
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    full_text = tokenizer.apply_chat_template(
        full_messages,
        tokenize=False,
        add_generation_prompt=False,
        enable_thinking=False,
    )

    if not full_text.startswith(prompt_text):
        raise ValueError("Gemma prompt/completion split failed because full_text does not start with prompt_text.")

    completion_text = full_text[len(prompt_text):]
    if not completion_text.strip():
        raise ValueError("Assistant completion is empty after template rendering.")

    return prompt_text, completion_text, full_text


def token_count(tokenizer, text: str) -> int:
    return len(tokenizer(text, add_special_tokens=False)["input_ids"])


def to_project_relative_path(path: Path, project_root: Path) -> str:
    return path.resolve().relative_to(project_root.resolve()).as_posix()


def main() -> None:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]

    articles_dir = args.articles_dir.resolve()
    process_dir = args.process_dir.resolve()
    output_file = args.output_file.resolve()

    if not articles_dir.exists():
        raise FileNotFoundError(f"Articles directory not found: {articles_dir}")
    if not process_dir.exists():
        raise FileNotFoundError(f"Process directory not found: {process_dir}")

    print(f"Loading tokenizer: {args.tokenizer_id}")
    tokenizer = AutoTokenizer.from_pretrained(
        args.tokenizer_id,
        use_fast=True,
        local_files_only=args.local_files_only,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    txt_files = collect_files(articles_dir, ".txt")
    xml_files = collect_files(process_dir, ".xml")

    txt_keys = set(txt_files)
    xml_keys = set(xml_files)

    common_keys = sorted(txt_keys & xml_keys, key=lambda value: int(value))
    missing_xml = sorted(txt_keys - xml_keys, key=lambda value: int(value))
    missing_txt = sorted(xml_keys - txt_keys, key=lambda value: int(value))

    if missing_xml:
        print(f"Warning: {len(missing_xml)} article text files have no matching XML file:")
        for key in missing_xml:
            print(f"  - article_{key}.txt")

    if missing_txt:
        print(f"Warning: {len(missing_txt)} XML files have no matching article text file:")
        for key in missing_txt:
            print(f"  - article {key}")

    records: list[dict[str, object]] = []

    for article_id in common_keys:
        article_path = txt_files[article_id]
        process_path = xml_files[article_id]

        article_text = read_text(article_path)
        xml_text = normalize_xml(read_text(process_path))

        source_messages = build_messages(article_text)
        prompt_text, completion_text, full_text = render_prompt_completion(
            tokenizer=tokenizer,
            source_messages=source_messages,
            assistant_text=xml_text,
        )

        record = {
            "article_id": article_id,
            "article_path": to_project_relative_path(article_path, project_root),
            "process_path": to_project_relative_path(process_path, project_root),
            "source_messages": [
                source_messages[0],
                source_messages[1],
                {"role": "assistant", "content": xml_text},
            ],
            "prompt": prompt_text,
            "completion": completion_text,
            "full_text": full_text,
            "prompt_token_count": token_count(tokenizer, prompt_text),
            "completion_token_count": token_count(tokenizer, completion_text),
            "full_text_token_count": token_count(tokenizer, full_text),
        }
        records.append(record)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Wrote {len(records)} records to {output_file}")

    if records:
        token_lengths = [record["full_text_token_count"] for record in records]
        print(
            "Token stats:",
            f"min={min(token_lengths)}",
            f"median={sorted(token_lengths)[len(token_lengths) // 2]}",
            f"max={max(token_lengths)}",
        )
        print("Sample article_id:", records[0]["article_id"])


if __name__ == "__main__":
    main()
