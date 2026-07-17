# Changelog

> Last 20 changes. Full history in git.

- 2026-07-17: LLM in the loop (Phase 1 steps 3-5): llm.py (httpx OpenAI-compatible client, forced AgentOutput tool call, ordered endpoint failover chain, auto-fixer ported from page-agent with 2x parse retry), agent.py (PageAgentCore loop port: max steps, step delay, <sys> observations, reflection history, errors excluded from LLM context), trace.py (JSONL per run, password values scrubbed), hermd run CLI. 51 tests green; live-proven on tests/pages/form.html via CLIProxyAPI + claude-sonnet-5 (4 steps, submitted:geez captured in trace).
- 2026-07-17: Engine core landed (0bd5e80): page-agent DOM extractor port (injectable, in-page selector map), serializer with 8 golden tests pinning the prompt contract, BrowserState render, hermd snapshot CLI, action tools (click/input/select/scroll incl. shadow DOM and container scroll); 23 tests green; live-verified on news.ycombinator.com.
- 2026-07-17: Repo initialized; naming unified on hermd (dist, import, CLI); requirements.txt removed as a pyproject duplicate; .env.example moved in from repos/.
- 2026-07-16: hermes-task-distiller deliverable moved in at integrations/hermes-task-distiller/ (Phase 5 design input, see its INTEGRATION.md).
