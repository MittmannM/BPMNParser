import os

from generator_v2_impl import generate_bpmn_master
from parser_v3_impl import extract_gdpr_structural

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    xml_input_path = os.path.join(script_dir, "rioKB_GDPR.xml")
    output_dir = os.path.join(script_dir, "output_v2")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Testing a subset of articles as requested
    for target_article in ["art_17", "art_33", "art_82"]:
        output_filename = os.path.join(output_dir, f"GDPR_{target_article}_v2.bpmn")
        print(f"\n--- {target_article} (v2) ---")
        tasks = extract_gdpr_structural(xml_input_path, target_article=target_article)
        generate_bpmn_master(tasks, output_filename)

if __name__ == "__main__":
    main()
