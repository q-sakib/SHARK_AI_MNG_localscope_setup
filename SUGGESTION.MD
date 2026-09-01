Yes — if you're thinking beyond "RAG + Obsidian" and want a serious personal AI memory/context system, there is a whole additional layer worth considering.

I'd think about it as AI knowledge infrastructure, with separate tools for memory, compression, retrieval, temporal history, wiki generation, context engineering, and observability.

The stack I'd investigate
1. Memory layer

For agent memories, look at:

Letta — one of the most interesting approaches if you want agents with explicit, persistent memory and controllable context.
Mem0 — focused specifically on long-term AI memory and extracting/retrieving memories from interactions.
Zep — designed around persistent memory and contextual retrieval for agents.
LangMem — useful if you're building around LangGraph/LangChain and want explicit memory management.

I wouldn't necessarily install all four.

I'd study their architectures and steal the ideas.

Your own system could eventually look like:

Conversation
     │
     ▼
Memory extraction
     │
     ├── fact
     ├── preference
     ├── decision
     ├── lesson
     ├── relationship
     └── temporary context
            │
            ▼
       memory policy
            │
     ┌──────┼────────┐
     ▼      ▼        ▼
 personal project  ephemeral

2. Context compression

This is actually more important than RAG for your use case.

You want a pipeline like:

10,000 messages
      ↓
extract important information
      ↓
2,000 useful facts
      ↓
500 durable memories
      ↓
50 highly relevant memories
      ↓
10 context items
      ↓
LLM


Look at:

LLMLingua — prompt/context compression.
LongLLMLingua — compression designed for long-context question answering.
LLMLingua-2 — newer token-level compression approaches.
Microsoft Research's LLMLingua family — worth studying even if you don't directly adopt it.

But I'd also build your own semantic compression hierarchy:

Raw
 ↓
Session summary
 ↓
Task summary
 ↓
Project knowledge
 ↓
Durable memory
 ↓
Canonical knowledge


This prevents your memory database becoming a graveyard of AI conversations.

3. Wiki / knowledge base

For your "wiki version" idea, I'd strongly consider:

Obsidian

Human-facing canonical wiki.

Docusaurus

For a proper generated developer/project wiki.

MkDocs

Excellent if you want Markdown → documentation/wiki.

Quartz

Interesting if you want an Obsidian-like Markdown knowledge base published as a website.

The architecture could be:

              Knowledge
                  │
        ┌─────────┴─────────┐
        │                   │
     Machine              Human
        │                   │
     SQLite              Obsidian
     Qdrant                 │
        │                   │
        └─────────┬─────────┘
                  │
             Wiki builder
                  │
             ┌────┴─────┐
             ▼          ▼
          MkDocs     Quartz

4. Versioned knowledge

This is something I think you'll particularly like.

Don't only version code.

Version knowledge.

For example:

knowledge/
├── architecture/
│   ├── authentication.md
│   └── payments.md
│
├── decisions/
│   ├── ADR-001.md
│   └── ADR-002.md
│
└── lessons/


Then Git tracks:

v1:
Authentication uses sessions.

v2:
Authentication migrated to JWT.

v3:
JWT abandoned due to security issue.


Your AI can answer:

What did we believe about authentication six months ago?

That's very different from normal RAG.

5. Temporal memory

I'd explicitly model time.

Every memory should have:

created_at:
valid_from:
valid_until:
supersedes:
superseded_by:
confidence:


Then you can distinguish:

"Authentication uses Redis."


from:

"Authentication used Redis between March and June."


This matters enormously for software projects because architecture changes.

Eventually you want queries like:

ai memory search \
  "authentication architecture" \
  --at 2026-04-01


That gives you historical context, not just semantic similarity.

6. Knowledge graph

Once your system gets sophisticated, add relationships.

You might have:

PR-381
   │
   ├── modifies → Authentication
   │                  │
   │                  └── depends_on → Redis
   │
   ├── caused → Decision-042
   │
   └── discussed_by → Review-381


You don't necessarily need Neo4j initially.

Start with SQLite:

entities
relationships
events


Then migrate to a graph database if you actually need graph traversal.

The important thing is the data model, not the database.

7. Hybrid search

Don't build a pure vector RAG.

Use:

                 Query
                   │
       ┌───────────┼───────────┐
       ▼           ▼           ▼
   Full text    Semantic     Metadata
    search       search       filtering
       │           │           │
       └───────────┼───────────┘
                   ▼
                Reranker
                   │
                   ▼
             Context selection


For your system I'd use:

SQLite FTS5 → exact/full-text
Qdrant → semantic retrieval
metadata → scope/time/project
reranking → final selection

This is considerably better than:

"embed everything and retrieve top 10."

8. Reranking

This is another advanced layer people often skip.

Suppose semantic search returns:

20 documents


You don't want to feed all 20 to Claude.

Use a reranker to decide:

20 candidates
      ↓
relevance scoring
      ↓
5 candidates
      ↓
context compression
      ↓
Claude


This becomes especially valuable once your personal knowledge base reaches thousands or tens of thousands of documents.

9. Agent context management

I'd also look at the ideas behind:

Letta/MemGPT
LangGraph
DSPy
LlamaIndex
Haystack

But I'd be careful about adopting a large framework.

You're not trying to build:

another generic AI agent framework.

You're trying to build:

your personal context operating system.

That's a different goal.

10. Session memory

I would create a dedicated session recorder.

Every Claude session becomes:

session/
└── 2026-09-01-auth-timeout/
    ├── transcript.md
    ├── summary.md
    ├── decisions.md
    ├── changes.md
    ├── questions.md
    └── memories.yaml


Then the session gets compressed.

Raw session
     ↓
summary
     ↓
important events
     ↓
candidate memories
     ↓
durable knowledge


You don't need to preserve every token forever.

11. "Memory garbage collection"

This is a very advanced but very important feature.

Your system should periodically ask:

Is this memory still useful?


For example:

Memory:
"I am currently debugging payment timeout."

Age:
183 days

Last retrieved:
never

Status:
stale


Then:

candidate
   ↓
active
   ↓
stale
   ↓
archived
   ↓
deleted


You can also detect contradictions:

Memory A:
Database = MongoDB

Memory B:
Database = PostgreSQL

         ↓

CONFLICT
         ↓

ask user / inspect Git


That's much more valuable than blindly accumulating memories.

12. Memory scoring

Give memories a score.

Something like:

importance
confidence
recency
frequency
project relevance
user relevance


Then:

memory_score =
    importance ×
    confidence ×
    relevance ×
    recency


Your context engine can select high-value memories.

13. "Canonicalization"

This is another concept I'd add.

AI conversations are messy:

Claude says:
"Maybe Redis is responsible for this..."

Later:
"Actually, the problem was PostgreSQL."



Don't store both as facts.

Instead:

Raw observations
        ↓
candidate knowledge
        ↓
verification
        ↓
canonical knowledge


Your wiki should contain canonical knowledge, not every thing an LLM ever hallucinated.

14. Provenance

Every memory should know where it came from.

Example:

id: mem_9281
content: Authentication timeout was caused by Redis connection pooling.
source:
  type: pr
  id: 381
  commit: a82f31c
confidence: high
verified: true


Then Claude can say:

This comes from PR #381 and commit a82f31c.

That's dramatically better than:

"I remember that..."

15. Contradiction detection

I'd eventually build:

new information
       ↓
compare against existing knowledge
       ↓
┌──────┼─────────┐
│      │         │
new  duplicate  conflict
│      │         │
↓      ↓         ↓
save   merge    resolve


For example:

Existing:
"Payments use Kafka."

New:
"Payments now use RabbitMQ."



Your system should understand:

RabbitMQ supersedes Kafka


rather than storing two unrelated vectors.

16. Personal "knowledge compiler"

This is where I think your idea gets really interesting.

Treat your knowledge like source code.

Raw notes
   ↓
Extract
   ↓
Normalize
   ↓
Resolve contradictions
   ↓
Compress
   ↓
Canonicalize
   ↓
Index
   ↓
Publish wiki


So:

~/ai/raw/
        ↓
~/ai/knowledge/
        ↓
~/ai/index/
        ↓
Obsidian / Wiki / Agent


You essentially have a knowledge compiler.

17. My ideal directory

I'd eventually structure your personal system like:

~/ai/
│
├── config/
│
├── projects/
│   └── project-a/
│       ├── context/
│       ├── sessions/
│       ├── reviews/
│       ├── decisions/
│       └── history/
│
├── memory/
│   ├── personal/
│   ├── preferences/
│   ├── skills/
│   └── experiences/
│
├── knowledge/
│   ├── canonical/
│   ├── temporal/
│   ├── candidates/
│   └── archived/
│
├── raw/
│   ├── conversations/
│   ├── exports/
│   └── imports/
│
├── indexes/
│   ├── sqlite/
│   └── qdrant/
│
├── wiki/
│
├── scripts/
│
└── ai.db


And your Obsidian vault becomes the human interface to selected parts of this system.

18. The advanced pipeline

Ultimately, I'd aim for this:

                     YOU
                      │
                      ▼
                Claude Code
                      │
                      ▼
              Context Broker
                      │
          ┌───────────┼────────────┐
          │           │            │
          ▼           ▼            ▼
       Project     Personal      History
       Context     Memory        Events
          │           │            │
          └───────────┼────────────┘
                      ▼
                Hybrid Search
                      │
             ┌────────┴─────────┐
             ▼                  ▼
          SQLite              Qdrant
             │                  │
             └────────┬─────────┘
                      ▼
                   Reranker
                      │
                      ▼
                Compression
                      │
                      ▼
                 Final Context
                      │
                      ▼
                  Claude
                      │
                      ▼
               New Knowledge
                      │
             ┌────────┼─────────┐
             ▼        ▼         ▼
          Project   Personal   Temporary
             │        │         │
             ▼        ▼         ▼
            Git    Obsidian   Session

If I were building it for myself

I'd prioritize the tools like this:

Tier 1 — definitely
Claude Code
Git
Obsidian
SQLite
your own CLI
MCP
Claude Code hooks
Tier 2 — very useful
Qdrant
hybrid search
reranking
Git worktrees
session recorder
automatic summaries
provenance tracking
Tier 3 — advanced
LLMLingua-style compression
temporal memory
contradiction detection
memory scoring
automatic memory garbage collection
knowledge graph
canonicalization pipeline
generated wiki
Tier 4 — research territory
Letta/MemGPT-style memory architecture
Mem0/Zep-style memory extraction
DSPy-based context optimization
automatic context-policy learning
multi-agent personal knowledge management

One warning: don't let "AI memory" become a giant pile of embeddings. The really advanced system isn't the one with the biggest vector database. It's the one that knows what should be remembered, at what scope, for how long, why it is trusted, when it became obsolete, where it came from, and how much of it should enter the current context.

That's the direction I'd take for the system you're imagining.