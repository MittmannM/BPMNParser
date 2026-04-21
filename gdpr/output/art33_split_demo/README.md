# Artikel 33 Split-Demo

Dieses Demo zerlegt `GDPR_art_33_reviewed.bpmn` in kleinere, fachlich sinnvolle Trainingseinheiten.
Die Textsegmente sind trainingsorientierte, semantisch treue Ausschnitte zu Art. 33 GDPR.
Fuer ein echtes Fine-Tuning wuerde ich spaeter den offiziellen Gesetzestext 1:1 je Segment hinterlegen.

## Fragmente

1. `text/art33_fragment_01_processor_notice.md`
   `bpmn/art33_fragment_01_processor_notice.bpmn`
   Fokus: Art. 33(2) - Prozessor meldet Verletzung unverzueglich an den Verantwortlichen.

2. `text/art33_fragment_02_controller_risk_screening.md`
   `bpmn/art33_fragment_02_controller_risk_screening.bpmn`
   Fokus: Art. 33(1) - Verantwortlicher bewertet Risiko; bei unwahrscheinlichem Risiko keine Meldung an Aufsichtsbehoerde.

3. `text/art33_fragment_03_notification_content.md`
   `bpmn/art33_fragment_03_notification_content.bpmn`
   Fokus: Art. 33(3)(a)-(d) - Mindestinhalt der Meldung.

4. `text/art33_fragment_04_complete_notification.md`
   `bpmn/art33_fragment_04_complete_notification.bpmn`
   Fokus: Art. 33(1) + 33(3) + 33(5) - Vollstaendige Meldung, inkl. Begruendung bei Verspaetung ueber 72 Stunden.

5. `text/art33_fragment_05_phased_notification.md`
   `bpmn/art33_fragment_05_phased_notification.bpmn`
   Fokus: Art. 33(4) + 33(5) - Phasenweise Meldung, wenn nicht alle Informationen gleichzeitig vorliegen.

6. `text/art33_fragment_06_documentation_duty.md`
   `bpmn/art33_fragment_06_documentation_duty.bpmn`
   Fokus: Art. 33(5) - Dokumentationspflicht als eigenstaendige Pflicht.

## Warum dieser Schnitt?

- Die Fragmente schneiden entlang von rechtlichen Mikro-Pflichten, nicht nur nach XML-Struktur.
- Jedes Fragment ist fuer ein LLM noch ueberschaubar und hat eine klare BPMN-Signatur.
- Gateways, Nachrichtenfluesse und parallele Mindestinhalte bleiben als eigene Muster sichtbar.
- Gleichzeitig bleibt die Komposition zum Gesamtmodell nachvollziehbar.

## Bezug zum reviewed BPMN

Die Fragmente orientieren sich an den Knoten und Zweigen aus:
`bpmn/GDPR_art_33_reviewed.bpmn`

Wichtige Anker:

- `Task_ProcessorNotifyController`
- `Task_AssessRisk`
- `Gateway_RiskUnlikely`
- `Gateway_CompileSplit`
- `Task_DescribeNature`
- `Task_ProvideContact`
- `Task_DescribeConsequences`
- `Task_DescribeMeasures`
- `Gateway_AllInfoAvailable`
- `Gateway_FullWithin72h`
- `Task_SendFullNotification`
- `Gateway_PhasedWithin72h`
- `Task_SendInitialNotification`
- `Task_SendFollowUpInformation`
- `Task_DocumentBreach`
