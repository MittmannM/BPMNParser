from pathlib import Path
import json
import re

articles_dir = Path("gdpr_articles")
process_format_dir = Path("gdpr_process_format")
output_dir = Path("training_data_LLM_format")


SYSTEM_PROMPT = """ You convert the text of one legal article into a legally faithful, process-oriented XML process model.

Use only the legal text provided by the user as the semantic source. Do not invent steps, actors, deadlines, exceptions, or legal assumptions that are not grounded in the text.

Output only valid XML with exactly one root element <processModel>.
"""

USER_PROMPT = """Generate a process-structure XML for the following article.

Model the legally relevant process logic, including triggers, obligations, exceptions, alternatives, deadlines, follow-up duties, actor interactions, and legally relevant cross-references where present.

Use concise task names. Use question-style names for exclusive gateways. Label exclusive outgoing flows explicitly where appropriate.

Return only XML using this top-level section order:
<pools>
<lanes />
<tasks>
<events>
<gateways>
<sequenceFlows>
<messageFlows>
<dataObjects />
<dataStores />
<dataAssociations />
<annotations />
<associations />

Legal text:
"""

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

    files = {}
    for path in directory.glob(f"*{suffix}"):

        article_id = extract_article_id(path.name)

        if article_id is None:
            print(f"Warning: Could not extract article ID from filename '{path.name}'. Skipping this file.")
            continue

        if article_id in files:
            print(f"Warning: Duplicate article ID '{article_id}' found in filename '{path.name}'. Skipping this file.")
            continue

        files[article_id] = path

    return files
                    
def main():

    txt_files = collect_files(articles_dir, ".txt")
    xml_files = collect_files(process_format_dir, ".xml")

    txt_keys = set(txt_files.keys())
    xml_keys = set(xml_files.keys())
    
    common_keys = sorted(txt_keys & xml_keys)
    missing_xml = sorted(txt_keys - xml_keys)
    missing_txt = sorted(xml_keys - txt_keys)

    if missing_xml:
        print(f"Warning: {len(missing_xml)} .txt files have no corresponding .xml files:")
        for key in missing_xml:
            print(f"  - {key}.txt")
    
    if missing_txt:
        print(f"Warning: {len(missing_txt)} .xml files have no corresponding .txt files:")
        for key in missing_txt:
            print(f"  - {key}.xml")

    records = []
    
    for article_id in common_keys:

        txt_content = read_text(txt_files[article_id])
        xml_content = read_text(xml_files[article_id])

        record = {
            "messages": [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": USER_PROMPT + "\n\n" + txt_content
                },
                {
                    "role": "assistant",
                    "content": xml_content
                }
            ]
        }
        records.append(record)
    
    with output_dir.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"{len(records)} pairs written to {output_dir}")


if __name__ == "__main__":
    main()
