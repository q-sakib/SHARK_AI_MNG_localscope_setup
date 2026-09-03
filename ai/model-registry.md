# Local Model Registry

Keep this file intentionally small.

## Recommended workflow

Do not pull models automatically. Select models against actual workloads.

Suggested categories:
- coding/agentic
- reasoning
- embeddings
- vision
- lightweight/private bulk processing

For each model record:
- model name/tag
- purpose
- context length used
- hardware
- benchmark notes
- known tool-calling behavior
- date evaluated

Current Ollama guidance for coding agents recommends large context windows; verify current model-specific requirements before changing settings.
