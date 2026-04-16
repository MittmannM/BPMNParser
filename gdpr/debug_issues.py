"""Final check - run multiple articles and summarize results."""
import sys
sys.path.insert(0, '.')
from parser import extract_gdpr_master

articles = ['art_5', 'art_17', 'art_28', 'art_30', 'art_33', 'art_34']
for art in articles:
    tasks = extract_gdpr_master('rioKB_GDPR.xml', art)
    actors = set(t['actor'] for t in tasks)
    print(f"\n{art.upper()} ({len(tasks)} tasks, actors={actors})")
    for t in tasks:
        cond = t['gateway_cond'] or '—'
        print(f"  [{t['actor'][:4]}] {t['action'][:40]:40} | {len(t['data_objects'])} objs | cond: {cond[:60]}")
