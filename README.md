# incident-memory

An on-call triage agent that writes down what it guessed, what the human corrected, and what actually fixed it — then retrieves that episode when a structurally similar alert fires later.

The key idea: memory stores **discriminators** (the observation that would have separated a wrong guess from the right one), not answers. Retrieved precedents are fed back to the agent as hypotheses to verify, never as conclusions.

## Why

Alert text similarity isn't incident similarity — the same alert fires for several unrelated causes. So instead of embedding the alert, the agent embeds a generated *situation summary* of the evidence, and instead of storing "it was pool exhaustion," it stores the specific check that would have told you so at page time.

## Stack

- Python 3.11+ (package: `imem`)
- MongoDB Atlas 8.0+ (`$rankFusion` for hybrid retrieval)
- Voyage AI embeddings
- Anthropic SDK, hand-rolled agent loop

## Status

Early scaffold — infra and simulator phases in progress. See [`docs/design.md`](docs/design.md) for the full design, build plan, and file-by-file breakdown.

## Local dev

A local Atlas deployment works fine for development:

```
atlas deployments setup --type local
```

Verify it's 8.0+ before relying on `$rankFusion`.
