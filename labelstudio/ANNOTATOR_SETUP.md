# Annotator setup (Label Studio 1.23.2)

Each annotator labels on their own, without seeing the other person's labels. A1 = hem436, A2 = Myank.
Read `guidelines_v1.md` (round 1) or `guidelines_v2.md` (round 2) before starting. It takes about 10 minutes.

## 1. Install (once)
```
python3 -m venv .venv-labelstudio
.venv-labelstudio/bin/pip install -r requirements-labelstudio.txt
.venv-labelstudio/bin/label-studio start --port 8080
```
On Windows use `.venv-labelstudio\Scripts\` instead of `.venv-labelstudio/bin/`.
Label Studio opens at http://localhost:8080. Create a local account (any email, it stays on your machine).

## 2. Create the project
1. Create project, name it `R1-A1` or `R1-A2` (round and your annotator id).
2. Labeling Setup > Custom template > Code: paste the whole of `config_v1.xml` > Save.
3. Data Import: upload `round1_tasks.json`.
4. Settings > Annotation > Task sampling: **Sequential** (keeps the seeded item order). Save.

## 3. Label
- Click **Label All Tasks** and work through the 40 items in order.
- For each item fill the levels in this order: 1) decision, 2) error category, 3) edit text (only when the decision is "edit").
- Do not change earlier items after seeing later ones, and do not discuss items with the other annotator until both exports are done.
- Takes about 45 to 60 minutes.

## 4. Export
Project > Export > **JSON** (not JSON-MIN). Rename the downloaded file to `export_A1.json` or `export_A2.json` and send it as is. Do not open and re-save it.
A2 commits it from their own GitHub account to `data/labels/round1/export_A2.json` if possible; otherwise send the file to A1.

Write down the date and time you started and finished; it goes into LABELLING_PROTOCOL.md.
