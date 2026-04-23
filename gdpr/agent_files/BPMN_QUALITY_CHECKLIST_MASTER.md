# BPMN Quality Checklist

This file is the binding reminder and checklist for all future manual BPMN conversions of GDPR articles in this project.

It serves two purposes:

1. It records the project-specific rules that emerged during the collaboration.
2. It serves as the final check immediately before delivering any new `*_reviewed.bpmn`.

## Binding Project Rules

- The XML files in the `artikel/` folder remain unchanged.
- The BPMN files are stored in the `bpmn/` folder.
- Manually reviewed final results use the naming scheme `GDPR_art_<n>_reviewed.bpmn`.
- Batch-generated BPMN files do not count as final results and are not a semantic source.
- Every reviewed BPMN is derived directly from the real English text of the respective GDPR article.
- Before finishing any new reviewed file, this checklist must be fully reviewed.

## Source Rule and Handling of the XML Files

- The article XML files in the `artikel/` folder remain archived and unchanged, but they are no longer a semantic source.
- Only the real English legal text of the respective GDPR article is authoritative for modeling.
- If old XML-based models, notes, or references conflict with the legal text, the legal text always prevails.
- Visible cross-references to other articles or paragraphs should remain visible in the BPMN when they explain or limit the legal flow in the real article text.
- When modeling, what matters is not an older formalization but the normative effect of the real article:
  - obligation
  - exception
  - alternative
  - follow-up duty
  - condition
  - deadline
  - involvement of other actors

## General Modeling Principle

- The goal is not a generic diagram, but a legally usable process model.
- The BPMN must represent the process-relevant logic of the article.
- Not every logical statement in the legal text needs its own BPMN element.
- Only elements that are relevant to the legal or decision flow should be modeled.

## Hard BPMN 2.0 Requirements

These points must always be satisfied.

- The file must be well-formed XML.
- The root element must be `bpmn:definitions`.
- All IDs must be unique.
- Every participant `processRef` must point to an existing process.
- Every process needs at least one start event.
- Every process needs at least one end event.
- `sequenceFlow` may only run within the same process.
- `messageFlow` may only be used between participants or between activities and other participants, never as a substitute for internal control flow.
- Any element referenced in the `sourceRef` or `targetRef` of a flow must exist.
- The BPMN file must be structured so that common BPMN tools can open it.
- Therefore, a reviewed file must be not only semantically correct, but also technically importable.

## Technical File Requirements for This Project

- Reviewed BPMN files should contain the usual BPMN namespaces:
  - `xmlns:bpmn`
  - `xmlns:bpmndi`
  - `xmlns:dc`
  - `xmlns:di`
- Reviewed files should contain a diagram with BPMN-DI:
  - `bpmndi:BPMNDiagram`
  - `bpmndi:BPMNPlane`
  - `bpmndi:BPMNShape`
  - `bpmndi:BPMNEdge`
- If a file is XML-valid but cannot be opened in the modeler, it is not finished.
- The diagram geometry must be set so that all visible elements lie within their pools or lanes.
- No process end may visually extend outside the pool.

## Pools, Participants, and Collaboration

- Pools are used when the article describes real interaction between actors.
- External actors may be modeled as black-box participants when their internal flow is not relevant for the article.
- Typical external actors are:
  - Supervisory Authority
  - Data Subject
  - Public
  - DPO, when only an advisory or communication relationship is modeled
- A separate expanded process for an external participant is only created if that participant’s internal flow is necessary for the article.
- A controller-internal flow should not be artificially split across multiple pools.

## Sequence Flow and Message Flow

- `sequenceFlow` connects only elements within the same process.
- `messageFlow` connects communication between participants.
- Communicative actions should be modeled as `sendTask` when the activity is genuinely the sending of a communication.
- Purely internal processing steps should remain normal `task` elements.
- Activities should not be used as a substitute for a decision gateway when only one of several follow-up paths is intended.
- If the same duty has effect in two different context paths, it is often cleaner to duplicate the activity per path instead of building one single task with ambiguous merge-and-split behavior.
- A flow must not be modeled as a message flow only because it sounds communicative; what matters is whether another participant is actually being addressed.

## Gateways

- Diverging exclusive gateways must be named as questions.
- These questions must end with `?`.
- Outgoing paths from such gateways must have explicit labels, usually `Yes` and `No`.
- Even if one path seems like a default path that simply continues straight to the next task, it must still exist as a separate visible outgoing flow and be clearly labeled.
- Join gateways should normally remain unnamed.
- Diverging parallel gateways should normally remain unnamed.
- Exclusive gateways are used for decisions, alternatives, exceptions, and yes-no checks.
- Parallel gateways are used when multiple required content elements or sub-activities must be assembled together.

## Naming Conventions

- Activities are named in a clear verb-noun form.
- Activity names should be as short and quickly readable as possible, ideally as a concise verb-object or verb-noun phrase rather than a full sentence.
- Names should describe what happens functionally, not merely refer to the article.
- Good examples:
  - `Assess risk to rights and freedoms`
  - `Provide DPO or contact point details`
  - `Notify supervisory authority`
- Overly long full-sentence task labels should be avoided even when they are semantically correct.
- If a longer legal meaning is important, the task should be named briefly and the precision should be expressed through gateway questions, documentation, or end events.
- Bad examples:
  - `Document information`
  - `Handle case`
  - `Art. 35 step 1`
- Gateways are formulated as questions.
- End events should have meaningful result names, for example:
  - `No direct data subject communication required`
  - `DPIA handling completed`

## Modeling Style for Legal Norms

- Triggers, conditions, and exceptions must appear as understandable decision logic.
- Deadlines must become visible as their own assessment or processing block when they are legally significant.
- Required contents of a notice or assessment should be modeled as sub-tasks when this is important for the quality of the process picture.
- Recurring or follow-up duties should appear as their own follow-up path.
- If a norm provides a substitute measure instead of the standard measure, this should be modeled as its own alternative path.

## Handling Exceptions

- Exceptions must not be hidden in the text of a task if they change the process flow.
- A legally relevant exception will usually receive:
  - an assessment activity, or
  - a gateway
- Conditions such as `if designated`, `if requested`, or similar yes-no dependencies should not be hidden only in a task name when they create different follow-up paths.
- If multiple exceptions lead to the same legal consequence, they may lead one after another to the same end or follow-up path.
- If an exception only triggers a special case of the same duty, it should be modeled as a clear alternative path.

## Handling Required Content

- If an article specifies required contents of a communication, assessment, or documentation, it must be checked whether these should be modeled as:
  - individual tasks
  - parallel collection tasks
  - or one combined activity
- The level of detail should be high enough to keep the legal structure visible.
- At the same time, the model should not be unnecessarily atomized.

## Documentation and Annotation

- `bpmn:documentation` may be used to briefly record the semantic derivation of a reviewed model.
- Documentation should mainly help where:
  - several paragraph parts or sentences are mapped together onto one BPMN path
  - a cross-reference article is made visible in the flow
  - an exception or substitute measure is modeled
- Use text annotations only when they truly help the reader.
- Annotations are not a substitute for clean modeling.

## Layout Rules

- All visible elements must lie within the correct pool.
- An end event must not visually stand outside its pool.
- Visible diagram elements must not overlap.
- This applies in particular to tasks, events, gateways, text annotations, notes, and their label area.
- Notes or other annotations must not be placed on top of tasks or other BPMN elements.
- Sequence flows to end events must dock cleanly; the last waypoint must not be set so that the arrow visibly extends too far into the end event.
- Message flows should be as clear and non-misleading as possible.
- The main flow should be readable from left to right whenever possible.
- Exception and alternative paths may branch upward or downward, but should remain readable.
- Parallel content collections should visually appear as one coherent block.

## Quality Standard Derived from Prior Reviews

The following points have already been explicitly identified as desired or necessary:

- Art. 33 is the qualitative reference standard.
- Art. 34 and the following articles should be modeled at the same level.
- Question gateways with `Yes` and `No` are mandatory where decisions diverge.
- Communication to other actors should be modeled as `sendTask`.
- Reviewed files must be openable in BPMN tools.
- Visual pool boundaries must be correct.
- Automatically generated diagrams must not be adopted without review.

## Recommended Workflow per Article

1. Read the real English text of the GDPR article.
2. Mark explicit cross-references, conditions, and legal consequences.
3. Break the normative logic into these categories:
   - trigger
   - obligation
   - exception
   - alternative
   - deadline
   - follow-up duty
   - involved actors
4. Decide whether a collaboration is useful.
5. Model the BPMN manually.
6. Before finishing, go through the complete checklist.
7. Perform XML validation.
8. Keep technical openability and layout quality in mind, especially BPMN-DI and pool boundaries.

## Final Check Before Delivery

This list must be actively checked before every new reviewed file is delivered.

- Was the article XML left unchanged?
- Was the BPMN file saved as a new `*_reviewed.bpmn`?
- Was the semantic logic derived directly from the real English legal text?
- Are explicit cross-references from the article visibly preserved where they matter for the legal flow?
- Are obligations, exceptions, and alternatives correctly represented in the process flow?
- Are the correct participants modeled?
- Are external interactions modeled as message flows rather than sequence flows?
- Are genuine communications modeled as `sendTask`?
- Does no activity have multiple outgoing paths when those are actually meant as alternatives rather than parallel continuations?
- Do all diverging exclusive gateways have question names ending with `?`?
- Do the outgoing paths of such gateways have labels such as `Yes` and `No`?
- Is the apparently straight default path of a gateway also explicitly visible as a `Yes` or `No` flow rather than being only implicit?
- Are join gateways unnamed unless there is a special reason to name them?
- Are parallel gateways unnamed unless there is a special reason to name them?
- Are conditional meanings not hidden only in task names when a gateway with an explicit `No` continuation path would be needed instead?
- Are the activity names functionally clear and in verb-noun form?
- Is there at least one start event and one end event?
- Are all IDs unique?
- Is the file XML-valid?
- Does the file contain BPMN-DI so that it opens in the modeler?
- Do all visible elements lie within the correct pools?
- Does no end event or task visually extend outside a pool?
- Does no visible element overlap another, especially no note overlapping a task or event?
- Do sequence flows dock cleanly to end events without the arrow extending too far into the event?
- Would I still accept this same file as cleanly modeled even without any explanation?

## Binding Working Rule for Future Tasks

From now on, before finishing each new BPMN conversion, this file must be reviewed again.

If that review shows that:

- something is missing,
- something was overlooked,
- something is formally invalid,
- something does not match the existing project rules,
- or something violates BPMN best practices,

then the diagram must still be adjusted before delivery.
