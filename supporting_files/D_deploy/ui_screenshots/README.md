# UI screenshots (15 Nov 2026)

Image `iitgn-advisor:a2` from tag `a2-final` (model 10, commit `74d734f2d5`) on arka, `--cpus 8 --memory 8g`, port 7860
published on 127.0.0.1 only; headless Chrome with every host except 127.0.0.1 blocked.

| file | what it shows |
|---|---|
| `ui_ask_rejected_full.png` | Ask tab, bundled example "Can I register for EE 618 next term?" (MTech-ICDT). The model said no (not offered in Sem-II); the rule engine says eligible with offering unknown, so the check REJECTED the model and the rule-engine answer is shown. Confidence 0.993, latency 29.2 s. |
| `ui_ask_pass_full.png` | Ask tab, bundled example "Am I allowed to take CS 613 in the coming term?" (MTech-AI, coursework, CS 610 and CS 612 done). PASS: consistent with the rule engine; eligible, offered in 2026-27 Sem-I (timetable row 245). Confidence 0.997, latency 34.9 s. |
| `ui_ask_core_full.png` | Ask tab, bundled example "Which core courses do I still need to finish?" (MTech-CSE AI/ML, thesis). The check rejected the model, so the rule-engine answer is shown. 2 of the 4 hand-written UI examples are rejected; on replay traffic 90% of v10 answers pass the check (supporting_files/E_monitoring/advisor_v10/windows.csv, windows 1 to 6). |
| `ui_monitoring_full.png` | Monitoring tab after 2 requests. With only 2 requests the window statistics are not meaningful; the alerts show the display, not drift. |
| `ui_validation_full.png` | Validation tab: fixed subset of the first 5 gold items, all 5 metrics PASS against the reported values, 285.5 s on this CPU. |
