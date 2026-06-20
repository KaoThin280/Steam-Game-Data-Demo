"""
E2B Sandbox service - run Python code in an isolated E2B sandbox.

Used by the data-analysis agent to execute charts, statistics, and other
transformations on the data the model has queried. Failures are returned
to the agent for retry (up to `max_retries` times per workflow).
"""
import asyncio
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class E2BService:
    """Thin wrapper around the e2b_code_interpreter SDK with async + retry support."""

    # ------------------------------------------------------------------
    # Core execution
    # ------------------------------------------------------------------
    @staticmethod
    async def execute(
        code: str,
        files_to_mount: Optional[List[str]] = None,
        deps_to_install: Optional[List[str]] = None,
        timeout_s: int = 180,
    ) -> Dict[str, Any]:
        """Run Python code in an E2B sandbox. Returns a structured result."""
        if not settings.E2B_API_KEY:
            return {
                "success": False,
                "logs": "",
                "results": [],
                "error": "E2B_API_KEY is not configured in .env",
                "sandbox_files": [],
            }

        return await asyncio.to_thread(
            E2BService._execute_sync,
            code,
            files_to_mount or [],
            deps_to_install or [],
            timeout_s,
        )

    @staticmethod
    def _execute_sync(
        code: str,
        files_to_mount: List[str],
        deps_to_install: List[str],
        timeout_s: int,
    ) -> Dict[str, Any]:
        from e2b_code_interpreter import Sandbox  # type: ignore

        os.environ["E2B_API_KEY"] = settings.E2B_API_KEY
        try:
            with Sandbox.create() as sandbox:
                # 1. Mount files
                for fp in files_to_mount:
                    if not os.path.isfile(fp):
                        logger.warning("Mount file not found: %s", fp)
                        continue
                    with open(fp, "rb") as f:
                        sandbox.files.write(os.path.basename(fp), f)
                # 2. Install deps
                if deps_to_install:
                    res = sandbox.commands.run(f"pip install {' '.join(deps_to_install)}")
                    if res.exit_code != 0:
                        return {
                            "success": False,
                            "logs": res.stderr or "",
                            "results": [],
                            "error": f"pip install failed:\n{res.stderr}",
                            "sandbox_files": [],
                        }
                # 3. Ensure temp dir
                sandbox.commands.run("mkdir -p temp_data")
                # 4. Run code
                execution = sandbox.run_code(code, timeout=timeout_s)
                # 5. Download any new files
                sandbox_files: List[str] = []
                temp_dir = Path(settings.TEMP_DATA_DIR)
                temp_dir.mkdir(parents=True, exist_ok=True)
                try:
                    listing = sandbox.files.list("temp_data")
                except Exception:
                    listing = []
                for f in listing:
                    name = getattr(f, "name", None) or str(f)
                    try:
                        content = sandbox.files.read(f"temp_data/{name}")
                    except Exception:
                        continue
                    if not content:
                        continue
                    out_path = temp_dir / name
                    try:
                        if isinstance(content, str):
                            out_path.write_text(content, encoding="utf-8")
                        else:
                            out_path.write_bytes(content)
                        sandbox_files.append(name)
                    except Exception as exc:
                        logger.warning("Could not save %s: %s", name, exc)
                # 6. Build response
                if execution.error:
                    err = (
                        f"Execution error:\n{execution.error.value}\n\n"
                        f"Code:\n```python\n{code}\n```"
                    )
                    return {
                        "success": False,
                        "logs": execution.logs.stdout if execution.logs else "",
                        "results": [r.text for r in execution.results if r.text],
                        "error": err,
                        "sandbox_files": sandbox_files,
                    }
                return {
                    "success": True,
                    "logs": execution.logs.stdout if execution.logs else "",
                    "results": [r.text for r in execution.results if r.text],
                    "error": None,
                    "sandbox_files": sandbox_files,
                }
        except Exception as exc:
            logger.exception("E2B execution failed")
            return {
                "success": False,
                "logs": "",
                "results": [],
                "error": f"Sandbox error: {exc}",
                "sandbox_files": [],
            }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def find_new_temp_files(before: set, allowed_ext: tuple = (".csv", ".html", ".png")) -> List[str]:
        """Return new artifact filenames in temp_data/ that were not in `before`."""
        temp_dir = Path(settings.TEMP_DATA_DIR)
        if not temp_dir.exists():
            return []
        now = set()
        for f in temp_dir.iterdir():
            if f.is_file() and f.suffix.lower() in allowed_ext and f.stat().st_size > 0:
                now.add(f.name)
        return sorted(now - before)

    @staticmethod
    def clean_temp(exclude: Optional[set] = None) -> None:
        """Delete all files in temp_data/ except those in `exclude`."""
        temp_dir = Path(settings.TEMP_DATA_DIR)
        if not temp_dir.exists():
            return
        for f in temp_dir.iterdir():
            if f.is_file() and (not exclude or f.name not in exclude):
                try:
                    f.unlink()
                except Exception as exc:
                    logger.warning("Could not clean %s: %s", f.name, exc)

    # ------------------------------------------------------------------
    # Execute code from a JSON tool_call
    # ------------------------------------------------------------------
    @staticmethod
    async def execute_from_tool_call(
        tool_call: Dict[str, Any],
        files_to_mount: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Run the `code` field of a tool_call dict and return the result."""
        code = (tool_call.get("code") or "").strip()
        if not code:
            return {
                "success": False,
                "logs": "",
                "results": [],
                "error": "Tool call has empty code",
                "sandbox_files": [],
            }
        result = await E2BService.execute(code=code, files_to_mount=files_to_mount)
        result["code"] = code
        return result
