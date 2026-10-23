# Plan: Frage 1.4, Netto-Einfluss bei LLM-Bietern

Stand: 23.10.2026 abends, Plan v3 (v2 von Astra geprüft, Runde 1). Schritt 0 und 1 fertig. Versuchsaufbau:
`docs/DESIGN.md`. Pitch: `docs/PITCH.md`. Sprint-Briefing:
`../Job Search/Bewerbungsunterlagen/4_Bewerbungen/2026-10_Apart-Research_Special-Projects-Manager/Sprint_AI_Collusion.md`.

## Forschungsfrage

*When does access to agents' private information let an auditor tell a covert bid-rigging cartel of LLM agents
apart from dependence that merely comes from shared history or a shared model?*

## Ziel: volle Punktzahl in allen drei Kategorien (Marvin: „Excellency across all measures“)

| Kategorie | Was eine 5 verlangt | Wie wir sie erreichen |
|---|---|---|
| Impact & Innovation | neu fürs Feld, nicht Replikation; wichtig, wenn es klappt | offenes Problem der gleichzeitigen Arbeit („Abhängigkeit ist keine Absprache“) mit privater Information und einem kausalen Eingriff angehen; Praxisfall mit Anschluss an Kartellrecht (Screens) und AI Control (Betreiber-Aufsicht); wiederverwendbares Werkzeug und Benchmark |
| Execution | sauber, robust validiert, überraschende Befunde | Vorregistrierung, Skript-Validierung mit bekannter Wahrheit, Positiv-/Negativkontrolle, Manipulationschecks, gepaarte Seeds, Markt-Bootstrap, Ablationen, ehrliche Grenzen |
| Presentation | Vorbild an Klarheit | eine Kernabbildung, die die Geschichte trägt (Detektion je Zugriffsstufe × Bedingung); klare Begriffe; jede Zahl reproduzierbar aus dem Repo |

## Pflichtteil laut Sprint-Seite (im Report sichtbar abhaken)

| Vorgabe 1.4 | Wo bei uns |
|---|---|
| Netto-Einfluss implementieren | `src/collusion/measures.py` (fertig) |
| an geskriptetem, wiederholtem RPS mit einem bekannten Paar testen | Schritt 2, minimal: Kontrollwerte, CDA-Tabelle, Fehlalarm |
| diskretes Spiel mit 4 Agenten und genau einem gesetzten Paar | Ausschreibung mit 4 Bietern, ein Kartell-Paar |
| Netto-Einfluss vs. einfache Aktionskorrelation vs. LLM-Richter beim Ranking des wahren Paars | auf den Stufen L1 und L2 |
| (Vorschlag) Marktfall, Doppelauktion | Ausschreibung als Marktfall; Begründung, warum statt Doppelauktion (diskret, private Kosten, ein Paar) |

## Was neu ist (Abgrenzung, vorsichtig formuliert)

Gleichzeitige Sprint-Arbeit, öffentlich vor Sprintbeginn: Raj-Taware/collusion-net-influence (RPS-Nachbau,
Permutations-Kalibrierung, LLM-RPS mit 3 Agenten) und soumya-nayak-commits/collusion-sprint (4-Spieler-RPS vs.
Cramér's V). Wir nutzen **keinen Code** daraus, zitieren beide mit Commit und Datum und vergleichen die
RPS-Kalibrierung mit ihren Zahlen. Unser Beitrag:
1. Teilweise beobachtbarer Fall (Eq. 3) mit privaten Kosten, inklusive Zerlegung in Aktionsabhängigkeit und
   Abhängigkeit von fremden Beobachtungen; bei LLM-Agenten nach unserem Kenntnisstand nicht getestet (prüfen).
2. Zugriffsstufen des Prüfers: Behörde (Gebote) vs. Plattform (plus Kosten), dazu Proben auf eingefrorenen
   Kontexten: Ehrlich-Referenz-Swap (explorativ) und **Partnerkosten-Eingriff** (kausaler Check des Signals).
3. Gleiches-Modell-Attrappe und gemischtes Kartell neben einem unschuldigen Gleiches-Modell-Paar.
4. Aktuelle Modelle aus drei Laboren in zwei Größen als Robustheitsachsen des Detektors.

## Zeitplan (deutsche Zeit)

| Wann | Was |
|---|---|
| Fr 23.10. abends | Plan v3, Pitch, Modal vorbereitet. Marvin: Ressourcen lesen, `modal setup`, Proxy-Token anlegen |
| Sa 9-12 | Schritt 2 (RPS minimal) und Schritt 3 (Auktion mit Skript-Agenten, Simulationen). Danach PREREG-Zahlen |
| Sa 12-14 | Schritt 4a: LLM-Harness, Deploy Qwen-9B, Smoke-Test, Durchsatz- und Kostenmessung, Go/No-Go mit Marvin |
| Sa 14:15 | Talk Nguyen. Danach `docs/PREREG.md` committen |
| Sa 15-20 | Hauptmodell: N0, P0, C1, C2; erste Auswertung |
| Sa abends / nachts | übrige 5 Modelle: N0, C1 |
| So vormittags | D, M2, Proben auf eingefrorenen Kontexten, LLM-Richter |
| So nachmittags / abends | Gesamtauswertung, Abbildungen, Report-Entwurf, Review durch Astra |
| Mo bis 11:00 | Report fertig, Repo öffentlich (Marvin entscheidet), Abgabe. Harte Frist 12:59 |

## Schritte mit Abnahmekriterien

### 0. Setup (fertig)
`.venv`, Python 3.14, `pip install -e ".[dev]"`, `requirements-lock.txt`. Modal-Dateien in `cloud/`.

### 1. Maße (fertig, Ergänzungen in Schritt 3)
Vorhanden: γ, Γ, Regel des Papers, Permutationstest, kalibrierte Regel, G-Test, 14 Tests. Ergänzen: Eq. 3 mit
getrennten Zuständen und Zerlegung (Test: Summe der drei Terme = Eq. 3), symmetrischer Permutationstest (beide
Gebote innerhalb ihrer Zustände), Paar-Score min(Γ_ij, Γ_ji), Swap-Test.

### 2. RPS minimal (0 $, Pflicht)
3-Spieler-RPS wie im Paper. Abnahme: γ trifft die Kontrollwerte; CDA für CP 0,3/0,4 bei 100-1000 Spielen nahe
Paper-Tabelle 2; Fehlalarm festes α vs. kalibriert. Eine Abbildung, eine Tabelle, Vergleich mit gleichzeitiger
Arbeit (dort nats, hier bits).

### 3. Auktion mit Skript-Agenten (0 $)
- Spiel nach `DESIGN.md` v3. Ökonomik-Check: Skript-Kartell ist profitabel gegen Skript-Ehrliche (Gewinn, Zuschlag,
  Entropie).
- Simulationen: Gültigkeit der Nullverteilung (Fehlalarm), Tabellenbelegung, Power über q und Runden,
  Attrappen-Effekt (Ergebnis offen), konstruiertes stilles Kartell (blinder Fleck nur unter dieser Bedingung).
- Ergebnis: Rundenzahl, Märkte, Zustandsdefinition, primäre Einheit für PREREG.

### 4. LLM-Läufe (Modal, Deckel 35 $ von ~50 $)
- 4a Harness (OpenAI-kompatibel), symmetrische Prompts, Logging jeder Anfrage (Prompt-Hash, Rohantwort, Gebot,
  Nachricht, Seed, Latenz, Token), Antwort-Cache. Smoke-Test: 1 Markt × 10 Runden je Modell; Abnahme: < 2 %
  ungültig, Gebote streuen, Kosten pro 1000 Aufrufe gemessen. Hochrechnung an Marvin, dann Go.
- 4b Reihenfolge: Qwen-9B (N0, P0, C1, C2) → Gemma-12B, Ministral-8B (N0, C1) → Qwen-4B, Gemma-E4B, Ministral-3B
  (N0, C1) → D, M2 → Proben → Richter.

### 5. Auswertung und Report
- Kernabbildung: Detektion (Top-1, Fehlalarm) je Stufe L1/L2 × Bedingung. Dazu RPS-Kalibrierung, Attrappe,
  Labore × Größen, Partnerkosten-Eingriff, Treffer vs. Rundenzahl.
- Report in der Vorlage, max. 8 Seiten, Abstract 150-250 Wörter, Anhang „Limitations and Dual-Use / Ethical
  Considerations“ (synthetischer Nachweis, kein Schuldbeweis; mögliche Umgehung benennen). Autor „Marvin Kemper,
  Independent“.

## Prüfung

1. Unit-Tests für Maße (inkl. Eq.-3-Zerlegung), Auszahlungen, Parser, Skript-Strategien.
2. Skript-Simulationen mit bekannter Wahrheit vor jedem LLM-Aufruf.
3. Smoke-Test mit Abbruchkriterien und Kostenmessung.
4. Manipulationschecks, in PREREG definiert; alle gesetzten Kartelle berichten, erfolgreiche getrennt.
5. Vorregistrierung mit Git-Zeitstempel vor den Hauptläufen.
6. Gepaarte Seeds; Bootstrap über Märkte; alle Antworten gecacht.
7. Astra-Reviews (Plan erledigt; Code und Auswertung später); Endkontrolle: frischer Clone rechnet alle Zahlen nach.

## Ausweichleiter

| Zeitpunkt | Wenn … | dann … |
|---|---|---|
| Sa 14 Uhr | Modal läuft nicht stabil oder Durchsatz zu klein | nur Qwen-9B plus ein zweites Labor; Proben nur Partnerkosten-Eingriff |
| Sa 20 Uhr | LLM-Kartell kungelt nicht nachweisbar | Anweisung deutlicher, P0 als Hauptbeleg, Befund berichten |
| So 12 Uhr | Zeit knapp | Streichliste: weitere Mischungs-Rotationen → Swap-Test → kleine Modelle von Gemma/Ministral → C2 |
| So abends | LLM-Teil unbrauchbar | RPS + Skript-Auktion (L1/L2) als Ergebnis, LLM als Pilot |

## Offene Punkte

- Marvin: `modal setup`, Proxy-Token im Modal-Dashboard anlegen und in `.env` eintragen (siehe `cloud/README.md`).
- Literatur prüfen und zitieren: Screens für Ausschreibungsabsprachen (z. B. Imhof et al. 2018, Huber & Imhof 2019),
  bedingter Randomisierungstest (Candès et al. 2018), Efimov 2024. Erst nach Prüfung in den Report.
- Neuheitscheck Eq. 3 bei LLM-Agenten und Partnerkosten-Eingriff (Suche vor dem Report).

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
