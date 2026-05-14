"""Scripts API - Execute backend scripts from Kaihle Admin."""

from __future__ import annotations

import os
import subprocess
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.deps import CurrentUser, require_role
from app.models.user import UserRole

logger = structlog.get_logger()

router = APIRouter(prefix="/scripts", tags=["scripts"])

# Path to scripts directory
# From app/api/v1/routes/scripts.py: go up to backend/ level
# app/api/v1/routes/scripts.py -> routes (1) -> v1 (2) -> api (3) -> app (4) -> backend/ (5)
SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))), "scripts"
)


class ScriptParameter(BaseModel):
    name: str
    type: str  # "string", "boolean", "number"
    required: bool = False
    default: Any = None  # type: ignore[assignment]
    description: str | None = None


class ScriptDefinition(BaseModel):
    name: str
    description: str
    parameters: list[ScriptParameter]
    requires_api_key: bool = False
    category: str = "general"


# Script definitions matching the scripts in backend/scripts/
SCRIPTS: dict[str, ScriptDefinition] = {
    "generate_subtopic_mapping": ScriptDefinition(
        name="generate_subtopic_mapping",
        description="Uses an LLM via OpenRouter to semantically map question bank subtopic names to canonical codes in cambridge_v1.json.",
        parameters=[
            ScriptParameter(name="questions", type="string", required=True, description="Path to questions JSON file"),
            ScriptParameter(
                name="curriculum",
                type="string",
                default="backend/data/curriculum/cambridge_v1.json",
                description="Path to cambridge_v1.json",
            ),
            ScriptParameter(
                name="output",
                type="string",
                default="backend/data/subtopic_mapping.json",
                description="Output path for mapping file",
            ),
            ScriptParameter(name="api_key", type="string", description="API key for OpenRouter or vLLM"),
            ScriptParameter(name="base_url", type="string", description="Base URL of a private vLLM server"),
            ScriptParameter(
                name="model", type="string", default="google/gemma-4-26b-a4b-it", description="Model identifier"
            ),
            ScriptParameter(
                name="resume", type="boolean", default=False, description="Resume from existing output file"
            ),
            ScriptParameter(name="dry_run", type="boolean", default=False, description="Print output without saving"),
            ScriptParameter(
                name="rate_limit_delay", type="number", default=0.3, description="Seconds to wait between API calls"
            ),
        ],
        requires_api_key=True,
        category="curriculum",
    ),
    "import_questions": ScriptDefinition(
        name="import_questions",
        description="Import questions from JSON or CSV into the question_bank table.",
        parameters=[
            ScriptParameter(
                name="file", type="string", required=True, description="Path to JSON or CSV file with questions"
            ),
            ScriptParameter(name="format", type="string", description="Force file format (json or csv)"),
            ScriptParameter(
                name="strategy",
                type="string",
                default="auto",
                description="Resolution strategy: auto, reresolve, or task",
            ),
            ScriptParameter(name="mapping_file", type="string", description="Path to subtopic_mapping.json"),
            ScriptParameter(
                name="dry_run",
                type="boolean",
                default=False,
                description="Validate and resolve all rows without writing to DB",
            ),
        ],
        requires_api_key=False,
        category="curriculum",
    ),
    "quiz_quality_review": ScriptDefinition(
        name="quiz_quality_review",
        description="Review harness for human quiz review before deployment.",
        parameters=[
            ScriptParameter(name="list", type="boolean", default=False, description="List all pending quizzes"),
            ScriptParameter(name="quiz_id", type="string", description="Quiz ID to review"),
            ScriptParameter(name="approve", type="boolean", default=False, description="Approve the specified quiz"),
            ScriptParameter(name="reject", type="boolean", default=False, description="Reject the specified quiz"),
            ScriptParameter(name="reason", type="string", description="Rejection reason (required with --reject)"),
        ],
        requires_api_key=False,
        category="review",
    ),
    "seed_curriculum_graph": ScriptDefinition(
        name="seed_curriculum_graph",
        description="Seed the full Cambridge curriculum hierarchy from cambridge_v1.json into the database.",
        parameters=[
            ScriptParameter(
                name="data_file",
                type="string",
                default="backend/data/curriculum/cambridge_v1.json",
                description="Path to the curriculum JSON file",
            ),
            ScriptParameter(
                name="dry_run",
                type="boolean",
                default=False,
                description="Validate JSON and simulate inserts without writing to the database",
            ),
        ],
        requires_api_key=False,
        category="database",
    ),
    "seed_subtopic_content": ScriptDefinition(
        name="seed_subtopic_content",
        description="Populate subtopic_content table from the curriculum graph with videos, explanations, and quiz questions.",
        parameters=[
            ScriptParameter(
                name="provider",
                type="string",
                default="openai",
                description="LLM provider: openai, anthropic, google, etc.",
            ),
            ScriptParameter(
                name="model",
                type="string",
                default="gpt-4o-mini",
                description="Model identifier (e.g., gpt-4o-mini, claude-3-5-sonnet-20241022)",
            ),
            ScriptParameter(name="api_key", type="string", description="API key for the LLM provider"),
            ScriptParameter(
                name="limit", type="number", description="Limit number of subtopics to process (for testing)"
            ),
            ScriptParameter(name="skip_videos", type="boolean", default=False, description="Skip video generation"),
            ScriptParameter(
                name="skip_explanations", type="boolean", default=False, description="Skip explanation generation"
            ),
            ScriptParameter(name="skip_quizzes", type="boolean", default=False, description="Skip quiz generation"),
            ScriptParameter(
                name="dry_run", type="boolean", default=False, description="Dry run without making DB changes"
            ),
        ],
        requires_api_key=True,
        category="database",
    ),
}


class ScriptExecuteRequest(BaseModel):
    parameters: dict[str, Any] = {}
    env_vars: dict[str, str] = {}


class ScriptExecuteResponse(BaseModel):
    script_name: str
    status: str  # "started", "completed", "failed"
    output: str | None = None
    error: str | None = None
    return_code: int | None = None


class ScriptListResponse(BaseModel):
    scripts: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------


async def run_script_process(script_name: str, args: list[str], env: dict[str, str]) -> tuple[int, str, str]:
    """Run a script and return (return_code, stdout, stderr)."""
    script_path = os.path.join(SCRIPTS_DIR, f"{script_name}.py")

    if not os.path.exists(script_path):
        raise FileNotFoundError(f"Script not found: {script_path}")

    # Build environment
    full_env = os.environ.copy()
    full_env.update(env)

    # Set working directory to backend
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

    try:
        result = subprocess.run(
            ["python", script_path] + args,
            cwd=backend_dir,
            env=full_env,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Script execution timed out after 5 minutes"
    except Exception as e:
        return -1, "", str(e)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=ScriptListResponse)
async def list_scripts(
    _: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
) -> ScriptListResponse:
    """Return list of available scripts with their parameters."""
    scripts_list = []
    for name, script in SCRIPTS.items():
        scripts_list.append(
            {
                "name": script.name,
                "description": script.description,
                "parameters": [p.model_dump() for p in script.parameters],
                "requires_api_key": script.requires_api_key,
                "category": script.category,
            }
        )
    return ScriptListResponse(scripts=scripts_list)


@router.post("/{script_name}/execute", response_model=ScriptExecuteResponse)
async def execute_script(
    script_name: str,
    request: ScriptExecuteRequest,
    _: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
) -> ScriptExecuteResponse:
    """Execute a script with the given parameters."""

    if script_name not in SCRIPTS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Script '{script_name}' not found",
        )

    script_def = SCRIPTS[script_name]

    # Build command line arguments
    args = []
    env_vars = request.env_vars.copy()

    # Handle special parameters for seed_subtopic_content - extract provider/model/api_key as env vars
    if script_name == "seed_subtopic_content":
        provider = request.parameters.get("provider")
        model = request.parameters.get("model")
        api_key = request.parameters.get("api_key")

        if api_key:
            # Use OPENROUTER_API_KEY for openrouter provider, otherwise LITELLM_API_KEY
            if provider == "openrouter":
                env_vars["OPENROUTER_API_KEY"] = str(api_key)
            else:
                env_vars["LITELLM_API_KEY"] = str(api_key)

        if model:
            # For openrouter provider, prepend "openrouter/" to model name
            if provider == "openrouter":
                env_vars["LITELLM_SEED_MODEL"] = f"openrouter/{str(model)}"
            else:
                env_vars["LITELLM_SEED_MODEL"] = str(model)

    for param_name, param_value in request.parameters.items():
        # Skip provider/model/api_key for seed_subtopic_content - handled as env vars above
        if script_name == "seed_subtopic_content" and param_name in ("provider", "model", "api_key"):
            continue

        # Find the parameter definition
        param_def = next((p for p in script_def.parameters if p.name == param_name), None)

        if param_def is None:
            continue

        # Handle boolean parameters
        if param_def.type == "boolean":
            if param_value:
                args.append(f"--{param_name}")
        elif param_def.type == "number":
            args.append(f"--{param_name}")
            args.append(str(param_value))
        else:
            # String parameter
            if param_value or param_def.required:
                args.append(f"--{param_name}")
                if param_value:
                    args.append(str(param_value))

    # Check for required API key (skip for seed_subtopic_content since we handle api_key in params)
    if script_name != "seed_subtopic_content":
        if (
            script_def.requires_api_key
            and not env_vars.get("OPENROUTER_API_KEY")
            and not env_vars.get("LITELLM_API_KEY")
        ):
            # Check if API key was provided in parameters
            api_key = request.parameters.get("api_key")
            if api_key:
                env_vars["OPENROUTER_API_KEY"] = api_key
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This script requires an API key. Please provide 'api_key' in parameters or set OPENROUTER_API_KEY env var.",
                )

    logger.info("executing_script", script=script_name, args=args)

    # Run the script
    return_code, stdout, stderr = await run_script_process(script_name, args, env_vars)

    if return_code == 0:
        return ScriptExecuteResponse(
            script_name=script_name,
            status="completed",
            output=stdout,
            return_code=return_code,
        )
    else:
        return ScriptExecuteResponse(
            script_name=script_name,
            status="failed",
            output=stdout if stdout else None,
            error=stderr,
            return_code=return_code,
        )
