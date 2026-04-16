import os
from parser import extract_gdpr_master
from generator import generate_bpmn_master

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    xml_input_path = os.path.join(script_dir, "rioKB_GDPR.xml")
    output_dir = os.path.join(script_dir, "output")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for target_article in ["art_28", "art_33", "art_30", "art_17", "art_34", "art_82"]:
        output_filename = os.path.join(output_dir, f"GDPR_{target_article}.bpmn")
        print(f"\n--- {target_article} ---")
        tasks = extract_gdpr_master(xml_input_path, target_article=target_article)
        generate_bpmn_master(tasks, output_filename)

if __name__ == "__main__":
    main()
