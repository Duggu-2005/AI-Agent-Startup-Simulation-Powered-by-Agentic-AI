# VyavasAI Experiment Runner

This directory contains the reproducible experiment runner used to execute the
current startup-simulation graph on three predefined startup scenarios.

## Scenarios

- S1: share-market company
- S2: quiz-based examination replacement
- S3: nursery plants business

The runner calls the existing `simulation.ai_graph.run_simulation()` function.
It does not replace the application's agent logic.

## Run locally

Set your environment variables:

```text
GROQ_API_KEY=...
GROQ_MODEL=...
```

Then run:

```bash
python experiments/run_experiments.py
```

Results are written to `experiment_results/`.

## GitHub Actions

The workflow `.github/workflows/run-experiments.yml` is manually triggered
from the Actions tab.

Create the repository secrets:

- `GROQ_API_KEY`
- `GROQ_MODEL` (optional; the application default is used if omitted)

Do not commit API keys.

## Evidence

Each JSON file contains the startup input, observed agent history, execution
steps, verdict, model name, duration, and any runtime error.

These outputs should be treated as raw experimental evidence. They do not by
themselves establish statistical significance or superiority over a baseline.
