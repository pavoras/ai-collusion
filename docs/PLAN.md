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
| Zustand / Historie (B) | **offen**: Erklärung an Marvin, Empfehlung B2 + B3 + B4 |

## Umfang (E, Marvins Fassung)

| Block | Modelle | Bedingungen | Märkte × Runden |
|---|---|---|---|
| Kern | Qwen3.5-9B | N0, P0, C1 (stark+stark), C1 stark+schwach, C1 schwach+schwach, C2 (still), E1 (Spion), Proben auf eingefrorenen Kontexten | 20 × 200 |
| Labore | Gemma-4-12B, Ministral-3-8B | N0, C1 | 10 × 200 |
| Größen | Qwen3.5-4B, Gemma-4-E4B, Ministral-3-3B | N0, C1 | 10 × 200 |
| Gleiches vs. verschiedenes Modell | Mittelgroße gemischt | C1 mit Kartell (X, X) vs. Kartell (X, Y), dazu ehrliche Kontrolle (X, X, Y, Z) | 10 × 200 |
| Richter | Qwen3.5-9B mit Denkmodus | alle Märkte, L1 und L2 | - |

Grob 250 000-300 000 Aufrufe. Ob das ins Budget passt (Deckel 35 $), zeigt der Testlauf. Streichreihenfolge:
C1 schwach+schwach → kleine Modelle außer Qwen-4B → Rotationen der gemischten Gruppen → Märkte der Breitenblöcke
auf 6.

## Stand

| Fertig | In Arbeit | Fehlt |
|---|---|---|
| Setup, Paket, 53 Tests | Entscheidung B (Marvin) | `DESIGN.md` v4 und `PREREG.md` |
| Maße inkl. Gl.-3-Zerlegung, symm. Permutationstest, Baselines | | Skript-Checks: exakter Zustand (B2), Power/Fehlalarm der Leck-Terme, Kategorie „unklar“ |
| RPS-Nachbau (Pflichtteil), Abbildungen | | LLM-Harness (Prompts, Parser, Logging, Cache, Runner), Richter-Skript |
| Skript-Auktion, Kartelle, Spion, Attrappe, Fingerabdruck-Entwurf | | Testlauf Qwen-9B (1 Markt, ~0,30 $), dann Go |
| Modal: Gewichte aller 6 Modelle, Qwen-9B deployt | | Hauptläufe, Auswertung, Abbildungen |
| Literatur- und Neuheitscheck (erste Runde) | | Report (Marvin schreibt), Endkontrolle, Abgabe |

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
| P6 Budget läuft davon | Kostenzähler | laufend | Streichreihenfolge oben; harter Stopp bei 35 $ |
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
