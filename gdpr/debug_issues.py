"""Inspect statement type encoding and lrml:Context / appliesModality."""
import xml.etree.ElementTree as ET

LRML   = 'http://docs.oasis-open.org/legalruleml/ns/v1.0/'
RULEML = 'http://ruleml.org/spec'

tree = ET.parse('rioKB_GDPR.xml')
root = tree.getroot()

DEONTIC_IRIS = {
    'rioOnto:Obliged', 'rioOnto:Permitted', 'rioOnto:Right', 'rioOnto:Prohibited',
}

# Check what's inside a Statements element and its ConstitutiveStatements
# Look for statement 'statements269' (art_82)
for stmt in root.iter(f'{{{LRML}}}Statements'):
    if stmt.get('key') != 'statements269':
        continue
    print(f"Statements key: {stmt.get('key')}")
    for child in stmt:
        print(f"  Child tag: {child.tag} | key={child.get('key')}")
        # Check appliesModality
        for mod in child.iter(f'{{{LRML}}}appliesModality'):
            print(f"    appliesModality: {mod.get('keyref') or mod.text}")
        # Check Context
        for ctx in child.iter(f'{{{LRML}}}Context'):
            print(f"    Context key: {ctx.get('key')}")
        # Check deontic atoms in the THEN block
        for rule in child.iter(f'{{{RULEML}}}Rule'):
            then = rule.find(f'{{{RULEML}}}then')
            if then is None: continue
            for atom in then.iter(f'{{{RULEML}}}Atom'):
                rel = atom.find(f'{{{RULEML}}}Rel')
                if rel is not None and rel.get('iri') in DEONTIC_IRIS:
                    keyrefs = [v.get('keyref') for v in atom if v.get('keyref')]
                    keys    = [v.get('key') for v in atom if v.get('key')]
                    print(f"    DEONTIC: {rel.get('iri')} | keyrefs={keyrefs} | keys={keys}")
    break

# Also check: does rioOnto:and appear as a tag directly, or only in iri attr?
print('\n--- Checking rioOnto:and structure ---')
for stmt in root.iter(f'{{{LRML}}}Statements'):
    if stmt.get('key') != 'statements269':
        continue
    for rule in stmt.iter(f'{{{RULEML}}}Rule'):
        then = rule.find(f'{{{RULEML}}}then')
        if then is None: continue
        print("THEN block atoms:")
        for atom in then.iter(f'{{{RULEML}}}Atom'):
            rel = atom.find(f'{{{RULEML}}}Rel')
            if rel is not None:
                iri = rel.get('iri', '')
                keyrefs = [v.get('keyref') for v in atom.iter(f'{{{RULEML}}}Var') if v.get('keyref')]
                keys    = [v.get('key')    for v in atom.iter(f'{{{RULEML}}}Var') if v.get('key')]
                funs    = [f.get('iri') for f in atom.iter(f'{{{RULEML}}}Fun')]
                print(f"  Atom iri={iri!r:50s} keys={keys} refs={keyrefs} funs={funs}")
        break
    break

# Also check IF block of same rule for the After + RexistAtTime
print('\n--- IF block of statements269 rule 1 ---')
count = 0
for stmt in root.iter(f'{{{LRML}}}Statements'):
    if stmt.get('key') != 'statements269':
        continue
    for rule in stmt.iter(f'{{{RULEML}}}Rule'):
        count += 1
        if count < 2: continue
        iff = rule.find(f'{{{RULEML}}}if')
        if iff is None: continue
        for atom in iff.iter(f'{{{RULEML}}}Atom'):
            rel = atom.find(f'{{{RULEML}}}Rel')
            if rel is not None:
                iri     = rel.get('iri', '')
                keyrefs = [v.get('keyref') for v in atom.iter(f'{{{RULEML}}}Var') if v.get('keyref')]
                keys    = [v.get('key')    for v in atom.iter(f'{{{RULEML}}}Var') if v.get('key')]
                print(f"  IF Atom iri={iri!r:50s} keys={keys} refs={keyrefs}")
        # Also check Naf
        for naf in iff.iter(f'{{{RULEML}}}Naf'):
            print(f"  NAF found!")
            for atom in naf.iter(f'{{{RULEML}}}Atom'):
                rel = atom.find(f'{{{RULEML}}}Rel')
                if rel is not None:
                    print(f"    NAF Atom: {rel.get('iri')}")
        break
    break
