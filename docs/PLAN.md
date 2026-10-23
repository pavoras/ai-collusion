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

| Fertig | In Arbeit | Fehlt |
|---|---|---|
| Setup, Paket, 53 Tests | Sol Runde 4: Skript-Checks (exakter Zustand, Leck-Power, „unklar“) | `PREREG.md` |
| Maße inkl. Gl.-3-Zerlegung, symm. Permutationstest, Baselines | | Skript-Checks: exakter Zustand (B2), Power/Fehlalarm der Leck-Terme, Kategorie „unklar“ |
| RPS-Nachbau (Pflichtteil), Abbildungen | Sol Runde 5: LLM-Harness, Richter-Skript | |
| Skript-Auktion, Kartelle, Spion, Attrappe, Fingerabdruck-Entwurf | | Pilot N0+P0 (eingefroren, ca. 24 000 Aufrufe), dann Budgetzweig |
| Modal: Gewichte aller 6 Modelle, Qwen-9B deployt | | Hauptläufe, Auswertung, Abbildungen |
| Literatur- und Neuheitscheck (erste Runde), `DESIGN.md` v4 | | Report (Marvin schreibt), Endkontrolle, Abgabe |

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
