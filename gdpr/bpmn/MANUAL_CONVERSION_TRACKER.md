# Manual Conversion Tracker

This tracker defines the authoritative workflow for the GDPR article conversions.
Existing auto-generated BPMN files in this folder are drafts only and do not count as manually reviewed deliverables.

## Quality Criteria

- Base each BPMN on the article XML in `artikel/` and the DAPRECO LegalRuleML semantics, not on the batch output.
- Preserve the article XML files unchanged.
- Write the reviewed result as `bpmn/GDPR_art_<n>_reviewed.bpmn`.
- Model legally relevant participant interaction as BPMN collaborations where it improves the legal process representation.
- Use question-style exclusive gateway names and explicit `Yes` / `No` flow labels.
- Prefer verb-noun task names and `sendTask` elements for actual communications.
- Re-check each reviewed BPMN against BPMN 2.0 best practices before marking it done.

## Status

| Article | Reviewed BPMN | Status | Notes |
| --- | --- | --- | --- |
| Art. 5 | `GDPR_art_5_reviewed.bpmn` | pending |  |
| Art. 6 | `GDPR_art_6_reviewed.bpmn` | pending |  |
| Art. 7 | `GDPR_art_7_reviewed.bpmn` | pending |  |
| Art. 8 | `GDPR_art_8_reviewed.bpmn` | pending |  |
| Art. 9 | `GDPR_art_9_reviewed.bpmn` | pending |  |
| Art. 10 | `GDPR_art_10_reviewed.bpmn` | pending |  |
| Art. 11 | `GDPR_art_11_reviewed.bpmn` | pending |  |
| Art. 12 | `GDPR_art_12_reviewed.bpmn` | pending |  |
| Art. 13 | `GDPR_art_13_reviewed.bpmn` | pending |  |
| Art. 14 | `GDPR_art_14_reviewed.bpmn` | pending |  |
| Art. 15 | `GDPR_art_15_reviewed.bpmn` | pending |  |
| Art. 16 | `GDPR_art_16_reviewed.bpmn` | pending |  |
| Art. 17 | `GDPR_art_17_reviewed.bpmn` | pending |  |
| Art. 18 | `GDPR_art_18_reviewed.bpmn` | pending |  |
| Art. 19 | `GDPR_art_19_reviewed.bpmn` | pending |  |
| Art. 20 | `GDPR_art_20_reviewed.bpmn` | pending |  |
| Art. 21 | `GDPR_art_21_reviewed.bpmn` | pending |  |
| Art. 22 | `GDPR_art_22_reviewed.bpmn` | pending |  |
| Art. 24 | `GDPR_art_24_reviewed.bpmn` | pending |  |
| Art. 25 | `GDPR_art_25_reviewed.bpmn` | pending |  |
| Art. 26 | `GDPR_art_26_reviewed.bpmn` | pending |  |
| Art. 27 | `GDPR_art_27_reviewed.bpmn` | pending |  |
| Art. 28 | `GDPR_art_28_reviewed.bpmn` | pending |  |
| Art. 29 | `GDPR_art_29_reviewed.bpmn` | pending |  |
| Art. 30 | `GDPR_art_30_reviewed.bpmn` | pending |  |
| Art. 31 | `GDPR_art_31_reviewed.bpmn` | pending |  |
| Art. 32 | `GDPR_art_32_reviewed.bpmn` | pending |  |
| Art. 33 | `GDPR_art_33_reviewed.bpmn` | done | Manual reference article, already accepted |
| Art. 34 | `GDPR_art_34_reviewed.bpmn` | done | Manual review completed after switch away from batch workflow |
| Art. 35 | `GDPR_art_35_reviewed.bpmn` | done | Manual review completed from statements180-188 |
| Art. 36 | `GDPR_art_36_reviewed.bpmn` | done | Manual review completed from statements189-195; explicit supervisory-authority request path added for additional information |
| Art. 37 | `GDPR_art_37_reviewed.bpmn` | done | Manual review completed from statements196-204; designation triggers and shared-DPO option checked against the master checklist |
| Art. 38 | `GDPR_art_38_reviewed.bpmn` | done | Manual review completed from statements205-210; DPO contact, independence, confidentiality, and conflict-of-interest checks aligned with the master checklist |
| Art. 39 | `GDPR_art_39_reviewed.bpmn` | done | Manual review completed from statements211-216; DPO task bundle and risk-based performance checked against the master checklist |
| Art. 40 | `GDPR_art_40_reviewed.bpmn` | done | Manual review completed from statements217-230; code-content areas, submission path, supervisory-authority review, and approval/publication logic checked against the master checklist |
| Art. 41 | `GDPR_art_41_reviewed.bpmn` | done | Manual review completed from statements231-234; public-body exception, accreditation requirements, monitoring setup, and non-compliance notification path checked against the master checklist |
| Art. 42 | `GDPR_art_42_reviewed.bpmn` | done | Manual review completed from statements235-238; voluntary certification path, information-and-access duty, and certification renewal handling checked against the master checklist |
| Art. 43 | `GDPR_art_43_reviewed.bpmn` | done | Manual review completed from statements239-241; accredited certification-body responsibility and supervisory-authority notification plus reasons path checked against the master checklist |
| Art. 45 | `GDPR_art_45_reviewed.bpmn` | done | Manual review completed from statements242-243; adequacy-based transfer paths and four-year authorization review logic checked against the master checklist |
| Art. 46 | `GDPR_art_46_reviewed.bpmn` | done | Manual review completed from statements244-250; six safeguard instruments, supervisory-authority authorization branches, and common safeguards-plus-risk check aligned with the master checklist |
| Art. 47 | `GDPR_art_47_reviewed.bpmn` | done | Manual review completed from statements251-252; grouped BCR content duties, supervisory-authority approval, data-subject availability, and ongoing governance obligations checked against the master checklist |
| Art. 48 | `GDPR_art_48_reviewed.bpmn` | done | Manual review completed from statements253; third-country request, Article 48 agreement check, non-recognition path, and agreement-based transfer path checked against the master checklist |
| Art. 49 | `GDPR_art_49_reviewed.bpmn` | done | Manual review completed from statements254-263; full derogation tree, public-authority restriction, public-register limitation, and fallback information plus documentation duties checked against the master checklist |
| Art. 77 | `GDPR_art_77_reviewed.bpmn` | pending |  |
| Art. 78 | `GDPR_art_78_reviewed.bpmn` | pending |  |
| Art. 79 | `GDPR_art_79_reviewed.bpmn` | pending |  |
| Art. 80 | `GDPR_art_80_reviewed.bpmn` | pending |  |
| Art. 82 | `GDPR_art_82_reviewed.bpmn` | pending |  |
| Art. 86 | `GDPR_art_86_reviewed.bpmn` | pending |  |
| Art. 89 | `GDPR_art_89_reviewed.bpmn` | pending |  |
