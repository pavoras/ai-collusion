# Plan: Frage 1.4, Netto-Einfluss bei LLM-Agenten

Stand: 23.10.2026 abends, Schritt 0 und 1 fertig. Ausführliches Sprint-Briefing (Talks, Tracks, Regeln,
Bewertung): `../Job Search/Bewerbungsunterlagen/4_Bewerbungen/2026-10_Apart-Research_Special-Projects-Manager/Sprint_AI_Collusion.md`.

## Forschungsfrage (Arbeitstitel)

*Does pairwise net influence detect a covertly coordinating pair of LLM agents, and does a permutation-calibrated
threshold make it more reliable than the fixed threshold of the original paper?*

Zwei Beiträge, der erste ist kostenlos und sicher, der zweite ist die Neuheit:
1. **Nachbau und Kalibrierung** an Schere-Stein-Papier (RPS): Paper-Ergebnisse reproduzieren, Fehlalarmrate des
   festen α messen, Permutationstest als bessere Schwelle.
2. **LLM-Agenten**: erstmals ein Spiel mit 4 LLM-Agenten und genau einem heimlichen Paar. Vergleich von
   Netto-Einfluss, einfacher Korrelation und LLM-Richter.

## Zeitplan (deutsche Zeit)

| Wann | Was |
|---|---|
| Fr 23.10. abends | Setup auf dem Arbeits-PC, Schritt 1 starten. Optional Talks 19:15 (Steganografie erkennen), 20:15 (Colosseum) |
| Sa 24.10. vormittags | Schritt 1 und 2 fertig (RPS, kostenlos) |
| Sa 24.10., 14:15 | Talk Khanh Linh Nguyen (wichtigster Talk), 17:00 Matthew Lee „Defining AI Collusion“ |
| Sa 24.10. nachmittags | Schritt 3: LLM-Spiel, erst Smoke-Test, dann Kontrollen |
| So 25.10. | Schritt 3 Hauptläufe, Schritt 4 Auswertung, Report-Entwurf |
| Mo 26.10. vormittags | Report fertig, **Abgabe bis 12:59** |

## Schritte mit Abnahmekriterien

### 0. Setup
- Python-Projekt mit `.venv`, Abhängigkeiten: numpy, scipy, matplotlib, pytest (später ein API-Client).
- Ordner: `src/collusion/` (Maße, Spiele, Agenten), `experiments/` (Skripte, die Abbildungen und Tabellen
  erzeugen), `results/` (Zahlen als JSON/CSV, Abbildungen), `tests/`.
- `.env` mit dem API-Schlüssel legt Marvin selbst an.

### 1. Maße implementieren (0 $)
- `influence(actions_i, actions_j, states) -> γ in bits` (Plug-in, Gl. 3/6), `net_influence` (Gl. 4),
  `detect(α)` (Gl. 5, „genau ein Paar“), `permutation_test` (a_i innerhalb jedes Zustands mischen; p-Wert und
  bias-korrigiertes γ).
- Tests: unabhängige Zufallsspieler → γ nahe 0 (im Rahmen des bekannten Bias); B = Funktion von A → γ = log2 3;
  Symmetrie γ(i; j) = γ(j; i) im simultanen Fall.

### 2. RPS nachbauen und kalibrieren (0 $)
- 3-Spieler-RPS mit Auszahlungsregeln aus dem Paper; Spieler A, C zufällig, B Assistent mit CP.
- **Abnahme**: γ(A; B) trifft die Kontrollwerte in `METHOD.md`; CDA-Tabelle für CP 0.3/0.4 und 100–1000 Spiele
  liegt nahe an Paper-Tabelle 2 (Abweichungen erklären, z. B. Zustand, Einheit).
- Neu: Fehlalarmrate unter der Nullhypothese (alle zufällig) für festes α = 0,05 vs. Permutationstest, über N.
  Trefferquote bei CP 0.1/0.2/0.3 für beide Schwellen. 4-Spieler-Variante (3 Ehrliche, 1 Paar).
- Ergebnis: 2 Abbildungen (Γ über CP; CDA und Fehlalarm über N), 1 Tabelle. Das ist schon ein abgabefähiger Kern.

### 3. LLM-Spiel mit 4 Agenten (5–50 $)
- **Empfehlung**: eigenes kleines Spiel statt der Doppelauktion, weil es diskret, billig und kontrollierbar ist.
  4-Spieler-RPS (gleiche Gewinnregeln) oder ein anderes diskretes Simultanspiel. Jede Runde: jeder Agent sieht die
  Historie der letzten Runden und wählt eine Aktion (JSON-Antwort, ungültige Antworten zählen und loggen).
- **Bedingungen** (je gleiche Seeds):
  - Kontrolle negativ: 4 unabhängige Agenten, kein Paar.
  - Paar per System-Prompt: zwei Agenten wissen, dass sie ein Team sind und den Teampunktestand maximieren.
  - Paar mit privatem Kanal: eine kurze Nachricht pro Runde vor dem Zug.
  - Positivkontrolle: ein geskripteter Assistent (wie RPS-B) neben LLM-Spielern, damit das Maß im LLM-Kontext
    nachweislich anschlägt.
- Umfang: 20–40 Spiele à 15–25 Runden pro Bedingung, Temperatur 0,7–1,0, ein günstiges Modell
  (z. B. über Nebius oder OpenRouter). Erst Smoke-Test mit 1 Spiel, Kosten hochrechnen, Marvin nennen.
- Logs: jede Runde mit Prompt-Hash, Rohantwort, geparster Aktion, Nachrichten, Punkten.
- Vergleich: Rangfolge des wahren Paars durch (a) Netto-Einfluss mit Permutationstest, (b) einfache
  Aktionskorrelation, (c) LLM-Richter, der das Spielprotokoll liest und das verdächtigste Paar nennt.
- Optional (nur wenn Zeit): Statistik auf die Agrawal-Doppelauktion aus dem Starter-Repo anwenden.

### 4. Auswertung und Report
- Offizielle Vorlage (Link in `RESOURCES.md`), max. 8 Seiten ohne Literatur/Anhang, Abstract 150–250 Wörter,
  Autor „Marvin Kemper, Independent“, Anhang „Limitations and Dual-Use / Ethical Considerations“.
- Aufbau: Einleitung, verwandte Arbeiten, Methode (Modelle, Prompts, Seeds, Metriken), Ergebnisse (mit Streuung,
  Baseline, Kontrollen), Diskussion, Grenzen, Literatur.
- Repo öffentlich machen (Marvin entscheidet), README mit Reproduktionsbefehlen.
- Abgabe über das Formular auf der Sprint-Seite. Korrekturen bis zur Frist: mit exakt gleichem Titel neu einreichen.

## Ausweichleiter

| Zeitpunkt | Wenn … | dann … |
|---|---|---|
| Sa ca. 18 Uhr | das LLM-Spiel liefert keine sauberen Daten (Parsing, Kosten, kaum Varianz) | Schritt 3 verkleinern: nur negative Kontrolle und System-Prompt-Paar |
| So abends | die LLM-Runde liefert nichts Verwertbares | RPS-Nachbau plus Kalibrierung als Ergebnis, LLM-Runde als Pilot und Ausblick |
| jederzeit | alles hakt | Frage 2.2 (Worte und Taten), 5–30 $, fertiger Starter-Code |

## Offene Punkte

- Auf der Sprint-Seite stand am 23.10. ohne Login „The submission window has closed“. Vermutlich ein Anzeigefehler
  vor Öffnung des Fensters; eingeloggt prüfen, sonst im Discord „help-desk“ fragen.
- Zustand für RPS: im Paper nicht im Haupttext (Anhang A im Supplement). Start ohne Zustand.

## Log

- 23.10.: Projekt und Dokumentation angelegt, Paper gelesen, Einheit (Bits) aus den Paper-Zahlen abgeleitet,
  Kontrollwerte berechnet.
- 23.10. abends: Schritt 0 (`.venv`, Python 3.14, `pip install -e ".[dev]"`, `requirements-lock.txt`) und
  Schritt 1 (`src/collusion/measures.py`, 14 Tests grün). Plug-in-γ trifft die Kontrollwerte bei N = 200 000
  auf ±0,003 bit. Zusätzlich zum Plan: Permutationstest mit Bonferroni-Regel (`detect_calibrated`) und
  asymptotischer G-Test (`g_test_pvalue`) als billiger Gegencheck.
