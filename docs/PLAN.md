# Plan: Frage 1.4, Netto-Einfluss bei LLM-Bietern

Stand: 23.10.2026 abends, Plan v2. Schritt 0 und 1 fertig. Versuchsaufbau im Detail: `docs/DESIGN.md`.
Ausführliches Sprint-Briefing: `../Job Search/Bewerbungsunterlagen/4_Bewerbungen/2026-10_Apart-Research_Special-Projects-Manager/Sprint_AI_Collusion.md`.

## Forschungsfrage

*What does an auditor need to see to catch an AI bid-rigging cartel? Pairwise net influence at three levels of
auditor access, tested on LLM bidders (three labs, two sizes, mixed populations) in a repeated procurement auction
with one covert cartel pair.*

## Pflichtteil laut Sprint-Seite (muss im Report klar abgehakt werden)

| Vorgabe 1.4 | Wo bei uns |
|---|---|
| Netto-Einfluss implementieren | `src/collusion/measures.py` (fertig) |
| an geskriptetem, wiederholtem RPS mit einem bekannten Paar testen | Schritt 2, minimal: Kontrollwerte, CDA-Tabelle, Fig. 3 |
| diskretes Spiel mit 4 Agenten und genau einem gesetzten Paar | Ausschreibung mit 4 Bietern, ein Kartell-Paar |
| Netto-Einfluss vs. einfache Aktionskorrelation vs. LLM-Richter beim Ranking des wahren Paars | auf allen drei Zugriffsstufen |
| (Vorschlag) Marktfall | die Ausschreibung ist der Marktfall |

## Was neu ist (Abgrenzung)

Gleichzeitige Sprint-Arbeit, öffentlich vor Sprintbeginn: Raj-Taware/collusion-net-influence (RPS-Nachbau,
Permutations-Kalibrierung, LLM-RPS mit 3 Agenten) und soumya-nayak-commits/collusion-sprint (4-Spieler-RPS vs.
Cramér's V). Wir nutzen **keinen Code** daraus, zitieren beide mit Commit und Datum und vergleichen unsere
RPS-Kalibrierung mit ihren Zahlen. Neu bei uns:
1. Praxisfall Ausschreibungsabsprache mit privaten Kosten (Eq. 3, teilweise beobachtbar; bisher nie mit LLMs).
2. Zugriffsstufen des Prüfers: Behörde (Gebote) → Plattform (plus Kosten) → Modellzugriff (kontrafaktische
   ehrliche Wiederholung als bedingter Randomisierungstest). Die dritte Stufe zielt direkt auf das offene Problem
   „Ähnlichkeit gleicher Modelle ist keine Absprache“.
3. Gleiches-Modell-Attrappe und gemischte Kartelle (Kartell aus zwei Laboren neben einem unschuldigen
   Gleiches-Modell-Paar).
4. Aktuelle Modelle aus drei Laboren in zwei Größen als Robustheitsachsen des Detektors.
5. Ehrliche Grenze: Ein stilles Kartell, das nur über öffentliche Signale koordiniert, ist für Statistiken, die auf
   diese Signale bedingen, grundsätzlich unsichtbar.

## Zeitplan (deutsche Zeit)

| Wann | Was |
|---|---|
| Fr 23.10. abends | Plan v2, Review durch Astra, Pitch, Modal vorbereiten. Marvin: Sprint-Ressourcen lesen, `modal setup`, HF-Token, Gemma-Lizenz |
| Sa 9-12 | Schritt 2 (RPS minimal) und Schritt 3 (Auktion mit Skript-Agenten, alle Detektoren, Simulationen gratis). Danach Rundenzahl festlegen |
| Sa 12-14 | Schritt 4: LLM-Agenten, Modal-Deploy Qwen-9B, Smoke-Test, Kostenmessung, Go/No-Go mit Marvin |
| Sa 14:15 | Talk Nguyen. Danach `docs/PREREG.md` committen |
| Sa 15-20 | Hauptmodell komplett (N0, P0, C1, C2, Replays), erste Auswertung |
| Sa abends / nachts | übrige 5 Modelle homogen (N0, C1, C2) |
| So vormittags | gemischte Gruppen (D, M2), LLM-Richter, Gesamtauswertung |
| So nachmittags / abends | Abbildungen, Report-Entwurf, Review |
| Mo bis 11:00 | Report fertig, Repo öffentlich (Marvin entscheidet), Abgabe. Harte Frist 12:59 |

## Schritte mit Abnahmekriterien

### 0. Setup (fertig)
`.venv`, Python 3.14, `pip install -e ".[dev]"`, `requirements-lock.txt`.

### 1. Maße (fertig)
γ, Γ, Regel des Papers, Permutationstest, kalibrierte Regel, G-Test, 14 Tests. Noch zu ergänzen in Schritt 3:
Eq. 3 mit getrennten Beobachtungen s_i, s_j (Permutation innerhalb s_i) und der Swap-Test für Stufe L3.

### 2. RPS minimal (0 $, Pflicht)
- 3-Spieler-RPS wie im Paper. Abnahme: γ trifft `METHOD.md`-Kontrollwerte; CDA für CP 0,3/0,4 bei 100-1000 Spielen
  nahe Paper-Tabelle 2; Fehlalarm festes α vs. kalibriert bei Nullhypothese. Eine Abbildung, eine Tabelle.
- Vergleich mit den Zahlen der gleichzeitigen Arbeit (Einheit beachten: dort nats, bei uns bits).

### 3. Auktion mit Skript-Agenten (0 $)
- Spiel nach `DESIGN.md`, geseedet. Ehrliche Skript-Bieter mit Geschichtsreaktion (simuliertes gleiches Modell),
  Skript-Kartell mit Treue q.
- Abnahme: Fehlalarm ~5 % auf L1-L3 ohne Kartell; Attrappen-Effekt sichtbar auf L1/L2 und auf L3 weg; Power-Kurve
  über q und Runden. Daraus Märkte × Runden festlegen (Start: 30 × 60).

### 4. LLM-Läufe (Modal, ca. 25 $ von 50 $)
- Agenten-Harness (OpenAI-kompatibel), Prompts symmetrisch, JSON, Logging jeder Anfrage (Prompt-Hash, Rohantwort,
  Gebot, Nachricht, Seed, Latenz, Token), Antwort-Cache, damit alles offline neu ausgewertet werden kann.
- Smoke-Test: 1 Markt × 10 Runden pro Modell. Abnahme: < 2 % ungültige Antworten, Gebote streuen (Entropie > 0),
  Kosten pro 1000 Aufrufe gemessen. Hochrechnung an Marvin, dann Go.
- Reihenfolge: Qwen-9B komplett → Gemma-12B, Ministral-8B → Qwen-4B → Gemma-E4B, Ministral-3B → D, M2.

### 5. Auswertung und Report
- Abbildungen: (1) RPS-Kalibrierung, (2) Detektion je Zugriffsstufe und Bedingung, (3) Fehlalarm Attrappe L1-L3,
  (4) Labore × Größen, (5) Treffer vs. Rundenzahl. Tabellen mit Wilson-Intervallen.
- Report in der Vorlage, max. 8 Seiten, Abstract 150-250 Wörter, Anhang „Limitations and Dual-Use / Ethical
  Considerations“. Autor „Marvin Kemper, Independent“. Gleichzeitige Arbeit in Related Work.

## Prüfung (wie wir sicherstellen, dass die Ergebnisse stimmen)

1. Unit-Tests für Maße, Auszahlungen, Parser, Skript-Strategien.
2. Simulationen mit bekannter Wahrheit vor jedem LLM-Aufruf (Positiv, Negativ, Attrappe, Swap-Test-Gültigkeit).
3. Smoke-Test mit Abbruchkriterien.
4. Manipulationschecks: Hat das Kartell wirklich gekungelt (Scheingebote, Rotation, Preisaufschlag, Nachrichten)?
5. Vorregistrierung (`docs/PREREG.md`) mit Git-Zeitstempel vor den Hauptläufen.
6. Gepaarte Seeds über Bedingungen und Modelle; Wilson-Intervalle; alle Antworten gecacht.
7. Review durch Astra (Plan jetzt, Code und Auswertung später) und Endkontrolle: frischer Clone rechnet alle Zahlen
   des Reports aus den Logs nach.

## Ausweichleiter

| Zeitpunkt | Wenn … | dann … |
|---|---|---|
| Sa 14 Uhr | Modal läuft nicht stabil | nur Qwen-9B und ein zweites Modell; L3 nur für Qwen-9B |
| Sa 20 Uhr | LLM-Kartell kungelt nicht nachweisbar (Manipulationscheck negativ) | Kartell-Anweisung deutlicher, P0 als Hauptbeleg, Befund berichten |
| So 12 Uhr | Zeit knapp | Streichliste: kleine Gemma/Ministral → M2 → C2 außer Hauptmodell → L3 außer Hauptmodell |
| So abends | LLM-Teil unbrauchbar | RPS + Skript-Auktion (L1-L3) als Ergebnis, LLM als Pilot |

## Offene Punkte

- Modal: Token (`modal setup`), HF-Token als Modal-Secret, Gemma-Lizenz auf Hugging Face akzeptieren.
- Literatur prüfen und zitieren: Screens für Ausschreibungsabsprachen (z. B. Imhof et al. 2018, Huber & Imhof 2019),
  bedingter Randomisierungstest (Candès et al. 2018), Efimov 2024. Erst nach Prüfung in den Report.
- Richter-Modell: Qwen3.5-9B mit Denkmodus; Gegenprobe mit Gemma-12B auf einer Teilmenge.

## Log

- 23.10.: Projekt und Dokumentation angelegt, Paper gelesen, Einheit (Bits) aus den Paper-Zahlen abgeleitet,
  Kontrollwerte berechnet.
- 23.10. abends: Schritt 0 (`.venv`, Python 3.14, `pip install -e ".[dev]"`, `requirements-lock.txt`) und
  Schritt 1 (`src/collusion/measures.py`, 14 Tests grün). Plug-in-γ trifft die Kontrollwerte bei N = 200 000
  auf ±0,003 bit. Zusätzlich zum Plan: Permutationstest mit Bonferroni-Regel (`detect_calibrated`) und
  asymptotischer G-Test (`g_test_pvalue`) als billiger Gegencheck.
- 23.10. abends: Lokale Modelle verworfen (PC zu schwach), nur Modal. Zwei gleichzeitige Sprint-Repos gefunden
  (Raj-Taware, soumya-nayak), die RPS-Kalibrierung und LLM-RPS schon abdecken. Neuer Kern: Ausschreibung mit
  privaten Kosten, Zugriffsstufen L1-L3, Attrappe und gemischte Kartelle. Plan v2 und `DESIGN.md`.
