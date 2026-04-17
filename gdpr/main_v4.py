import os

from generator_v4_impl import generate_bpmn_master
from parser_v4_impl import extract_gdpr_structural

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    xml_input_path = os.path.join(script_dir, "rioKB_GDPR.xml")
    output_dir = os.path.join(script_dir, "output_v4")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for target_article in ["art_6", "art_18", "art_24", "art_33", "art_43", "art_49", "art_82"]:
        output_filename = os.path.join(output_dir, f"GDPR_{target_article}_v4.bpmn")
        print(f"\n--- {target_article} (v4) ---")
        tasks = extract_gdpr_structural(xml_input_path, target_article=target_article)
        generate_bpmn_master(tasks, output_filename)

if __name__ == "__main__":
    main()
