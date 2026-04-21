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
| Art. 5 | `GDPR_art_5_reviewed.bpmn` | done | Manual review completed from statements1-6; six processing-principle branches, explicit accuracy rectification-or-erasure path, and non-overlapping DI layout checked against the master checklist |
| Art. 6 | `GDPR_art_6_reviewed.bpmn` | done | Manual review completed from statements7-13; six legal-basis branches, Article 6(4) compatibility-factor block, and non-overlapping DI layout checked against the master checklist |
| Art. 7 | `GDPR_art_7_reviewed.bpmn` | done | Manual review completed from statements14-16; clear consent-request path, withdrawal-right information, easy-withdrawal mechanism, demonstrability, and non-overlapping DI layout checked against the master checklist |
| Art. 8 | `GDPR_art_8_reviewed.bpmn` | done | Manual review completed from statements17-18; Article 8 applicability gate, applicable-age split, child-consent path, parental-authorisation plus reasonable-efforts verification path, and non-overlapping DI layout checked against the master checklist |
| Art. 9 | `GDPR_art_9_reviewed.bpmn` | done | Manual review completed from statements19-28; Article 9(1) special-category gate, default prohibition, explicit Article 9(2)(a)-(i) exception block, and non-overlapping DI layout checked against the master checklist |
| Art. 10 | `GDPR_art_10_reviewed.bpmn` | done | Manual review completed from statements29; Article 10 applicability gate, comprehensive-register special rule, official-authority path, Union-or-Member-State-law authorization path with safeguards, and non-overlapping DI layout checked against the master checklist |
| Art. 11 | `GDPR_art_11_reviewed.bpmn` | done | Manual review completed from statements30-31; no-identification path, Article 11(2) information duty, Articles 15 to 20 exception with additional-identification-information fallback, and non-overlapping DI layout checked against the master checklist |
| Art. 12 | `GDPR_art_12_reviewed.bpmn` | done | Manual review completed from statements32-38; general information path for Article 12(1) and (7), request-handling path for Article 12(2)-(6), identity-check and Article 11(2) branch, extension and no-action notices, fee-or-refusal exception, and non-overlapping DI layout checked against the master checklist |
| Art. 13 | `GDPR_art_13_reviewed.bpmn` | done | Manual review completed from statements39-51; direct-collection information duties, legitimate-interest and transfer-safeguard branches, supplementary information block, and further-purpose notice path checked against the master checklist |
| Art. 14 | `GDPR_art_14_reviewed.bpmn` | done | Manual review completed from statements52-71; indirect-collection information duties, Article 14(5) exception chain, timing alternatives, source-category duties, and further-purpose notice path checked against the master checklist |
| Art. 15 | `GDPR_art_15_reviewed.bpmn` | done | Manual review completed from statements72-82 plus transparent no-processing supplement from the legal text; Article 15(1) access-information bundle, transfer-safeguards branch, copy and additional-copy handling, electronic-format split, and Article 15(4) protective limitation checked against the master checklist |
| Art. 16 | `GDPR_art_16_reviewed.bpmn` | done | Manual review completed from statements83; shared request intake, Article 12(2) and Article 11(2) exception gate, inaccurate-data rectification path, incomplete-data completion path with supplementary-statement handling, and non-overlapping DI layout checked against the master checklist |
| Art. 17 | `GDPR_art_17_reviewed.bpmn` | done | Manual review completed from statements84-96; six Article 17(1) erasure grounds, Article 17(3) exception block, public-data notification path under Article 17(2), and non-overlapping DI layout checked against the master checklist |
| Art. 18 | `GDPR_art_18_reviewed.bpmn` | done | Manual review completed from statements97-102; four Article 18(1) restriction grounds, Article 18(2) limited-processing block, prior-information path before lifting the restriction, and non-overlapping DI layout checked against the master checklist |
| Art. 19 | `GDPR_art_19_reviewed.bpmn` | done | Manual review completed from statements103; rectification-erasure-restriction trigger split, recipient-notification duty, too-much-effort exception path, optional data-subject recipient-information path, and non-overlapping DI layout checked against the master checklist |
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
| Art. 77 | `GDPR_art_77_reviewed.bpmn` | done | Manual review completed from statements264 plus Article 77(2) follow-up inference; complaint venue options, authority feedback path, and non-overlapping DI layout checked against the master checklist |
| Art. 78 | `GDPR_art_78_reviewed.bpmn` | done | Manual review completed from statements265-266 plus Article 78(3)-(4) legal-text supplementation; decision path, complaint-inactivity path, court venue, Board-material forwarding, and non-overlapping DI layout checked against the master checklist |
| Art. 79 | `GDPR_art_79_reviewed.bpmn` | done | Manual review completed from statements267 plus Article 79(2) venue supplementation; infringement-based remedy path, public-authority venue restriction, and non-overlapping DI layout checked against the master checklist |
| Art. 80 | `GDPR_art_80_reviewed.bpmn` | done | Manual review completed from statements268 plus transparent Article 80(2) legal-text supplementation; mandate path, optional Member-State no-mandate path, complaint/judicial-remedy/compensation action scope, and non-overlapping DI layout checked against the master checklist |
| Art. 82 | `GDPR_art_82_reviewed.bpmn` | done | Manual review completed from statements269-273; compensation right, controller liability, processor-specific liability, exemption, full-compensation path, recourse claim, and non-overlapping DI layout checked against the master checklist |
| Art. 86 | `GDPR_art_86_reviewed.bpmn` | done | Manual review completed from statements274; official-document access request, public-interest holder check, reconciliation with access law, disclosure decision, and non-overlapping DI layout checked against the master checklist |
| Art. 89 | `GDPR_art_89_reviewed.bpmn` | done | Manual review completed from statements275; Article 89 purpose gate, safeguards and measures path, pseudonymisation and non-identifying processing checks, and non-overlapping DI layout checked against the master checklist |
