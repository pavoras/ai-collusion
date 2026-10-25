# Plan: Frage 1.4, Netto-Einfluss bei LLM-Bietern

Stand: Fr 23.10.2026, ca. 17 Uhr, Plan v4. Details: `docs/DESIGN.md` (Versuch), `docs/REPORT_OUTLINE.md` (Report,
Literatur), `docs/PITCH.md`, `docs/METHOD.md`.

## Auf einen Blick

**Titel:** Collusion, Espionage, or Look-alikes? Auditing Information Flow between LLM Agents
**Untertitel:** Pairwise net influence with and without private inputs in a procurement auction
**Forschungsfrage:** Can pairwise net influence detect covert coordination between LLM agents, and when do
private inputs let an auditor tell collusion apart from espionage and shared-history dependence?

**Kerngeschichte:** Gebote allein zeigen, *dass* Information fließt. Die privaten Kosten zeigen, *in welche Richtung*:
zweiseitig (Kartell), einseitig (Spion) oder gar nicht (bloße Ähnlichkeit, gleiche Historie).

**Report:** offizielle Vorlage, empfohlen 4 Seiten (max. 8) ohne Literatur und Anhang. Gliederung und Seitenbudget
in `REPORT_OUTLINE.md`. Marvin schreibt die Endfassung selbst (Vorgabe der Vorlage), Claude entwirft und prüft.

## Entscheidungen (Marvin, 23.10.)

| Punkt | Entscheidung |
|---|---|
| Titel und Frage | D3 (oben) |
| Analyseeinheit (A) | A4: Erkennung pro Markt mit 200 Runden als Hauptergebnis; gepoolte Fingerabdrücke als Mechanismus-Analyse |
| Hauptstatistik (C) | C3: zwei vorab festgelegte Endpunkte. Netto-Einfluss für „welches Paar“ (Pflichtteil, fairer Vergleich mit Korrelation und LLM-Richter auf gleicher Zugriffsstufe); gerichtete Leck-Terme für „welche Art Informationsfluss“ |
| Spionage | ja (Marvin: „das ist gold“) |
| Kartell-Prompt | Hinweis auf Überwachung durch das Kartellamt, unauffällig bleiben; Scheingebote frei gewählt |
| Kartell-Positionen | stark+stark (Haupt), dazu stark+schwach und schwach+schwach beim Hauptmodell |
| Umfang (E) | ein Hauptmodell komplett, dazu kleinere Runden: Labore, Größen, Kartell aus gleichem vs. verschiedenem Modell |
| Zustand / Historie (B) | exakter letzter Gewinnerpreis H als Zustand (grobe Stufen nur als Ablation); Hauptstatistik für den Mechanismus: Leck I(B_i; C_j \| C_i, H); dazu Proben auf eingefrorenen Kontexten mit Partnerkosten-Eingriff |

| Marktzahlen | 200 Runden; Marktzahlen nach Testlauf und Power-Simulation (Sol Runde 6) festlegen, vor PREREG |
| Denkmodus | Bieter aus, Richter an |
| Sampling | Herstellerempfehlung je Modell (Qwen Instruct allgemein: T 0,7, top_p 0,8, top_k 20, presence 1,5; Gemma 4: T 1,0, top_p 0,95, top_k 64; Ministral 3: T < 0,1, Beispiel 0,15) |
| Gemischter Block | X = Qwen-9B, Y = Gemma-12B, Z = Ministral-8B: Kartell (X, X) vs. (X, Y), ehrliche Kontrolle (X, X, Y, Z) |
| Richter-Gegenprobe | Gemma-12B auf 10 Märkten |

## Umfang (E, Marvins Fassung)

| Block | Modelle | Bedingungen | Märkte × Runden |
|---|---|---|---|
| Kern | Qwen3.5-9B | N0, P0, C1 (stark+stark), C1 stark+schwach, C1 schwach+schwach, C2 (still), E1 (Spion), Proben auf eingefrorenen Kontexten | 20 × 200 |
| Labore | Gemma-4-12B, Ministral-3-8B | N0, C1 | 10 × 200 |
| Größen | Qwen3.5-4B, Gemma-4-E4B, Ministral-3-3B | N0, C1 | 10 × 200 |
| Gleiches vs. verschiedenes Modell | X = Qwen-9B, Y = Gemma-12B, Z = Ministral-8B | D = ehrlich (X, X, Y, Z) mit Behandlung C1-XX; H-XYZZ = ehrlich (X, Y, Z, Z) mit Behandlung C1-XY; jede Behandlung nur gegen ihre eigene Kontrolle; keine Kausalaussage zu „gleiches Modell“ (Identität und Stärke nicht gekreuzt) | 10 × 200 |
| Richter | Qwen3.5-9B mit Denkmodus | alle Märkte, L1 und L2 | - |

Grob 250 000-300 000 Aufrufe. Verbindlich ist ab dem Einfrieren `docs/PREREG.md` (Manifest, Budgetleiter B0-B5,
Reihenfolge); der Pilotlauf wählt nur anhand von Betriebsdaten den Zweig. Streichreihenfolge:
C1 schwach+schwach → N0-Kern 40 → 20 → kleine Modelle außer Qwen-4B → gemischtes Paar H-XYZZ/C1-XY → Märkte der Breitenblöcke
auf 6.

## Stand

Stand 24.10., 16:20: Datensammlung, eingefrorene Auswertung (`final_v1`) und Report-Entwurf fertig.

| Fertig | In Arbeit | Fehlt |
|---|---|---|
| Sammlung Kern, A1, A2, A3/Breite (43 Läufe, `results/analysis_runs.json`) | | Marvins Endprüfung des Reports in eigenen Worten |
| Qwen-Richter Kern + A2 (600 Urteile), Gemma-Gegenrichter (40), Sonden (`core.probes`) | | Repo öffentlich machen, URLs in Report, Repo verschlanken |
| Auswertung `final_v1` (Freeze `4c4b6f1`), Astra Runde 13 (Prüfung), Runde 14 (Report) | | Abgabe bis Mo 26.10., 12:59 |
| Addenda v2.2 (Replikation E1/C2/C1-SS, Märkte 20-39) und v2.3 (Richter 24k), Abweichung 7 | | |
| Report: 8 Seiten Haupttext, Abbildungen A/B, Tabelle 1 (Replikation), Anhang E.7, Literatur geprüft (`report/main.pdf`) | | |
| Modal-Endstand 76,30 $ gemessen (76,03 $ Guthaben), unter 80 $ | | |

## Zeitplan (deutsche Zeit)

| Wann | Was | Wer |
|---|---|---|
| Fr bis 20 Uhr | Entscheidung B; `DESIGN.md` v4; Sol-Runde: Skript-Checks + LLM-Harness | Marvin, Claude, Sol |
| Fr abends | Harness prüfen; Testlauf Qwen-9B; Kosten hochrechnen; Go/No-Go | Claude, Go: Marvin |
| Sa bis 12 Uhr | `PREREG.md` committen; Kernblock starten | Claude |
| Sa 14:15 | Talk Nguyen (Einleitung, Begriffe) | Marvin |
| Sa nachmittags / abends | Kernblock auswerten (Checkpoint P1-P3); Breitenblöcke starten | Claude |
| So vormittags | Breitenblöcke fertig, Richter, Proben; Abbildungen | Claude / Sol |
| So nachmittags | Report-Entwurf nach `REPORT_OUTLINE.md` | Claude entwirft |
| So abends | Marvin überarbeitet in eigenen Worten; Astra-Review | Marvin, Astra |
| Mo bis 11 Uhr | Endkorrektur, Reproduktionscheck aus frischem Clone, Repo öffentlich, Abgabe (Frist 12:59) | Marvin |

## Pivot-Plan (es wird etwas schiefgehen)

Jede Zeile ist ein Szenario mit Erkennungsmerkmal, Entscheidungszeitpunkt und dem, was wir dann berichten. Die
Kerngeschichte bleibt in jedem Fall erzählbar, weil Skript-Simulation und RPS-Nachbau schon stehen.

| Szenario | Woran wir es merken | Wann | Dann |
|---|---|---|---|
| P1 LLM-Kartell kungelt nicht | Manipulationscheck: kein Preisaufschlag, keine Scheingebote, Nachrichten ohne Absprache | nach 3 Märkten C1 | einmal vorregistrierte deutlichere Anweisung; sonst Befund „LLMs setzen Kartell nicht um“ berichten, Erkennung an P0 und Spion zeigen |
| P2 viele Fehlalarme bei ehrlichen LLMs | N0-Fehlalarm deutlich über 5 % | nach N0 Kernblock | Befund zur gemeinsamen Historie wird zentral; Gewicht auf Leck-Terme und Proben |
| P3 Leck-Terme trennen Kartell und Spion bei LLMs nicht | Fingerabdruck E1 ≈ C1 | nach Kernblock | ehrlich berichten; Fingerabdruck an Skripten als Methode, LLM als Grenze |
| P4 Gebote ohne Streuung (LLMs fast deterministisch) | Entropie der Gebote nahe 0 im Testlauf | Testlauf | Temperatur hoch, Prompt prüfen; sonst anderes Modell als Hauptmodell |
| P5 Modal hakt oder zu langsam | Smoke-Test/Throughput | Testlauf | weniger Märkte; Hauptmodell + ein weiteres Labor; notfalls OpenRouter (Schlüssel: Marvin) |
| P6 Budget läuft davon | Kostenzähler | laufend | Budgetleiter (PREREG); harter Stopp bei 50 $ (80 $ Guthaben, Marvin 23.10.) |
| P7 Zeit läuft davon | Sa 20 Uhr Kernblock nicht fertig | Sa 20 Uhr | Breitenblöcke streichen; Report = RPS + Skript-Auktion + LLM-Kern |
| P8 Netto-Einfluss schlechter als Baselines | Vergleich | Auswertung | ehrlich berichten (Endpunkt C3 trägt die Geschichte trotzdem) |

## Pflichtteil 1.4 (im Report sichtbar)

Netto-Einfluss implementiert ✓ · an geskriptetem RPS getestet ✓ · 4-Agenten-Spiel mit genau einem gesetzten Paar
(Ausschreibung) · Vergleich Netto-Einfluss vs. Korrelation vs. LLM-Richter · Marktfall (Ausschreibung statt
Doppelauktion, begründet).

## Prüfung

Unit-Tests; Skript-Simulationen mit bekannter Wahrheit; Testlauf mit Abbruchkriterien; Manipulationschecks;
Vorregistrierung vor den Hauptläufen; gepaarte Seeds, Bootstrap über Märkte; Astra-Reviews; Endkontrolle aus
frischem Clone. Keine Zahl im Report ohne reproduzierbaren Lauf.

## Log

- 23.10.: Projekt und Dokumentation angelegt, Paper gelesen, Einheit (Bits) aus den Paper-Zahlen abgeleitet,
  Kontrollwerte berechnet.
- 23.10. abends: Schritt 0 und 1 fertig (14 Tests grün, Kontrollwerte bei N = 200 000 auf ±0,003 bit).
- 23.10. abends: Lokale Modelle verworfen, nur Modal. Zwei gleichzeitige Sprint-Repos gefunden. Neuer Kern:
  Ausschreibung mit privaten Kosten. Plan v2.
- 23.10. abends: Astra Runde 1 (gpt-6-astra/high, read-only, Thread 01a168c9-0f89-7fa2-b825-53a5b8e444e9, ~1 %
  Wochenkontingent): 6 Must-fix. Übernommen: Neuheit vorsichtiger, Eq.-3-Zerlegung, symmetrischer Nulltest ohne
  Pauschalgarantie, In-Game-Replays durch Proben auf eingefrorenen Kontexten ersetzt, Tabellenbelegung und
  Analyseeinheit vorab simulieren, Partnerkosten-Eingriff als kausaler Check, Umfang gekürzt. Selbst nachgerechnet:
  Kartell-Regel war unprofitabel (−4 % gegen Kosten+1-Bieter); daher asymmetrisches Spiel mit zwei starken Firmen
  (+29 % bis +76 %). Plan v3.
- 23.10. nachmittags: RPS-Nachbau fertig (Bits + Vorrunden-Zustand treffen Paper-Tabelle 2; festes α bis 59 %
  Fehlalarm, kalibriert 2-4 %). Modal: Gewichte aller 6 Modelle im Volume, App qwen-9b deployt (keine GPU aktiv).
  Sol Runde 2 (gpt-6.1-sol/high, Thread 01a168ed-aae1-76c2-8ca3-3815b7e6b7f6): Auktion, Skript-Agenten, Gl.-3-
  Zerlegung, symmetrischer Permutationstest, Baselines, Simulationen (53 Tests grün; von Claude geprüft).
  Befunde: Fingerabdruck trennt Kartell (zweiseitig), Spion (einseitig) und Attrappe (nur Aktionsterm); geteilte
  Historienreaktion hebt Fehlalarme auf 13,5 %; Stark-Schwach-Kartell auf L2 schwer (15 % bei 100 Runden).
  Codex-Wochenkontingent danach: 1.0 %.
- 23.10. ca. 17 Uhr: Astra Runde 3 (gpt-6-astra/high, read-only, Thread 01a1691c-4ed8-7af1-b815-4e020a52916f) zu
  Analyseeinheit, Zustand, Hauptstatistik, Titel, Umfang. Marvin entschied A4, C3, D3, Umfang wie oben; B offen.
  Report-Vorlage gelesen (empfohlen 4 Seiten, Endfassung überwiegend vom Team). Literatur- und Neuheitscheck
  vorgezogen (siehe REPORT_OUTLINE.md), neu relevant: Audit the Whisper (2510.04303), Bid-Rigging-Screens von
  Huber/Imhof/Wallimann. Plan v4 mit Pivot-Plan.
- 23.10. abends: Marvin entschied B (exakter letzter Gewinnerpreis, Leck-Term als Hauptstatistik). `DESIGN.md` v4.
  Sol Runde 4 (gpt-6.1-sol/high, Thread 01a1693a-392a-7870-a618-7cfa1dc09baa): Skript-Checks. Sol Runde 5
  (gpt-6.1-sol/xhigh wegen Geld und Logging, Thread 01a1693a-41b2-7543-91e0-b9a092a2a5e6): LLM-Harness. Beide
  parallel in getrennten Dateien. Testlauf vorbereitet, Ausführung erst nach Marvins Go.
- 23.10. abends: Sol Runde 4 fertig (exakter Zustand: L2-Fehlalarme bei geteilter Historie 7/20 -> 0/20;
  Leck-Klassifikation mit "unklar"; Stark-Schwach-Kartell pro Markt kaum klassifizierbar). Sol Runde 6 (Power):
  Kartell stark+stark bei q = 0,5 mit 20 Märkten AUROC ~1; Zwei-Wege-Klassifikation pro Markt bricht bei q <= 0,5 ein.
  Astra Runde 7 (Thread 01a1695a-4029-7ea2-942d-deb2965ef22a): nicht einfrieren vor Must-fixes; umgesetzt in
  PREREG v2 (eine Primärhypothese mit Label-Swap-Test, Manifest, Budgetleiter, blinde Auswertung, passende
  Kontrollen im gemischten Block, keine Erfolgsselektion). Sol Runde 8 (Thread 01a16965-93f0-7ac2-8001-9811aef03105):
  historienabhängige ehrliche Bieter treiben L1/L2-Fehlalarme bis 100 %, Leck-Terme bleiben bei ca. 1-8 % ->
  Leck-Score als zusätzlicher Detektor in PREREG; Abbildung Kandidat für den Hauptteil. Marvin: Sol nur auf high;
  Pilotlauf nach eigenem Ermessen nach dem Einfrieren.
- 23.10. abends: Sol Runde 5 (Harness inkl. Manifest, Live-P0, blinder Richter, Proben, Pilot-Stopps) und Runde 9
  (blinde Auswertung nach PREREG) fertig; von Claude geprüft und ergänzt (Spaltenreihenfolge im Prompt, Manifest an
  PREREG angeglichen, Leck-Regel). 287 Tests grün. Marvin: 80 $ Modal-Guthaben, höchstens 50 $ nutzen; Leck-Score
  benennt bei mindestens einer Richtung.
- **PREREG v2 eingefroren:** Commit `56717aba03261552b9e09be4dded8b6e4cdc04b3` (2026-10-23T19:33:39+02:00). Manifest-Hash
  `2ffab714f5160ff9a44b49a3199ff064de817057012031ef0bc5de9952f69b7b`.
- 23.10. abends: **Pilot** `pilot_qwen9b_v5` (N0 + P0, Märkte 0-19, Qwen-9B) vollständig: 24 029 Aufrufe, 0,33 %
  ungültig, 0 Transportfehler, Latenz p50 11,7 s / p95 12,3 s, 35 981 Aufrufe pro GPU-Stunde, 40 min, ca. 1,30 $.
  Nur Betriebswerte angesehen (blind). Erster Versuch `pilot_qwen9b_v4` stoppte beim Aufwärmen (PREREG-Abweichung 1).
- **Budgetzweig B0** (Vollausbau): Projektion 13,77 $ GPU (7,36 GPU-Stunden), mit 15 % Reserve ca. 15,8 $ <= 45 $.
  Engpass ist Zeit, nicht Geld: Zellen eines Blocks laufen gleichzeitig (Modal skaliert Container hoch); die
  Streichreihenfolge bei Budget- oder Zeitnot bleibt die der PREREG. Auswertung der Ergebnisse erst, wenn der
  Kernblock komplett ist.
- 23.10. ca. 20-21 Uhr: Kernblock (6 Zellen, Qwen-9B) läuft parallel auf Modal (bis zu 3 Container). Marvin: Stufe 1
  voll umsetzen. PREREG-Nachtrag v2.1 (A1 Kartell ohne Warnsatz, A2 gekreuzte Doppelgänger mit Zwillingszellen,
  A3 Breite auf 20 Märkte) vor jeder Ergebnisauswertung geschrieben (`fe26f6e`), Astra Runde 10 (Thread
  01a16a06-2ee2-7910-8cad-f35a9ff265a8): A2 kausal umgebaut. Sol Runde 11 (Thread 01a16a08-ffdb-7582-bde8-5bfe9d9f67d0)
  setzt um; Amendment-Freeze `4c4b6f1` (21:05), Manifest v2 `a63ef104...`, 305 Tests grün. Zweig B0+ (ca. 548 000
  Aufrufe, grob 27 $ + Reserve). A1 startet sofort parallel zum Kernblock (Budget nicht bindend, Streichreihenfolge
  unverändert), A2 nach dem Aufwärmen von Gemma und Ministral.
- 23.10. 22:00-22:50: Kern E1, C2, N0 (20-39), A2-LY fertig; C1-SS/SF/FF und A1 laufen. **Probleme aus
  Betriebswerten (blind):** (1) Gemma/Ministral antworten mit JSON im Markdown-Codeblock, der strikte Parser wertet
  100 % als ungültig -> alle A2-Zellen unbrauchbar, gestoppt; Parser-Version 2 (`--parse-fenced`) für alle Zellen mit
  Gemma/Ministral, A2 neu als `_p2` (PREREG-Abweichung 2). Live-Test: 0 % ungültig. (2) Parallele gepaarte Zellen
  blockierten sich gegenseitig -> Ledger wartet jetzt (Abweichung 3a). (3) Richter: 1200-s-Timeouts unter Last;
  freigegeben und neu eingereicht (Abweichung 3b). Richterdurchsatz gemessen: ca. 670 Token/s bei 29 parallel, ca.
  0,009 $ pro Urteil. Kleine Modelle (qwen-4b, gemma-e4b, ministral-3b) deployt. Marvin: insgesamt 80 $ für alles,
  über Nacht höchstens 60 $; 30-Minuten-Statusmeldungen.
- 23.10. 23:13-23:51: **C: voll**, alle Läufe abgebrochen (PREREG-Abweichung 4); Claude-Sitzung beendet, daher keine
  Nachtmeldungen. 24.10. 08:00: Marvin: 27,11 $ verbraucht; Rohdaten nach D: verschoben (Junction), Speicherwächter
  (BudgetStop unter 3 GB frei), verwaiste Ledger-Einträge freigegeben, alles unter Suffix `_c` fortgesetzt.
- 24.10. 08:00-11:50: Wiederaufnahme der Sammlung unter `_c`/`_d`; Betriebsprobleme (Speicherwächter, Preemption,
  `database is locked`, Gemma-E4B-Obergrenzen, Lader-Junction) als PREREG-Abweichung 5a-h dokumentiert.
- 24.10. 11:50-15:00: **Richterphase** (Abweichung 6). Gemessen ca. 18 000 erzeugte Token pro Urteil, also ca.
  0,018 $ statt der geschätzten 0,009 $. Marvin (12:45): Breiten-Richter gestrichen, Kern- und A2-Richter
  vollständig. Richter-Timeout 1800 s (`_s4`); Modal-Autoscaler-Abbrüche durch festgepinnte Container behoben,
  danach zurückgesetzt. 71 Transportfehler freigegeben und neu gelaufen. Gemma-Gegenrichter und Sonden danach.
- 24.10. ca. 15:00: Auswertung `final_v1` mit Richtern und Sonden. Primärtest bestätigt (C1-SS vs. N0, L2, AUROC
  0,865, p = 2e-05), aber kein allgemeiner Vorteil gegenüber Korrelation; E1 einzige Zelle mit Differenz-Intervall
  ohne 0 (deskriptiv). Astra Runde 13 rechnete alle 122 AUROCs nach. Runde 14 schrieb den Report
  (`2318815`). Literaturangaben am 24.10. an Primärquellen geprüft (`7584cae`). Modal-Stand laut Marvin ca. 70-71 $.
- 24.10. abends: Codex-Abo abgelaufen (Astra/Sol nicht verfügbar); eine Luna-Runde wurde auf Marvins Anweisung
  gestoppt und vollständig verworfen. Marvin (ca. 19:30): Zusatzläufe im 80-$-Budget, Reihenfolge E1+C2, Richter,
  dann C1-SS nach Restbudget. **Addendum v2.2** (`63cb9f4`, vor den Daten): Replikation von E1/C2 (und C1-SS) auf den
  frischen Märkten 20-39 gegen die vorhandenen N0 20-39, ausgewertet als eigene Kohorte mit dem eingefrorenen Code
  (`--run-index results/analysis_runs_v22.json`). Kostenloser Trockenlauf inkl. Auswertung; eine Prüfkohorte auf den
  Märkten 0-19 deckte einen fehlenden `position`-Eintrag auf (behoben mit `experiments/cohort_index.py`) und zeigte,
  dass Korrelation/Stärke/Paper exakt und Netz/Leck bis auf Permutationsrauschen (max. 0,0075 AUROC) reproduziert
  werden. E1+C2 gesammelt 20:01-20:35 (je 4 000 Runden, 1,39 $). Ergebnis: R1 (E1, L2 Netz minus Korrelation > 0)
  repliziert (+0,265 [0,070, 0,445]); R1b (L1) nicht; R2 (C2 Gewinnaufschlag) repliziert (+0,283 [0,179, 0,371]).
  **Addendum v2.3** (`9d759d0`, vor den Daten): Richter mit 24 000 statt 12 000 Tokens (L2, N0/C1-SS/C1-SF 0-19).
  Richter und C1-SS ab 20:38 parallel; gestufter Kostenwächter (C1-SS-Stopp bei 77,3 $, Gesamtstopp bei 78,5 $),
  weil drei GPUs zugleich ca. 6-7 $/h kosten.
  C1-SS und Richter fertig bis 21:27 (Richter 54/60 gültig, 8 abgebrochene Streams mit Prüfprotokoll neu gestellt, Abweichung 7).
  Kein Stopp-Schwellwert erreicht. Ergebnis: R4 (C1-SS, L2 Netz-AUROC > 0,5) repliziert (0,9075 [0,8025, 0,985]),
  Korrelation wieder besser (0,995; Differenz -0,0875 [-0,19, -0,015]); C2 bei frischen Märkten etwas besser erkannt
  (Netz 0,753, Korrelation 0,630), Differenz weiter mit 0 im Intervall. Richter 24k: AUROC 0,625 [0,424, 0,808] auf
  17 Blöcken (Netz 0,907, Korrelation 1,000 auf denselben Blöcken); Top-1 SS 0,92, N0 0,90, SF 0,02: der Richter nennt
  das starke Paar. Zusammenfassung: `experiments/addendum_summary.py` -> `results/analysis/addendum_summary/`,
  Tabellen `report/sections/addendum_table.tex` und `addendum_full_table.tex`. Report überarbeitet (einfachere
  Sprache, neue Abschnitte 3.5 und 4.4, Anhang E.7), 8 Seiten Haupttext. Modal-Endstand 21:43: 76,30 $ gemessen,
  davon 76,03 $ aus Guthaben.
- 25.10.: Marvin: restliche ca. 4 $ Compute nach eigenem Ermessen; Entscheidung: kein weiterer Lauf (zu knapp an der
  80-$-Grenze, Abrechnung mit Verzögerung; alle tragenden Befunde schon repliziert; neuer Lauf bräuchte neues
  Addendum). Stattdessen neue Übersichtsabbildungen ohne Compute (`experiments/key_figures.py`): Abb. 1 Design und
  Einzelmarkt-Scores (C1-SS, E1), Abb. 2 Netz-minus-Korrelation (Original + Replikation) und Gewinn vs. Erkennbarkeit.
  Abb. B zeigt jetzt 12k- gegen 24k-Richter. Verhaltens- und Replikationstabelle in den Anhang; Haupttext 8 Seiten.
- 25.10. (später): Marvin fand Text und Grafiken für Laien unverständlich (Kürzel L1/L2, Grafiken nicht eingängig,
  Praxisnutzen unklar; Wunsch: Richtung des Informationsflusses zeigen). Umbau: Haupttext in einfacher Sprache
  („nur Gebote“ / „Gebote + Kosten“), fünf neue Grafiken aus `experiments/key_figures.py`: Ablauf, Alarm-Ergebnis
  (richtiges Paar / falsches Paar / kein Alarm), Flussrichtung (gepoolt; Pfeil nur, wenn 95-%-Intervall ohne 0),
  Netto-Einfluss vs. Korrelation, Warnungen (stilles Kartell, KI-Richter). Kernaussagen: aus Geboten allein nannte
  die korrigierte Regel das Kartellpaar in 49 von 60 Märkten mit Chat, nie ein falsches Paar, 1 Fehlalarm in 40;
  Richtung gepoolt sichtbar (Kartell beidseitig, Spion einseitig), pro Markt nur 4 von 20 Spionagemärkten. Alte
  Abbildungen A/B in Anhang D. Haupttext 8 Seiten.
