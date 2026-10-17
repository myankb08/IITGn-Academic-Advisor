# Scope and modelling decisions

Decisions made by the team that are not stated, or not stated clearly, in a source document.
Each one is cited in rules.json / courses.json as `source_doc: docs/DECISIONS.md` with its id.

| id | decision | decided by | date | why |
|---|---|---|---|---|
| D1 | Scope is M.Tech programmes in the CS and EE departments | hem436 | 2026-10-17 | Project plan targets CS first; EE added to give a second department for programme-level splits |
| D2 | Programmes: MTech-CSE, MTech-AI (CS department); MTech-EE, MTech-ICDT (EE department) | hem436 | 2026-10-17 | The EE site calls ICDT a separate degree, "MTech (Integrated Circuit Design & Technology)", in the same way MTech-AI is separate from MTech-CSE |
| D3 | Every student is on exactly one track, `coursework` or `thesis`, in every programme | hem436 | 2026-10-17 | Adv5 defines both tracks for all M.Tech programmes; the EE site only describes the thesis structure, so the EE/ICDT coursework track uses the Adv5 common rules (48 coursework + 16 project + 2 Aarohan) plus the EE discipline rules |
| D4 | UG course codes named in course plans are stored as `recommended_background`, not hard prerequisites | orchestrator, accepted by hem436 | 2026-10-17 | Plans say "or equivalent" and M.Tech students come from other universities |
