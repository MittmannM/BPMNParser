# Art. 33 Fragment 05

## Scope

Art. 33(4) und Art. 33(5)

## Trainingssegment

Koennen nicht alle erforderlichen Informationen gleichzeitig bereitgestellt werden,
duerfen sie stufenweise ohne unnoetige weitere Verzoegerung nachgereicht werden.
Der Verantwortliche sendet zunaechst eine erste Meldung und uebermittelt die fehlenden Informationen anschliessend in weiteren Mitteilungen.
Falls die erste Meldung erst nach Ablauf von 72 Stunden erfolgt, sind die Gruende fuer die Verspaetung zu dokumentieren und mitzuteilen.
Der Vorfall selbst ist ebenfalls zu dokumentieren.

## BPMN-Anker im reviewed Modell

- `Gateway_AllInfoAvailable`
- `Gateway_PhasedWithin72h`
- `Task_RecordDelayReasonsInitial`
- `Task_SendInitialNotification`
- `Task_CollectRemainingInformation`
- `Task_SendFollowUpInformation`
- `Task_DocumentBreach`
