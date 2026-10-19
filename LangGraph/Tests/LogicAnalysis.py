
import json
import os
import shutil
import tempfile
import subprocess

import docker
from docker.errors import DockerException

from dotenv import load_dotenv
from langchain_mistralai import ChatMistralAI

# from workFlow import PR_State


load_dotenv()

llm = ChatMistralAI(
    model="mistral-small-latest",
    temperature=0
)

REPO_PATH = os.getenv("REPO_PATH")
BASE_SHA = os.getenv("BASE_SHA")
SEMGREP_IMAGE = os.getenv(
    "SEMGREP_IMAGE",
    "semgrep/semgrep:latest"
)

# worktree_path = "/var/folders/sb/0dh9kxt13p13p7n5_tpnj1680000gn/T/pr-2-3mjmj2le"


def run_semgrep(worktree_path , filename):
    client = None
    container = None

    try:
        client = docker.from_env(timeout=180)
        client.ping()

        
        container = client.containers.run(
            image=SEMGREP_IMAGE,
            command=[
                "semgrep",
                "scan",
                "--config", "auto",
                "--config", "/rules/logic_rules.yml",
                "--json",
                "--no-git-ignore",
                f"/workspace/repo/{filename}"
            ],
            volumes={
                os.path.abspath(worktree_path): {
                    "bind": "/workspace/repo",
                    "mode": "ro"
                },
                os.path.abspath("../Custom/Checks/logic_rules.yml"): {
                    "bind": "/rules/logic_rules.yml",
                    "mode": "ro"
                }
            },
            working_dir="/workspace/repo",
            detach=True,
            mem_limit="1g",
            network_mode="bridge"
        )


        result = container.wait(timeout=180)

        stdout = container.logs(
            stdout=True,
            stderr=False
        ).decode("utf-8", errors="replace")

        stderr = container.logs(
            stdout=False,
            stderr=True
        ).decode("utf-8", errors="replace")

        if result.get("StatusCode") not in (0, 1):
            return {
                "status": "failed",
                "error": stderr or stdout or "Semgrep failed"
            }

        data = json.loads(stdout)
        findings = []

        for finding in data.get("results", []):
            extra = finding.get("extra", {})
            path = finding.get("path", "")

            if path.startswith("/workspace/repo/"):
                path = path[len("/workspace/repo/"):]

            findings.append({
                "rule_id": finding.get("check_id"),
                "path": path,
                "message": extra.get("message"),
                "severity": extra.get("severity"),
                "start_line": finding.get("start", {}).get("line"),
                "end_line": finding.get("end", {}).get("line"),
                "code": extra.get("lines")
            })

        return {
            "status": "completed",
            "findings": findings
        }

    except Exception as e:
        return {
            "status": "failed",
            "error": str(e)
        }

    finally:
        if container is not None:
            try:
                container.remove(force=True)
            except DockerException:
                pass

        if client is not None:
            try:
                client.close()
            except Exception:
                pass


def analyze_logic_with_llm(
    filename,
    original_code,
    merged_code,
    semgrep_findings
):
    prompt = f"""
You are a senior software engineer reviewing a pull request
for potential logic errors.

Analyze the changed file using:

1. The original code from the base commit.
2. The code after applying the PR patch.
3. Static analysis findings from Semgrep.

Do not assume every Semgrep finding is a logic error.
Semgrep findings are evidence, not proof.

Identify actual or plausible logic errors introduced by the patch.
Focus on incorrect conditions, boundary cases, calculations,
return values, broken assumptions, and unintended behavior.

Do not invent bugs. If you cannot identify a plausible logic error,
return "No logic errors".

Severity score:
0 = no apparent logic error
1-3 = low impact
4-6 = moderate impact
7-8 = high impact
9-10 = critical impact

Possible lines must refer to line numbers in the resulting file.
Do not invent line numbers. Propose minimal, relevant fixes.

Return ONLY valid JSON in this format:

{{
    "filename": {json.dumps(filename)},
    "logic error": "Description or No logic errors",
    "severity score": 0,
    "possible lines": [],
    "Suggested_changes": "Suggested fix or No changes required"
}}

FILE: {filename}

ORIGINAL CODE:
{original_code}

CODE AFTER PATCH:
{merged_code}

SEMGREP FINDINGS:
{json.dumps(semgrep_findings, indent=2)}
"""

    response = llm.invoke(prompt)
    content = response.content

    if isinstance(content, list):
        content = "".join(
            item.get("text", "") if isinstance(item, dict)
            else str(item)
            for item in content
        )

    content = content.strip()

    if content.startswith("```"):
        content = content.split("\n", 1)[1]
        content = content.rsplit("```", 1)[0].strip()

    result = json.loads(content)

    return {
        "filename": filename,
        "logic error": result.get(
            "logic error", "Unable to determine"
        ),
        "severity score": result.get("severity score", 0),
        "possible lines": result.get("possible lines", []),
        "Suggested_changes": result.get(
            "Suggested_changes", "Unable to determine"
        )
    }


def main_logic_analysis(worktree_path, changed_files, base_sha):
    repo_path = REPO_PATH
    results = []

    try:

        for filename in changed_files:
            
            semgrep_result = run_semgrep(worktree_path,filename)
            
            if semgrep_result["status"] == "failed":
                return {
                "filename":filename,
                "status": "failed",
                "error": semgrep_result["error"],
                "results": []
            }
                
            all_findings = semgrep_result.get("findings", [])
            
            original_result = subprocess.run(
                [
                    "git",
                    "show",
                    f"{base_sha}:{filename}"
                ],
                cwd=repo_path,
                capture_output=True,
                text=True
            )

            original_code = (
                original_result.stdout
                if original_result.returncode == 0
                else ""
            )

            merged_file_path = os.path.join(
                worktree_path,
                filename
            )

            if os.path.isfile(merged_file_path):
                with open(
                    merged_file_path,
                    "r",
                    encoding="utf-8",
                    errors="replace"
                ) as file:
                    merged_code = file.read()
            else:
                merged_code = ""

            file_findings = [
                finding
                for finding in all_findings
                if finding["path"] == filename
            ]

            analysis = analyze_logic_with_llm(
                filename=filename,
                original_code=original_code,
                merged_code=merged_code,
                semgrep_findings=file_findings
            )

            results.append(analysis)

        return {
            "filename":filename,
            "status": "completed",
            "total_files": len(changed_files),
            "results": results
        }

    except Exception as e:
        return {
            "filename":filename,
            "status": "failed",
            "error": str(e),
            "results": results
        }
