Yes. What you’re describing is essentially a two-scope agent architecture:

Project scope → shared, version-controlled, team-owned, reproducible.
Personal scope → local/private, evolving, personalized, containing your working memory, preferences, history, RAG, experiments, review context, etc.

The important part is to not let Claude Code treat your personal memory as project configuration. You want a deliberate boundary between the two.

The architecture I’d recommend
                         ┌──────────────────────────┐
                         │       Claude Agent        │
                         │     / Claude Code         │
                         └────────────┬─────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    │                                   │
             PROJECT SCOPE                         PERSONAL SCOPE
             Git-controlled                       Local / private
                    │                                   │
        ┌───────────┼───────────┐              ┌────────┼─────────┐
        │           │           │              │        │         │
     CLAUDE.md    Rules       Skills         Memory    RAG     History
        │           │           │              │        │         │
     Coding      Testing    Workflows       Prefs   Notes   Decisions
     standards   security   architecture    context  docs    Reviews
     CI/CD       style      conventions     lessons  PRs     Experiments
        │                                   │
        └────────────── Git ────────────────┘
                                            │
                                      Local filesystem
                                            │
                              ┌─────────────┴──────────────┐
                              │                            │
                           Obsidian                    SQLite/DB
                              │                            │
                         human notes                  machine memory
                              │                            │
                              └─────────────┬──────────────┘
                                            │
                                      Local RAG/index
                                            │
                                  embeddings / search


The key design principle is:

Git contains what the project needs to know. Your local system contains what you need to remember about working on the project.

That distinction is extremely powerful.

1. Project scope

Your existing project configuration should remain the source of truth for the team.

Something like:

project/
├── CLAUDE.md
├── .claude/
│   ├── rules/
│   ├── skills/
│   ├── agents/
│   └── commands/
│
├── src/
├── tests/
├── docs/
├── package.json
└── ...


This layer should answer:

"If another developer clones this repository, what does the agent need to know to work correctly?"

Examples:

Architecture
Coding conventions
Testing requirements
Build commands
Deployment rules
Security constraints
API conventions
Database conventions
PR requirements
Commit conventions
Project terminology
Important directories
Generated-code rules


Don't put things like:

I personally prefer...
My current experiment...
My TODO...
My conversation with Claude...
My temporary hypothesis...
My PR review thoughts...
What I learned yesterday...


into this layer.

Those belong elsewhere.

2. Your personal scope

I'd create a completely separate directory outside the repository.

For example:

~/ai/


Then:

~/ai/
├── memory/
├── projects/
├── rag/
├── history/
├── reviews/
├── decisions/
├── experiments/
├── prompts/
├── exports/
├── indexes/
└── config/


And project-specific memory:

~/ai/projects/
└── my-project/
    ├── memory/
    ├── decisions/
    ├── reviews/
    ├── prs/
    ├── experiments/
    ├── context/
    ├── notes/
    └── history/


This directory should never be inside the Git repository.

3. Don't make "memory" one giant file

This is one of the biggest improvements I'd make.

Don't build:

memory.md


with 50,000 lines.

Instead, create different classes of memory.

For example:

memory/
├── identity/
│   ├── preferences.md
│   ├── coding-style.md
│   └── workflow.md
│
├── project/
│   └── my-project/
│       ├── architecture-understanding.md
│       ├── known-problems.md
│       ├── decisions.md
│       └── lessons.md
│
├── work/
│   ├── active-context.md
│   └── current-objectives.md
│
└── history/
    ├── 2026-09/
    ├── 2026-08/
    └── ...


This gives your agent a much better mental model.

4. Separate "memory" from "knowledge"

This is another important distinction.

I'd use three concepts:

Memory

Things about you and your interactions.

User prefers TypeScript.
User likes concise PR descriptions.
User normally runs tests before committing.
User is experimenting with X.

Knowledge

Facts about the project or external systems.

The authentication service uses OAuth.
The billing service communicates through Kafka.
The legacy API is deprecated.

History

Things that happened.

PR #381 changed authentication.
On Aug 31 we discovered race condition X.
Decision was made to postpone migration.


They shouldn't all be treated equally by RAG.

5. Add a local "context broker"

This is where your idea becomes much more advanced.

Instead of asking Claude to directly rummage through everything, build a tiny local service/CLI.

For example:

aictx search "authentication architecture"

aictx context

aictx project my-project

aictx remember "We decided to keep Redis for session storage."

aictx review PR-381

aictx history

aictx export


The CLI becomes the interface between Claude and your personal knowledge system.

6. Have an explicit context hierarchy

This is probably the most important architectural rule.

I'd define:

Priority 1
PROJECT RULES
        ↓
Priority 2
PROJECT CURRENT STATE
        ↓
Priority 3
PERSONAL WORKFLOW
        ↓
Priority 4
PERSONAL MEMORY
        ↓
Priority 5
RAG / historical information
        ↓
Priority 6
Speculation


So if your personal memory says:

"I prefer using library X."

but project rules say:

"Use library Y."

The agent follows Y.

Your personal scope should never override project authority.

Instead:

Project says:
Use PostgreSQL.

Personal memory says:
I personally prefer SQLite.

Agent:
Use PostgreSQL.


That's the behavior you want.

7. Give every piece of memory a scope

This is where I'd go beyond normal RAG.

Every memory item should have metadata.

Something like:

id: mem_01928
scope: personal
project: my-project
type: decision
created: 2026-09-01
source: user
confidence: high
visibility: private
expires: null


Or:

scope: project
visibility: shared


Then your retrieval system can enforce:

personal → never write to Git
project → eligible for Git
temporary → expire automatically
historical → retrieve only when relevant

8. Use an "ephemeral context" layer

This is something I'd strongly recommend.

Not everything deserves permanent memory.

For example, today you are debugging:

authentication race condition


You might accumulate:

temporary hypothesis
stack traces
PR comments
Claude discussion
failed approaches
temporary patches


Don't permanently store all of that.

Create:

~/ai/projects/my-project/context/session-2026-09-01/


When the problem is solved:

temporary context
       ↓
   summarize
       ↓
 ┌─────┴─────┐
 ↓           ↓
discard    durable memory


For example:

"Race condition caused by transaction boundary."

gets promoted into:

```text
decisions/authentication.md


while:

"Maybe line 381 is causing it..."


gets deleted.

That prevents your RAG from becoming garbage.

9. PR review deserves its own system

You specifically mentioned PR review context.

I'd make:

~/ai/projects/my-project/reviews/


with:

reviews/
├── PR-381/
│   ├── context.md
│   ├── findings.md
│   ├── discussion.md
│   ├── unresolved.md
│   └── final.md
│
├── PR-392/
└── ...


The agent can then understand:

What was reviewed
What was discovered
What comments were made
Which comments were resolved
What architectural concerns remain


But the actual code changes remain in Git.

That's a very clean division.

10. Git should remain the canonical code history

Don't duplicate Git history into your memory system unnecessarily.

Instead, your personal layer stores interpretation.

Git:

commit
diff
branch
merge
PR
file history


Personal memory:

Why I made this change
What I learned
What I was trying to accomplish
What confused me
What future work remains
What Claude suggested
What I rejected


That distinction is incredibly useful.

11. Obsidian is perfect for the human layer

Your idea of using Obsidian makes sense.

I'd use Obsidian primarily for:

human-readable long-term knowledge

rather than making it the database for everything.

Something like:

Obsidian/
├── Projects/
│   └── MyProject/
│       ├── Architecture/
│       ├── Decisions/
│       ├── PR Reviews/
│       ├── Learnings/
│       └── Ideas/
│
├── Engineering/
│   ├── Patterns/
│   ├── Databases/
│   ├── AI/
│   └── DevOps/
│
└── Personal/
    ├── Preferences/
    ├── Workflows/
    └── Experiments/


Then the machine layer can index Obsidian.

12. I'd use SQLite for machine memory

You don't necessarily need some giant vector database.

Start with:

SQLite


and potentially add vector search later.

For example:

memories
--------
id
project
scope
type
content
source
created_at
updated_at
confidence
importance
expires_at


Then:

events
--------
id
project
event_type
content
timestamp
git_commit
pr_number


And:

documents
--------
id
path
project
content_hash
embedding
updated_at


This gives you an extremely manageable local system.

13. RAG should be a layer, not the source of truth

This is a subtle but important distinction.

Don't think:

RAG = memory


Think:

Memory / Documents
       ↓
Index
       ↓
Retrieval
       ↓
Context selection
       ↓
Claude


RAG is simply a retrieval mechanism.

Your actual source material can be:

Git
Obsidian
PRs
local notes
terminal history
decision records
documents
personal memory

14. Build a context assembler

This is the piece that can make the whole system feel "smart."

When Claude starts a task:

User:
Fix the authentication timeout bug.


Your context system determines:

PROJECT
├── CLAUDE.md
├── relevant project rules
└── authentication architecture

PERSONAL
├── current authentication investigation
├── previous findings
└── relevant PR reviews

RAG
├── similar historical issue
└── relevant design decision

GIT
├── current branch
├── recent commits
└── relevant diff


Then it generates something like:

TASK CONTEXT

Project rules:
...

Relevant architecture:
...

Current investigation:
...

Previous findings:
...

Relevant historical decisions:
...

Current Git state:
...


And only that context goes to Claude.

This is much better than dumping your entire memory database into the prompt.

15. Add a memory promotion pipeline

This is the part I'd make semi-automatic.

Whenever Claude finishes work, classify information:

                Claude interaction
                       │
                       ↓
                 Extract facts
                       │
          ┌────────────┼────────────┐
          ↓            ↓            ↓
       Project       Personal     Temporary
          │            │            │
          ↓            ↓            ↓
        Git         Memory       Session
                       │
                       ↓
                    Review
                       │
                       ↓
                  Obsidian/RAG


For example:

"We discovered that the API retries POST requests."

The system asks:

Is this a project fact?


If yes:

project knowledge


Potentially:

docs/


or a project ADR.

Whereas:

"I prefer seeing the API diff before the full test output."

becomes:

personal preference


and stays local.

16. Use ADRs for durable project decisions

For project-level architectural decisions, don't rely on AI memory.

Use actual Architecture Decision Records:

docs/adr/
├── 001-use-postgresql.md
├── 002-event-driven-billing.md
├── 003-authentication-strategy.md
└── ...


Then:

Project knowledge
        ↓
ADR
        ↓
Git
        ↓
Claude


This makes the project reproducible even without your personal AI system.

17. Keep your personal system portable

I'd make the personal layer independent of Claude.

For example:

~/ai/


should work with:

Claude Code
Codex
Gemini CLI
local models
other agents


The architecture should be:

              ┌───────────────┐
              │ Personal AI   │
              │ Context Layer │
              └───────┬───────┘
                      │
       ┌──────────────┼───────────────┐
       ↓              ↓               ↓
   Claude Code      Codex          Local LLM


That way you aren't building a "Claude memory system."

You're building your own AI context infrastructure.

That's a much better long-term investment.

18. Terminal should be the control plane

Since you mentioned terminal, I'd lean heavily into it.

Something like:

ai project list
ai project init my-project

ai memory add
ai memory search "database migration"

ai context build
ai context build --project my-project

ai review PR 381
ai review history

ai decision add

ai rag index
ai rag search "authentication"

ai export obsidian
ai export project

ai doctor


And:

ai status


could show:

AI Context System

Project: my-project

Project context:
  ✓ CLAUDE.md
  ✓ 14 project rules
  ✓ 6 ADRs

Personal context:
  ✓ 128 memories
  ✓ 42 decisions
  ✓ 18 PR reviews

RAG:
  ✓ 8,421 documents indexed
  ✓ 2,183 Obsidian notes
  ✓ Git indexed

Current session:
  ✓ Authentication investigation

Privacy:
  ✓ Personal data outside repository

19. Add hard security boundaries

This is extremely important.

Your personal directory should have:

chmod 700 ~/ai


And never allow your agent to blindly write personal information into the project.

I'd establish explicit rules:

PROJECT WRITE
├── source code
├── tests
├── project docs
├── ADRs
└── project configuration

PERSONAL WRITE
├── memory
├── history
├── notes
├── PR analysis
├── preferences
└── experiments


And ideally the context broker itself enforces this rather than relying purely on Claude instructions.

20. Your final architecture could look like this

I'd personally aim for:

                 ┌─────────────────────┐
                 │     AI Agent        │
                 │ Claude / Codex/etc. │
                 └──────────┬──────────┘
                            │
                     Context Broker
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
          ▼                 ▼                 ▼
    PROJECT SCOPE     PERSONAL SCOPE      EXTERNAL
          │                 │                 │
       Git repo         ~/ai/             APIs
          │                 │
    ┌─────┼─────┐     ┌────┼────────┐
    │     │     │     │    │        │
 CLAUDE Rules ADR   Memory RAG    History
    │     │     │     │    │        │
    └─────┴─────┘     │    │        │
                      │    │        │
                   SQLite Obsidian  Git metadata
                      │    │
                      └────┴───────┐
                                   │
                              Context Engine
                                   │
                                   ▼
                              Agent Prompt

The really important conceptual split

I'd define the system around these four questions:

Question	Owner
How must the project work?	Git / project
What code/documents exist?	Git / project
What do I personally know/remember?	Local AI memory
What happened while I worked on it?	Local history

And one additional rule:

If another developer clones the repository, the project must remain fully understandable and operational without your personal AI memory.

Your personal layer should make you dramatically more productive, but it shouldn't become an undocumented dependency of the project.

What I'd build first

Don't start by building a huge RAG platform.

Build this in stages:

Phase 1 — filesystem architecture
~/ai/
├── projects/
├── memory/
├── sessions/
├── reviews/
├── decisions/
└── exports/

Phase 2 — CLI

Build:

ai context
ai memory
ai search
ai review
ai export

Phase 3 — SQLite

Add structured metadata and history.

Phase 4 — Obsidian integration

Two-way-ish relationship:

AI memory ←→ Obsidian


but keep Obsidian human-oriented.

Phase 5 — RAG

Index:

Git
Obsidian
PR history
personal notes
project docs


with metadata-aware retrieval.

Phase 6 — context broker

Automatically assemble:

project rules
+
current Git state
+
task-specific project context
+
personal relevant memory
+
historical context

Phase 7 — automatic memory promotion

Have the agent suggest:

PROJECT MEMORY
PERSONAL MEMORY
TEMPORARY
IGNORE


and you approve important promotions.

The end result is less like "I configured Claude Code really well" and more like building a personal AI operating environment around your development workflow.

And that's the direction I'd take if you expect this to grow over years: Git remains the project's brain; your local AI system becomes your personal brain; the context broker decides what the agent is allowed and actually needs to see.