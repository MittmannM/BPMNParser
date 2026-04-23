# BPMN Quality Checklist

Diese Datei ist die verbindliche Erinnerungs- und Checkliste fuer alle zukuenftigen manuellen BPMN-Konvertierungen der GDPR-Artikel in diesem Projekt.

Sie dient zwei Zwecken:

1. Sie haelt die projektspezifischen Vorgaben fest, die waehrend der Zusammenarbeit entstanden sind.
2. Sie dient als Abschluss-Check direkt vor Abgabe jeder neuen `*_reviewed.bpmn`.

## Verbindliche Projektregeln

- Die XML-Dateien im Ordner `artikel/` bleiben unveraendert.
- Die BPMN-Dateien werden im Ordner `bpmn/` abgelegt.
- Manuell gepruefte Endergebnisse bekommen das Namensschema `GDPR_art_<n>_reviewed.bpmn`.
- Die Batch-generierten BPMN-Dateien gelten nicht als Endergebnis und nicht als semantische Quelle.
- Jede reviewed-BPMN wird direkt aus dem echten englischen Text des jeweiligen GDPR-Artikels hergeleitet.
- Vor Abschluss jeder neuen reviewed-Datei wird diese Checkliste komplett durchgegangen.

## Quellenregel und Umgang mit den XML-Dateien

- Die Artikel-XML im Ordner `artikel/` bleibt archiviert und unveraendert, ist aber keine semantische Quelle mehr.
- Massgeblich fuer die Modellierung ist nur noch der echte englische Gesetzestext des jeweiligen GDPR-Artikels.
- Wenn alte XML-basierte Modelle, Notizen oder Referenzen vom Gesetzestext abweichen, geht immer der Gesetzestext vor.
- Sichtbare Cross-References auf andere Artikel oder Absaetze sollen im BPMN erhalten bleiben, wenn sie im echten Artikeltext den Rechtsablauf erklaeren oder begrenzen.
- Beim Modellieren ist nicht eine alte Formalisierung entscheidend, sondern die normative Wirkung des echten Artikels:
  - Pflicht
  - Ausnahme
  - Alternative
  - Folgepflicht
  - Bedingung
  - Frist
  - Beteiligung anderer Akteure

## Grundsatz fuer die Modellierung

- Ziel ist kein generisches Diagramm, sondern ein rechtlich brauchbares Prozessmodell.
- Das BPMN muss die prozessrelevante Logik des Artikels abbilden.
- Nicht jede logische Aussage aus dem Gesetzestext braucht ein eigenes BPMN-Element.
- Es sollen nur solche Elemente modelliert werden, die fuer den Rechts- oder Entscheidungsablauf relevant sind.

## Harte BPMN-2.0-Anforderungen

Diese Punkte muessen immer erfuellt sein.

- Die Datei muss wohlgeformtes XML sein.
- Das Wurzelelement muss `bpmn:definitions` sein.
- Alle IDs muessen eindeutig sein.
- Jeder `processRef` eines Participants muss auf einen existierenden Prozess zeigen.
- Jeder Prozess braucht mindestens ein Start Event.
- Jeder Prozess braucht mindestens ein End Event.
- `sequenceFlow` darf nur innerhalb desselben Prozesses verlaufen.
- `messageFlow` darf nur zwischen Teilnehmern bzw. zwischen Aktivitaeten und anderen Teilnehmern verwendet werden, nie als Ersatz fuer internen Kontrollfluss.
- Ein Element, das im `sourceRef` oder `targetRef` eines Flows vorkommt, muss existieren.
- Die BPMN-Datei muss so aufgebaut sein, dass gaengige BPMN-Tools sie oeffnen koennen.
- Deshalb muss eine reviewed-Datei nicht nur semantisch, sondern auch technisch importierbar sein.

## Technische Datei-Anforderungen fuer dieses Projekt

- Reviewed-BPMN-Dateien sollen die ueblichen BPMN-Namespaces enthalten:
  - `xmlns:bpmn`
  - `xmlns:bpmndi`
  - `xmlns:dc`
  - `xmlns:di`
- Reviewed-Dateien sollen ein Diagramm mit BPMN-DI enthalten:
  - `bpmndi:BPMNDiagram`
  - `bpmndi:BPMNPlane`
  - `bpmndi:BPMNShape`
  - `bpmndi:BPMNEdge`
- Wenn eine Datei zwar XML-gueltig, aber nicht im Modeler oeffenbar ist, ist sie nicht fertig.
- Die Diagrammgeometrie muss so gesetzt sein, dass alle sichtbaren Elemente innerhalb ihrer Pools oder Lanes liegen.
- Kein Prozessabschluss darf optisch aus dem Pool herausragen.

## Pools, Teilnehmer und Zusammenarbeit

- Pools werden verwendet, wenn der Artikel eine echte Interaktion zwischen Akteuren beschreibt.
- Externe Akteure duerfen als Black-Box-Participants modelliert werden, wenn ihr interner Ablauf fuer den Artikel nicht relevant ist.
- Typische externe Akteure sind:
  - Supervisory Authority
  - Data Subject
  - Public
  - DPO, wenn nur eine Beratungs- oder Kommunikationsbeziehung modelliert wird
- Ein eigener expandierter Prozess fuer einen externen Teilnehmer wird nur angelegt, wenn dessen interner Ablauf fuer den Artikel notwendig ist.
- Ein Controller-interner Ablauf soll nicht kuenstlich auf mehrere Pools verteilt werden.

## Sequence Flow und Message Flow

- `sequenceFlow` verbindet nur Elemente innerhalb desselben Prozesses.
- `messageFlow` verbindet Kommunikation zwischen Teilnehmern.
- Nachrichtliche Handlungen sollen als `sendTask` modelliert werden, wenn der Charakter der Aktivitaet das Senden einer Mitteilung ist.
- Reine interne Bearbeitungsschritte sollen normale `task`-Elemente bleiben.
- Aktivitaeten sollen nicht als Ersatz fuer ein Entscheidungs-Gateway verwendet werden, wenn nur einer von mehreren Folgepfaden gemeint ist.
- Hat dieselbe Pflicht in zwei verschiedenen Kontextpfaden Wirkung, ist es oft sauberer, die Aktivitaet pro Pfad zu duplizieren, statt eine einzelne Task mit mehrdeutigem Merge-und-Split-Verhalten zu bauen.
- Ein Flow darf nicht nur deshalb als Message Flow modelliert werden, weil er sprachlich nach Kommunikation klingt; entscheidend ist, ob wirklich ein anderer Teilnehmer adressiert wird.

## Gateways

- Divergierende exklusive Gateways muessen als Fragen benannt werden.
- Diese Fragen enden mit `?`.
- Die ausgehenden Pfade an solchen Gateways muessen explizite Labels tragen, in der Regel `Yes` und `No`.
- Auch wenn ein Pfad als scheinbarer Standardpfad einfach geradeaus zur naechsten Task weiterlaeuft, muss dieser als eigener sichtbarer ausgehender Flow vorhanden und eindeutig gelabelt sein.
- Join-Gateways sollen normalerweise unbenannt bleiben.
- Divergierende parallele Gateways sollen normalerweise unbenannt bleiben.
- Exklusive Gateways werden fuer Entscheidungen, Alternativen, Ausnahmen und Ja-Nein-Pruefungen genutzt.
- Parallele Gateways werden genutzt, wenn mehrere Pflichtinhalte oder Teilaktivitaeten gemeinsam zusammengestellt werden muessen.

## Benennungskonventionen

- Aktivitaeten werden in klarer Verb-Nomen-Form benannt.
- Aktivitaetsnamen sollen moeglichst kurz und schnell lesbar sein, idealerweise als knappe Verb-Objekt- oder Verb-Nomen-Phrase statt als ganzer Satz.
- Namen sollen beschreiben, was fachlich passiert, nicht nur auf den Artikel verweisen.
- Gute Beispiele:
  - `Assess risk to rights and freedoms`
  - `Provide DPO or contact point details`
  - `Notify supervisory authority`
- Zu lange ganze Saetze als Task-Label sollen vermieden werden, auch wenn sie inhaltlich korrekt waeren.
- Wenn ein laengerer juristischer Inhalt wichtig ist, soll die Task kurz benannt werden und die Praezisierung ueber Gateway-Fragen, Dokumentation oder End Events erfolgen.
- Schlechte Beispiele:
  - `Document information`
  - `Handle case`
  - `Art. 35 step 1`
- Gateways werden als Frage formuliert.
- End Events bekommen sinnvolle Ergebnisnamen, zum Beispiel:
  - `No direct data subject communication required`
  - `DPIA handling completed`

## Modellierungsstil fuer Rechtsnormen

- Ausloeser, Voraussetzungen und Ausnahmen muessen als nachvollziehbare Entscheidungslogik erscheinen.
- Fristen muessen als eigener Pruef- oder Verarbeitungsbaustein sichtbar werden, wenn sie rechtlich bedeutsam sind.
- Pflichtinhalte einer Meldung oder Bewertung sollen als Teilaufgaben modelliert werden, wenn sie fuer die Qualitaet des Prozessbildes wichtig sind.
- Wiederkehrende oder nachgelagerte Pflichten sollen als eigener Folgepfad erscheinen.
- Wenn eine Norm eine Ersatzmassnahme statt der Standardmassnahme vorsieht, soll das als eigener Alternativpfad modelliert werden.

## Umgang mit Ausnahmen

- Ausnahmen duerfen nicht im Text einer Aufgabe versteckt werden, wenn sie den Prozessverlauf aendern.
- Eine rechtlich relevante Ausnahme bekommt in der Regel:
  - eine Pruefaktivitaet oder
  - ein Gateway
- Bedingungen wie `if designated`, `if requested` oder aehnliche Ja-Nein-Abhaengigkeiten sollen nicht nur im Task-Namen versteckt werden, wenn daraus unterschiedliche Folgepfade entstehen.
- Wenn mehrere Ausnahmen dieselbe Rechtsfolge haben, duerfen sie nacheinander auf denselben End- oder Folgepfad fuehren.
- Wenn eine Ausnahme nur einen Sonderfall derselben Pflicht ausloest, soll dieser als klarer Alternativpfad modelliert werden.

## Umgang mit Pflichtinhalten

- Wenn ein Artikel Pflichtinhalte einer Mitteilung, Bewertung oder Dokumentation nennt, wird geprueft, ob diese als:
  - einzelne Aufgaben
  - parallele Sammelaufgaben
  - oder zusammengefasste Aktivitaet
  modelliert werden sollen.
- Der Detaillierungsgrad soll hoch genug sein, dass die juristische Struktur erkennbar bleibt.
- Gleichzeitig soll das Modell nicht unnoetig atomisiert werden.

## Dokumentation und Annotation

- `bpmn:documentation` kann verwendet werden, um die semantische Herleitung eines reviewed-Modells knapp festzuhalten.
- Documentation soll vor allem dort helfen, wo:
  - mehrere Absatzteile oder Saetze zusammen auf einen BPMN-Pfad abgebildet werden
  - ein Cross-Reference-Artikel im Ablauf sichtbar gemacht wird
  - eine Ausnahme oder Ersatzmassnahme modelliert wird
- Text Annotations nur verwenden, wenn sie den Leser wirklich unterstuetzen.
- Annotationen sind kein Ersatz fuer saubere Modellierung.

## Layout-Regeln

- Alle sichtbaren Elemente muessen innerhalb des passenden Pools liegen.
- Ein End Event darf nicht optisch ausserhalb des Pools stehen.
- Sichtbare Diagrammelemente duerfen sich nicht ueberlappen.
- Das gilt insbesondere fuer Tasks, Events, Gateways, Text Annotations, Notes und deren Beschriftungsraum.
- Notizen oder sonstige Annotationen duerfen nicht auf Tasks oder andere BPMN-Elemente gelegt werden.
- Sequence Flows zu End Events muessen visuell sauber andocken; der letzte Waypoint darf nicht so gesetzt sein, dass der Pfeil sichtbar zu tief in das Endereignis hineinragt.
- Message Flows sollen moeglichst klar und nicht irrefuehrend verlaufen.
- Der Hauptfluss soll moeglichst von links nach rechts lesbar sein.
- Ausnahme- und Alternativpfade duerfen nach oben oder unten ausweichen, sollen aber lesbar bleiben.
- Parallele Inhaltssammlungen sollen visuell als zusammengehoeriger Block erscheinen.

## Qualitaetsmassstab aus den bisherigen Reviews

Folgende Punkte wurden bisher explizit als gewuenscht oder notwendig erkannt:

- Art. 33 ist der qualitative Referenzstandard.
- Art. 34 und folgende sollen auf demselben Niveau modelliert werden.
- Frage-Gateways mit `Yes` und `No` sind Pflicht, wo Entscheidungen divergieren.
- Kommunikation an andere Akteure soll als `sendTask` modelliert werden.
- Reviewed-Dateien muessen in BPMN-Tools oeffenbar sein.
- Visuelle Pool-Grenzen muessen korrekt sein.
- Automatisch erzeugte Diagramme duerfen nicht unbesehen uebernommen werden.

## Empfohlener Arbeitsablauf pro Artikel

1. Den echten englischen Text des GDPR-Artikels lesen.
2. Explizite Cross-References, Voraussetzungen und Rechtsfolgen markieren.
3. Normative Logik in diese Kategorien zerlegen:
   - Ausloeser
   - Pflicht
   - Ausnahme
   - Alternative
   - Frist
   - Folgepflicht
   - Beteiligte Akteure
4. Entscheiden, ob eine Collaboration sinnvoll ist.
5. BPMN manuell modellieren.
6. Vor Schluss die komplette Checkliste durchgehen.
7. XML-Pruefung ausfuehren.
8. Oeffnungs- und Layoutfaehigkeit mitdenken, insbesondere BPMN-DI und Pool-Grenzen.

## Schluss-Check vor Abgabe

Diese Liste ist vor jeder neuen reviewed-Datei aktiv abzuhaken.

- Wurde die Artikel-XML unveraendert gelassen?
- Wurde die BPMN-Datei als neue `*_reviewed.bpmn` gespeichert?
- Wurde die semantische Logik direkt aus dem echten englischen Artikeltext hergeleitet?
- Sind explizite Cross-References aus dem Artikel dort sichtbar erhalten, wo sie fuer den Rechtsablauf wichtig sind?
- Sind Pflichten, Ausnahmen und Alternativen korrekt im Prozessverlauf abgebildet?
- Sind die richtigen Teilnehmer modelliert?
- Sind externe Interaktionen als Message Flows und nicht als Sequence Flows modelliert?
- Sind echte Mitteilungen als `sendTask` modelliert?
- Hat keine Aktivitaet mehrere ausgehende Pfade, wenn damit eigentlich alternative statt parallele Fortsetzungen gemeint waeren?
- Haben alle divergierenden exklusiven Gateways Frage-Namen mit `?`?
- Haben die ausgehenden Pfade solcher Gateways Labels wie `Yes` und `No`?
- Ist auch der geradeaus weiterlaufende Standardpfad eines Gateways explizit als `Yes`- oder `No`-Flow sichtbar und nicht nur implizit gedacht?
- Sind Join-Gateways unbenannt, sofern kein besonderer Grund fuer einen Namen besteht?
- Sind parallele Gateways unbenannt, sofern kein besonderer Grund fuer einen Namen besteht?
- Sind bedingte Formulierungen nicht nur im Task-Namen versteckt, wenn stattdessen ein Gateway mit explizitem `No`-Weiterpfad noetig waere?
- Sind die Aktivitaetsnamen fachlich klar und in Verb-Nomen-Form?
- Gibt es mindestens ein Start Event und ein End Event?
- Sind alle IDs eindeutig?
- Ist die Datei XML-gueltig?
- Enthaelt die Datei BPMN-DI, damit sie im Modeler oeffnet?
- Liegen alle sichtbaren Elemente innerhalb der richtigen Pools?
- Ragt kein End Event oder Task optisch aus einem Pool heraus?
- Ueberlappt kein sichtbares Element ein anderes, insbesondere keine Notiz eine Task oder ein Event?
- Docken Sequence Flows an End Events visuell sauber an, ohne dass der Pfeil zu weit in das Ereignis hineinragt?
- Wuerde ich dieselbe Datei ohne Erklaerung noch immer als sauber modelliert akzeptieren?

## Verbindliche Arbeitsregel fuer kommende Aufgaben

Ab jetzt wird bei jeder neuen BPMN-Konvertierung kurz vor dem Abschluss diese Datei nochmals durchgegangen.

Wenn dabei auffaellt, dass:

- etwas fehlt,
- etwas uebersehen wurde,
- etwas formal ungueltig ist,
- etwas nicht den bisherigen Projektregeln entspricht,
- oder etwas gegen BPMN-Best-Practices verstoesst,

wird das Diagramm vor der Abgabe noch angepasst.
