# ai-collusion: Arbeitsregeln

Marvins Beitrag zum **AI Collusion Research Sprint** von Apart Research (23.–25.10.2026), Frage **1.4**:
Findet ein informationstheoretisches Maß (Netto-Einfluss nach Bonjour et al. 2022) das heimliche Absprache-Paar,
auch bei LLM-Agenten?

Vor jeder Arbeit lesen:
1. `docs/PLAN.md`: Zeitplan, Schritte mit Abnahmekriterien, Ausweichleiter, Stand
2. `docs/METHOD.md`: Formeln, Einheiten, Kontrollwerte, Fallstricke
3. `docs/RESOURCES.md`: alle Links (Sprint, Paper, Starter-Code, APIs, Vorlage)

## Regeln

- **Frist**: Abgabe bis **Montag, 26.10.2026, 12:59 Uhr** deutscher Zeit (Sonntag 23:59 AoE). Lieber ein sauberes
  kleines Ergebnis als ein halbes großes.
- **Sprache**: mit Marvin Deutsch. Code, Kommentare, README und Report auf Englisch.
- **Ehrlichkeit**: Keine erfundenen Zahlen, Quellen oder Ergebnisse (führt zur Disqualifikation). Jede Zahl im
  Report kommt aus einem Lauf, der im Repo reproduzierbar ist (Seed, Befehl, Datei).
- **Vorher geschriebener Code**: Code vor Freitag 23.10. müsste als „preexisting“ markiert werden. Bisher gibt es
  keinen; alles im Repo entsteht ab dem 23.10.
- **KI-Werkzeuge** sind im Sprint ausdrücklich erlaubt. Größere, klar abgegrenzte Code-Runden darf Codex (Sol)
  übernehmen (Marvin, 23.10.); Claude plant, reviewt, prüft und committet. Claudes 5-h- und Wochenlimit im Blick
  behalten. Regeln für Codex: `AGENTS.md`.
- **API-Schlüssel**: Marvin trägt sie selbst in `.env` ein (`OPENROUTER_API_KEY` oder `NEBIUS_API_KEY`). Nie in
  Git, nie in Logs oder Chat. Ausgabelimit beim Anbieter ca. 30 $. Modal (Hauptweg): 80 $ Guthaben, davon höchstens 50 $ (Marvin, 23.10.). Vor jedem LLM-Lauf Kosten schätzen und nennen.
- **Erst die Positivkontrolle**, dann Varianten. Erst kostenlos (Skripte), dann kleine LLM-Läufe, dann größere.
- **Git**: kleine Commits, keine Attributionszeilen. Repo ist privat, bis Marvin es für die Abgabe öffentlich macht.
- **Projekte-Sync**: Dieses Repo wird über `..\sync.ps1` mitverwaltet (pull vor der Arbeit, push danach).
