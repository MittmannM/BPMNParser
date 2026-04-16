# Sets for structural and deontic analysis
ACTOR_LIST = {'Controller', 'Processor', 'SupervisoryAuthority', 'DataSubject', 'MemberState'}
STRUCTURAL_NS = {'rioOnto', 'swrlb', 'rdfs', 'ruleml'}
DEONTIC_WRAPPERS = {'Obliged', 'Permitted', 'Right', 'Prohibited'}

# Modal helpers: domain verbs that qualify another verb but are NOT primary tasks
MODAL_HELPERS = {'AbleTo', 'nonDelayed', 'possible', 'responsible', 'feasible', 'reasonable'}

# Content verbs: verbs that describe WHAT a document/record must contain — never primary tasks
CONTENT_VERBS = {'Contain', 'Describe', 'CategoryOf', 'allInfoAbout', 'imply'}

# Relation verbs: structural relations in the ontology — skip as data objects
RELATION_VERBS = {
    'isRepresentedBy', 'ResponsibleFor', 'Transmit', 'nominates',
    'isBasedOn', 'RelatedTo', 'partOf', 'cause', 'imply', 'Hold',
    'Execute', 'Request', 'LegalRequirement', 'Marketing', 'publicPowers',
    'Purpose', 'PersonalDataProcessing'
}

# True process-triggering events
EVENT_TRIGGERS = {
    'DataBreach', 'AwareOf', 'Request', 'PersonalDataProcessing',
    'Complaint', 'ReceiveFrom', 'Execute', 'Lodge'
}

# Structures namespace concepts that are not domain actions
STRUCTURAL_THEN = STRUCTURAL_NS | {
    'nonDelayed', 'LetterReasonFor', 'Define',
    'RexistAtTime', 'AbleTo', 'writtenForm', 'electronicForm'
}

# Mapping for human-friendly labels
HUMANIZER = {
    "Communicate'": "Notify", "Communicate": "Notify",
    "LetterReasonFor": "Provide Reason for Delay",
    "Document'": "Document", "Document": "Document",
    "ComplyWith": "Comply With Obligations",
    "Verify": "Verify",
    "DataBreach": "Data Breach Detected",
    "AwareOf": "Became Aware of Breach", "AwareOf'": "Became Aware of Breach",
    "PersonalDataProcessing": "Personal Data Processing",
    "PersonalDataProcessing'": "Personal Data Processing",
    "Measure": "Measures Taken/Proposed",
    "TakenToAddress": "Measures Already Taken",
    "ProposedToAddress": "Measures Proposed",
    "natureOf": "Nature of Breach",
    "dpoOrCP": "Contact Details (DPO/CP)", "dpoOrCp": "Contact Details (DPO/CP)",
    "imply": "Likely Consequences",
    "contactDetails": "Contact Details",
    "Risk": "High Risk to Individuals",
    "likely": "Likely to Result in Risk",
    "riskinessRightsFreedoms": "Risk to Rights and Freedoms",
    "feasible": "Feasible",
    "nominates": "Processor Nominates Controller",
    "allInfoAbout": "All Info About the Breach",
    "SupervisoryAuthority": "Supervisory Authority",
    "Delete": "Erase Personal Data",
    "Rectify": "Rectify Data",
    "Access": "Provide Data Access",
    "Lodge": "Lodge Complaint",
    "ReceiveFrom": "Receive Communication",
    "Charge": "Charge Fee",
    "WithdrawConsent": "Withdraw Consent",
    "Register": "Maintain Processing Record",
    "WriteIn": "Record Processing Activity",
    "Implement": "Implement Measure",
}

COND_HUMANIZER = {
    "Risk": "High Risk to Individuals",
    "likely": "Likely to Cause Risk",
    "riskinessRightsFreedoms": "Risk to Rights & Freedoms",
    "Person": "Natural Person Affected",
    "nominates": "Processor Nominates Representative",
    "feasible": "Notification Feasible",
    "NOT Possible": "NOT all info available yet",
}

RECIPIENT_HUMANIZER = {
    'SupervisoryAuthority': 'Supervisory Authority',
    'Controller': 'Controller',
    'Processor': 'Processor',
    'DataSubject': 'Data Subject',
}

RAW_SKIP_LABELS = {
    'Describe', "Describe'", 'Contain', "Contain'", 'and', 'or', 'System', 'partOf',
    'Notify', 'Document', 'Verify', 'Comply With Obligations', 'Provide Reason for Delay',
    "Communicate'", "Communicate", "LetterReasonFor", "ComplyWith", "Document'", "Verify",
    'Define',
}
