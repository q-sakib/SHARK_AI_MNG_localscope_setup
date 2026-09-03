# /cpres — Context Compress

Compress this conversation's context to reduce token overhead. Extract only what is needed to continue the task.

## Output format

Return a compressed context block using this structure — dense bullets, max 12 words each:

```
## ACTIVE TASK
- <what we are building/fixing>

## STATUS
- <what is done>
- <what is in progress>

## KEY DECISIONS
- <decision and why, one line each>

## FILES CHANGED
- <path>: <what changed and why>

## OPEN / NEXT
- <blocker or next step>
```

Rules:
- Remove all conversational filler, pleasantries, and explanations already acted on
- Preserve file paths, error messages, and concrete decisions verbatim
- If local Ollama is available, pipe long sections through: `caveman compress`
- Do not summarize code — keep exact function names, paths, and error strings
- Output only the compressed block above, nothing else
