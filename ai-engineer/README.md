# Technical Challenge — Senior AI Engineer

## Context

You are inheriting **Billforge Support Copilot**, the support assistant of Billforge, a multi-tenant billing SaaS. It answers customer tickets using each customer's own knowledge base (policies, rates, FAQs), and it can look up invoices and issue credits. It is a prototype, and whoever built it is no longer on the team.

Product wants to go live with the first three customers in two weeks. It works in the demo, but **nobody on the team is comfortable putting it in front of real customers**, and nobody can quite say why.

Your task is the one you would get on day 1: assess how ready it is, prioritize the risks, and fix what matters most, **without breaking what works**.

## Setup

From this folder:

The chat model runs locally through Ollama (`llama3.1:8b` by default), and LangGraph
orchestrates tool calls. Run setup once to start the services, download the model, apply
database migrations, and load demo data:

```bash
bin/setup.sh
curl -s localhost:8000/v1/ask -H 'Content-Type: application/json' -d '{"tenant_id":"acme","question":"What is the refund policy for annual plans?"}'
```

On Windows, run this from Git Bash, or enable Docker Desktop integration for your WSL
distribution before running it there.

The model download can take several minutes the first time. The Ollama model and database
are stored in Docker volumes, so they persist between runs. Set `LLM_MODEL` before running
setup to download a different Ollama model. `OLLAMA_BASE_URL` is used when running the API
outside Docker, and `LLM_TIMEOUT_S` controls the model request timeout (120 seconds by default).

## Debugging in VS Code

No `.env` file or manually configured environment variables are needed for the
default local setup. Install the Python extension, select an interpreter with
this project installed (`pip install -e .`), then run the same one-step setup:

```bash
bin/setup.sh
```

Open **Run and Debug**, select **FastAPI: Billforge Support Copilot**, and press
**F5**. Set breakpoints in the app (for example, in `app/routers/ask.py`) and send
a request to `http://localhost:8001/v1/ask`. The debug launcher uses port 8001
so it can run alongside the default API port, and connects to the Compose Ollama
container through `http://127.0.0.1:11435`. This avoids accidentally using a
separate Ollama installation on the host. The Compose Ollama port is bound only
to the local machine, as is the embedding service port used by the host-run
debugger. The debugger also uses a Selector event loop on Windows for Psycopg
compatibility. PostgreSQL, Ollama, the embedding service, and the Compose API
stay in Docker.

**Save the output of `bin/bench.sh` before you change anything**: it is your latency and cost baseline. There are **10 tests** that run in CI and **must stay green**. If a change of yours breaks them, either fix them with good judgment or explain why the test was wrong. The embedding service remains a local simulation; no external API key is required.

`langchain-ollama` connects the application to Ollama and provides its chat/tool-calling
interface. The direct `ollama` dependency exposes provider errors so failed requests keep
the app's explicit upstream-error and retry behavior. `langgraph` classifies each request,
routes knowledge questions through tenant-scoped retrieval, and manages billing tool calls
and model execution with a bounded number of iterations.

## What to deliver

### 1. `FINDINGS.md`

For each finding: what it is (with `file:line`), why it matters, its severity, and whether you fixed it or not. **Ordered by priority, with your criteria written down.**

In the same document, also answer these questions:

1. An enterprise customer of Billforge asks whether their data can show up in the answers another customer receives. What do you tell them today, based on what you saw in the system, and what evidence would you show them?
2. The product team wants the assistant to issue credits automatically whenever it considers it reasonable. What would have to be true before enabling that in production?
3. You make a change that should improve answer quality. How do you know, with numbers, whether it got better or worse? What would you measure before touching anything?

### 2. The fixes

Atomic commits, using conventional commits, from branches. Wrap up with **one Pull Request** using the repo's template: what you changed, why, how you verified it, and what risk it carries. Include **before and after evidence** pasted in the PR (test output, bench output, or whatever commands you use).

### 3. AI usage log

An `AI_LOG.md` file or a `prompts/` folder with your prompts exactly as you wrote them, transcripts, and any rules or context files you used. **Raw, not a polished summary.** We work AI-first: using AI counts in your favor, using it without judgment shows, and so does not using it at all.

## Rules

- You can use any tools you want, **as long as you justify every new dependency**.
- It doesn't need to be perfect. **It does need to not be broken.** If something stopped working because of a change you made, say so.
- Code and comments in English. `FINDINGS.md` in whichever language you prefer.

## How we evaluate

In order of weight: **prioritization judgment** > risks actually fixed and verified > code quality > process (commits, PR, green tests).

There is no live technical review: **everything you want us to know has to be in writing.** If you pass, the next stage is an interview with the team.

## Submission

Send a link to the repo (with access granted) and a link to the PR by email, within **3 days** of receiving this brief.

Questions about the brief: ask the contact listed in the README at the root of the repo. Asking good questions counts too.
