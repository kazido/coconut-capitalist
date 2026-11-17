# Planner / executor workflow

How work gets done in this repo when a **strong cloud model plans** and **local models (Ollama) execute**. Written for the owner and for
the planner. Local executors read [EXECUTOR.md](EXECUTOR.md) instead (it is short on purpose).

## Roles

| Role | Who | Does | Never does |
|---|---|---|---|
| **Planner** | Claude (best model you can afford), plan mode | Designs features, writes plans and **task briefs**, reviews results, rewrites a brief when an attempt fails | Bulk typing of code, exploring dozens of files, running long test loops |
| **Executor** | Local model via Ollama (Claude Code pointed at it, or any agent tool) | Implements ONE brief at a time, runs `scripts/verify.sh`, commits | Design decisions, balance numbers, multi-system refactors |
| **Gate** | `scripts/verify.sh` | Lint + the tests that match the changed files. "Done" means it printed `VERIFY PASSED` | |
| **Owner** | You | Approves plans, plays the bot, decides taste (art, balance, wording) | |

## The loop

1. **Plan** (planner, plan mode). Output: `docs/plans/NNN-name.md`: goal, decisions, an ordered list of steps. Keep each step small.
2. **Brief** (planner). One file per step in `docs/briefs/NNN-step.md`, from [briefs/TEMPLATE.md](briefs/TEMPLATE.md). A brief names exact files,
   exact functions to reuse, the behaviour, and the tests that prove it. A good brief needs **no exploring**.
3. **Execute** (executor). In a second terminal: `scripts/local-claude.sh qwen3-coder -- -p "$(cat docs/briefs/NNN-step.md)"`
   (or paste the brief into any local agent). It edits, runs `scripts/verify.sh`, commits.
4. **Gate**. `VERIFY PASSED` or it is not done. The executor fixes its own failures, at most **3 attempts**.
5. **Review** (planner, cheap). Look at `git diff --stat`, the verify output and only the key hunks. Do not re-read whole files.
   Accept, or append feedback to the brief's **Attempt log** (what was wrong, what to do instead) and run step 3 again.
6. **Escalate** after 2 failed rounds: the planner splits the step smaller, or does it itself (or a cloud Sonnet agent does it).

## What is safe to give a local model

Good: a new test file; adding a config entry and its validation; one new service function with a clear spec; a screen tweak that copies
an existing screen; renames; docs; mechanical edits across files given an exact pattern; fixing a failing test whose cause is already known.

Keep for the planner (or a cloud agent): anything touching `cococap/ui/nav.py`, `cococap/registry/`, migrations, the economy balance,
cross-cutting refactors, new systems (those need a plan first), and any bug whose cause is unknown.

**Sizing rule:** at most 3 files, about 150 changed lines, one behaviour, tests named in the brief.

## Keeping the planner's usage low

- Plans and briefs are small files; the executor's reading and typing is the expensive part and it happens locally.
- Start each planning session by reading only `CLAUDE.md` and `docs/HANDOFF.md`. `/clear` between unrelated tasks.
- Use plan mode for design, then **stop planning when the briefs are written**. Do not keep the planner in the loop for typing.
- Review by `git diff --stat` and test output, not by re-reading files.
- Use a cheaper model for review (`/model`), and the best one only for design.
- Prefer one long-lived plan file over re-explaining context in chat.

## Setup (once)

**1. Local models (Ollama).**
```bash
ollama pull qwen3-coder        # or another model that supports tools: https://ollama.com/search?c=tools
OLLAMA_CONTEXT_LENGTH=64000 ollama serve    # agents need >= 64k context; the default can be only 4k
ollama ps                      # while a model is loaded: CONTEXT should say 64000 and PROCESSOR 100% GPU
```
Windows PowerShell: `$env:OLLAMA_CONTEXT_LENGTH=64000; ollama serve`. A bigger context uses more memory; if the model spills to CPU
(`ollama ps` shows less than 100% GPU) it will be very slow: use a smaller model, not a smaller context.

**2. The executor terminal** (never export these in your shell profile, they would redirect the planner too):
```bash
scripts/local-claude.sh qwen3-coder                     # interactive
scripts/local-claude.sh qwen3-coder -- -p "$(cat docs/briefs/001-example.md)"   # one brief, then exit
```
Without the script: `ANTHROPIC_AUTH_TOKEN=ollama ANTHROPIC_API_KEY="" ANTHROPIC_BASE_URL=http://localhost:11434 claude --model qwen3-coder`
(or `ollama launch claude`). Inside Claude Code, `/status` shows which endpoint is active.

**3. The planner terminal**: a normal `claude`, logged in with either a Claude plan or an Anthropic Console API key
(see "Paying for the planner" below). Run it in the same repo, in a different terminal from the executor.

**4. Same machine or two machines?** If Ollama runs on another PC, set `ANTHROPIC_BASE_URL=http://<that-pc>:11434` for the executor and
start Ollama there with `OLLAMA_HOST=0.0.0.0` (only on a network you trust).

## Paying for the planner

The free claude.ai plan does **not** include Claude Code. Options, as of the last check (prices change; check the pricing page):

- **Pro** subscription: about $20/month ($17 billed yearly). Simple, usage limits in 5-hour and weekly windows.
- **Pay as you go** with an Anthropic Console API key (`/login`, choose the Console account): you pay per token and nothing when idle.
  Set a **monthly spend limit in the Console** first. Planning-only sessions are cheap; sessions that read many files or spawn many agents are not.
- **No cloud at all**: run everything on Ollama (`scripts/local-claude.sh` for the planner terminal too). Free, but a local model plans much
  worse than a frontier model; use it for small, well-specified work only.

## Troubleshooting

- *The executor ignores the repo rules*: the model is too small or the context is truncated. Check `ollama ps`, shorten the brief, point it at the
  exact files.
- *Tool-call errors or loops*: pick a model from the tools-capable list; lower the task size.
- *`VERIFY FAILED` repeatedly*: read the first failing line to the planner; usually the brief missed a convention (add it to EXECUTOR.md).
- *Planner session suddenly uses the local model*: you exported the `ANTHROPIC_*` variables in that shell. Open a new terminal.
- *Slow*: a 30B-class model on 24 GB of memory with a 64k context is tight; prefer a ~14B model first.
