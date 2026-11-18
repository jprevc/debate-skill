@README.md

## Working in this debate

- This is a run of the `debate` skill (`<skill dir>`). To continue it, invoke the skill: it resumes from `agent/state.md`.
- Never write, rename or delete anything in `sources/`. To use a new user file, put it in `sources/` and extract it with `evidence.py import agent sources/<file> --name <slug>`.
- Every fix to a Report or the Confrontation goes into every language version (`outputs/report*.md`, `outputs/confrontation*.md`); then rebuild the HTML Reports and the ledger (see "Rebuilding the Reports"). The Confrontation says only what the Claims in each turn's ID line say.
- Log every change to the record in the Log section of `agent/state.md`, with the date.
- The Report never recommends a decision. Keep its title, captions and text neutral.
- Keep the Advocates, Auditors, Judge, Editor and Checker blind to the user: dispatch them only with what the skill's dispatch prompts name, never with the user's leanings.
