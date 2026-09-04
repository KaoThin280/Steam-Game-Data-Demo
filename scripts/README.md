# Local run and test scripts

Run these commands from the repository root on Windows PowerShell.

## Start the complete local stack

```powershell
.\scripts\start_local_stack.ps1
```

This starts, in order:

- MCP-compatible tool server at `127.0.0.1:8001`
- product API/agent runtime at `127.0.0.1:8000`
- Next.js frontend at `localhost:3000`

The script supplies the same temporary `MCP_SHARED_SECRET` to both backend processes. Stop it with `Ctrl+C`. Production must use a persistent random secret from a protected environment file.

## Unit tests

```powershell
.\scripts\test_backend_unit.ps1
```

Unit tests exercise individual runtime, transport, security and chart-cache behaviors with controlled dependencies. They are fast and do not prove that Supabase, OpenRouter or E2B credentials work.

## End-to-end agent smoke test

```powershell
.\scripts\test_agent_local.ps1
```

The script can start MCP and API, log in with `LOCAL_TEST_EMAIL` and `LOCAL_TEST_PASSWORD` from the gitignored `back_end/.env`, create a durable session, submit a real tool-calling run, inspect persisted events and test cancellation. Credentials passed interactively are preferred on shared machines.

For the assessment conversation demo:

```powershell
.\scripts\test_agent_local.ps1 -ConversationSuite
```

This creates separate Vietnamese and English sessions and asks multiple turns in each: agent identity, total game count and monthly game-release visualization. Use the browser UI at `http://127.0.0.1:8000/agent-demo` for a manual backend-only demo, or the Next.js chat page when the full stack is running.

`test_e2e.py` targets the retired legacy `/api/v1/ai` and file workflow. It is retained only as historical reference and is not part of the current test path while `ENABLE_LEGACY_AI=False`.
