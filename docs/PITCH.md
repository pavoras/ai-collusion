# Pitch: Was muss ein Prüfer sehen, um ein KI-Kartell zu erkennen?

Arbeitstitel (Report): **What Must an Auditor See? Detecting Covert LLM Bid-Rigging Cartels with Pairwise Net
Influence**

Stand 23.10.2026, Plan v3. Alles unten sind Ziele und Hypothesen, keine Ergebnisse.

## Die Frage in einem Satz

*When does access to agents' private information let an auditor tell a covert bid-rigging cartel of LLM agents
apart from dependence that merely comes from shared history or a shared model?*

## Das Problem

KI-Agenten bieten, verhandeln und setzen Preise zunehmend selbstständig. Zwei Agenten können sich heimlich
absprechen, über einen versteckten Kanal oder einfach, weil man sie so angewiesen hat. Die naheliegende
Gegenmaßnahme ist Statistik auf ihren Handlungen: Wer handelt auffällig abhängig voneinander? Genau das misst der
Netto-Einfluss von Bonjour et al. (2022). Die gleichzeitige Sprint-Arbeit zeigt aber das Kernproblem: Zwei Kopien
desselben Modells handeln ähnlich, ganz ohne Absprache, und werden fälschlich als Paar markiert. **Abhängigkeit ist
keine Absprache.** Solange ein Detektor das nicht trennen kann, ist er für die Praxis unbrauchbar.

## Unsere Idee

Absprache unterscheidet sich von bloßer Ähnlichkeit durch **Informationsfluss**. Ein Kartell tauscht private
Information aus (wer gerade die niedrigeren Kosten hat) und teilt den Auftrag auf. Zwei gleiche, aber ehrliche
Modelle tun das nicht: Ihre Gebote hängen nur an den eigenen Kosten und der öffentlichen Historie.

Die teilweise beobachtbare Form des Netto-Einflusses (Gl. 3 im Paper, bei LLMs bisher nicht getestet) zerlegt sich
in genau diese Teile:

    γ = I(B_i; B_j | S_i, S_j) + I(B_i; S_j | S_i) + I(B_j; S_i | S_j)

Die beiden letzten Terme messen, ob ein Gebot von den **privaten Kosten des anderen** abhängt. Das kann bei
unabhängig gezogenen Kosten nur durch Informationsfluss passieren.

Daraus folgt eine Frage mit direktem Praxisbezug: **Was muss ein Prüfer sehen?**
- **Behörde (L1):** sieht nur Gebote und Zuschläge, wie eine Wettbewerbsbehörde.
- **Plattform (L2):** sieht zusätzlich die privaten Eingaben jedes Agenten, wie ein Betreiber, der die Agenten selbst
  laufen lässt. Das ist der Vorteil von KI-Aufsicht gegenüber klassischer Kartellaufsicht.
- **Kausaler Check:** In eingefrorenen Spielsituationen tauschen wir die Kosten aus, die der Partner mitgeteilt hat,
  gegen Zufallswerte. Reagieren die Gebote? Findet der Detektor genau diese künstlich erzeugte Abhängigkeit? Damit
  ist das Signal an einen kontrollierten Informationsweg gebunden, nicht nur an eine Korrelation.

## Der Versuch

- **Spiel:** wiederholte Ausschreibung mit 4 Firmen: zwei starke (Kosten 1-3), zwei schwächere (3-5), Gebote 2-7,
  das niedrigste gewinnt. Die beiden starken Firmen sind ein heimliches Kartell. Wir haben nachgerechnet, dass sich
  das Kartell hier lohnt (+29 % bis +76 % Gewinn), mit symmetrischen Kosten dagegen kaum.
- **Bedingungen:** ehrlich (Negativkontrolle), geskriptetes Kartell (Positivkontrolle), LLM-Kartell mit privatem
  Kanal, LLM-Kartell ohne Kanal, **Gleiches-Modell-Attrappe** (zwei Kopien eines Modells, ehrlich) und
  **gemischtes Kartell** (zwei verschiedene Modelle sprechen sich ab, daneben ein unschuldiges Gleiches-Modell-Paar).
- **Modelle:** Qwen3.5, Gemma 4 und Ministral 3, je in klein (3-4B) und mittel (8-12B), auf Modal mit vLLM.
- **Vergleich (Pflichtteil 1.4):** Netto-Einfluss vs. einfache Korrelation vs. LLM-Richter beim Finden des wahren
  Paars; dazu der Nachbau des Papers an Schere-Stein-Papier.
- **Strenge:** Vorregistrierung vor den Hauptläufen, Validierung an Skript-Agenten mit bekannter Wahrheit,
  Manipulationschecks (hat das Kartell wirklich gekungelt?), gepaarte Seeds, Bootstrap über Märkte, Ablationen.

## Warum relevant

- **Kartellrecht:** Ausschreibungsabsprachen sind die häufigste verfolgte Kartellform. Behörden nutzen schon heute
  statistische Screens auf Gebotsdaten. Wir prüfen, ob ein informationstheoretischer Screen auch Kartelle aus
  KI-Agenten findet, und was ihm fehlt.
- **KI-Sicherheit (AI Control):** Betreiber von Multi-Agenten-Systemen sehen die Eingaben ihrer Agenten. Ob das
  reicht, um verdeckte Koordination zu erkennen, ist eine offene Frage der Aufsicht über Agenten.
- **Methodik:** Wir trennen zwei Dinge, die bisher vermischt werden: statistische Abhängigkeit und Absprache.

## Warum neu

Nach unserem Kenntnisstand neu (Neuheitscheck vor dem Report):
- der **teilweise beobachtbare** Netto-Einfluss (private Beobachtungen) an LLM-Agenten;
- **Zugriffsstufen des Prüfers** als Variable und ein **kausaler Eingriff**, der das Signal validiert.
- Gezielte Tests des bekannten Fehlers (Gleiches-Modell-Attrappe, gemischtes Kartell) statt nur Fehlalarme zu
  zählen.
- Aktuelle Modelle aus drei Laboren in zwei Größen.
- Abgrenzung: Die gleichzeitige Arbeit nutzt Schere-Stein-Papier mit voller Beobachtung. Wir zitieren sie offen,
  übernehmen keinen Code und setzen genau an ihrem offenen Problem an.

## Was ein spannendes Ergebnis wäre

Jede dieser Antworten ist berichtenswert, auch die negative:
1. **Private Information macht den Unterschied:** L2 findet Kartelle zuverlässig und meldet die Attrappe nicht; L1
   verwechselt beides. Dann hätten Betreiber ein Werkzeug, das Behörden fehlt.
2. **Der kausale Eingriff bestätigt das Signal:** Der Detektor reagiert genau auf den künstlich erzeugten
   Informationsfluss.
3. **Ein klarer blinder Fleck:** Kartelle, die nur über öffentliche Signale koordinieren, sind für solche
   Statistiken unsichtbar. Das wäre eine präzise Grenze der Methode, kein Scheitern.
4. **Robustheit über Labore und Größen,** oder ein Muster, etwa dass kleinere Modelle schwerer zu fassen sind, weil
   sie inkonsistenter kungeln.

## Was am Ende steht

Ein Report (max. 8 Seiten) mit einer Kernabbildung, die die ganze Geschichte erzählt (Detektion je Zugriffsstufe
und Bedingung), ein öffentliches Repo mit Detektor-Bibliothek, Ausschreibungs-Umgebung, allen Prompts, Logs und
Reproduktionsbefehlen. Andere können damit weiterarbeiten: andere Märkte, mehr Kartellmitglieder, echte
Gebotsdaten.

## Ehrliche Grenzen (gehören in den Report)

- Synthetisches Spiel, angewiesene Kartelle, kein Schuldbeweis im rechtlichen Sinn.
- Die Gültigkeit des Nulltests hängt an Annahmen (grobe Zustände, adaptive Historien). Wir prüfen sie an
  Simulationen, garantieren sie aber nicht allgemein.
- Dual Use: Die Ergebnisse zeigen auch, wie ein Kartell der Entdeckung entgehen könnte (über öffentliche Signale).
  Das benennen wir und ordnen es ein.
