import re

def extract_xml(xml_path, target_article="art_33"):
    try:
        with open(xml_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading: {e}")
        return

    legal_refs = re.findall(r'<lrml:LegalReference[^>]+>', content)
    source_ids = {re.search(r'refersTo="([^"]+)"', r).group(1): re.search(r'refID="([^"]+)"', r).group(1) 
                  for r in legal_refs if target_article.lower() in r.lower() and re.search(r'refersTo="([^"]+)"', r)}
    
    assoc_blocks = re.findall(r'<lrml:Association>(.*?)</lrml:Association>', content, re.DOTALL | re.IGNORECASE)
    statement_ids = {}
    for block in assoc_blocks:
        src = re.search(r'appliesSource[^>]*keyref="#([^"]+)"', block)
        tgt = re.search(r'toTarget[^>]*keyref="#([^"]+)"', block)
        if src and tgt and src.group(1) in source_ids:
            statement_ids[tgt.group(1)] = source_ids[src.group(1)]

    for stmt_id, human_ref in statement_ids.items():
        start_idx = content.find(f'<lrml:Statements key="{stmt_id}">')
        if start_idx == -1: continue
        end_idx = content.find('</lrml:Statements>', start_idx)
        print("="*80)
        print(f"Statement ID: {stmt_id} / Reference: {human_ref}")
        print("="*80)
        print(content[start_idx:end_idx + 18])

if __name__ == "__main__":
    extract_xml("rioKB_GDPR.xml")
