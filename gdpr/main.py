import os
from parser import extract_gdpr_master
from generator import generate_bpmn_master

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    xml_input_path = os.path.join(script_dir, "rioKB_GDPR.xml")
    if not os.path.exists(xml_input_path):
        xml_input_path = os.path.join(script_dir, "..", "..", "rioKB_GDPR.xml") # check if it's elsewhere
    
    if not os.path.exists(xml_input_path):
        # Fallback to the previous logic if it's still not found
        xml_input_path = "rioKB_GDPR.xml"
        if not os.path.exists(xml_input_path):
             xml_input_path = os.path.join("daprecokb", "gdpr", "rioKB_GDPR.xml")

    if not os.path.exists(xml_input_path):
        print(f"❌ Eingabedatei nicht gefunden: {xml_input_path}")
        return

    # Create output directory relative to script
    output_dir = os.path.join(script_dir, "output")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    target_article = "art_28"
    output_filename = os.path.join(output_dir, f"GDPR_{target_article}.bpmn")

    print(f"Starte Refactored Parser für {target_article}...")
    
    # 1. Extraction / Parsing
    tasks = extract_gdpr_master(xml_input_path, target_article=target_article)
    
    # 2. Generation
    generate_bpmn_master(tasks, output_filename)
    
    print("\nFertig! Das Modell wurde erfolgreich erstellt.")

if __name__ == "__main__":
    main()
