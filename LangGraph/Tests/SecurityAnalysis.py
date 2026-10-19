import json
import subprocess
import os
import docker
from docker.errors import DockerException

from dotenv import load_dotenv
from langchain_mistralai import ChatMistralAI


from workFlow import PR_State

load_dotenv()

llm = ChatMistralAI(
    model="mistral-small-latest",
    temperature=0
)

REPO_PATH = os.getenv("REPO_PATH")
BASE_SHA = os.getenv("BASE_SHA")
# WORKTREE_PATH = os.getenv("WORKTREE_PATH")
SEMGREP_IMAGE = os.getenv(
    "SEMGREP_IMAGE",
    "semgrep/semgrep:latest"
)


def run_semgrep_security(worktree_path, filename):
    client = None
    container = None

    try:
        client = docker.from_env()

        container = client.containers.run(
            image=SEMGREP_IMAGE,
            command=[
                "semgrep",
                "scan",
                "--config", "p/security-audit",
                "--config", "/rules/security_rules.yml",
                "--json",
                "--quiet",
                "--no-git-ignore",
                f"/workspace/repo/{filename}"
            ],
            volumes={
                os.path.abspath(worktree_path): {
                    "bind": "/workspace/repo",
                    "mode": "ro"
                },
                os.path.abspath("../Custom/Checks/security_rules.yml"): {
                    "bind": "/rules/security_rules.yml",
                    "mode": "ro"
                }
            },
            working_dir="/workspace/repo",
            detach=True,
            mem_limit="1g",
            network_mode="bridge"
        )

        exit_result = container.wait(timeout=120)
        exit_code = exit_result.get("StatusCode", -1)

        stdout = container.logs(
            stdout=True,
            stderr=False
        ).decode("utf-8", errors="replace")

        stderr = container.logs(
            stdout=False,
            stderr=True
        ).decode("utf-8", errors="replace")

        if exit_code not in (0, 1):
            return {
                "status": "failed",
                "error": stderr or stdout or f"Semgrep exited with code {exit_code}"
            }

        data = json.loads(stdout)
        findings = []

        for finding in data.get("results", []):
            extra = finding.get("extra", {})

            findings.append({
                "rule_id": finding.get("check_id"),
                "path": finding.get("path"),
                "message": extra.get("message"),
                "severity": extra.get("severity"),
                "start_line": finding.get("start", {}).get("line"),
                "end_line": finding.get("end", {}).get("line"),
                "code": extra.get("lines"),
                "metadata": extra.get("metadata", {})
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
            client.close()


def analyze_security_with_llm(
    filename,
    original_code,
    merged_code,
    semgrep_findings
):
    prompt = f"""
You are a senior application security engineer reviewing a pull request.

Analyze the changed file using:

1. The original code from the base commit.
2. The code after applying the PR patch.
3. The security findings reported by Semgrep.

Identify security vulnerabilities introduced or worsened by the patch.

Consider issues such as:
- Injection vulnerabilities
- Authentication and authorization weaknesses
- Improper input validation
- Hardcoded secrets and sensitive information exposure
- Unsafe deserialization
- Path traversal and file handling vulnerabilities
- Insecure cryptographic practices
- Unsafe execution of commands
- Other relevant application security weaknesses

Treat Semgrep findings as evidence, not proof.
Verify whether each finding is applicable to the actual code.
Do not assume every finding is a vulnerability.
Do not invent vulnerabilities.
Distinguish newly introduced vulnerabilities from pre-existing issues.

Assess severity from 0 to 10:
0 = no apparent vulnerability introduced
1-3 = low
4-6 = moderate
7-8 = high
9-10 = critical

Possible lines must refer to line numbers in the resulting file.
If exact lines cannot be determined, return an empty list.

The analysis is limited to this file and the supplied context.
Do not claim that cross-file behavior has been verified.

Return ONLY valid JSON in this format:

{{
    "filename": "{filename}",
    "vulnerability": "Description of the vulnerability or No security vulnerabilities identified",
    "severity_score": 0,
    "possible_lines": [],
    "explanation": "Reasoning based on the supplied code and findings",
    "suggested_fix": "Minimal relevant fix or No changes required"
}}

FILE: {filename}

ORIGINAL CODE:
{original_code}

CODE AFTER PATCH:
{merged_code}

SEMGREP SECURITY FINDINGS:
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
        "vulnerability": result.get(
            "vulnerability",
            "Unable to determine"
        ),
        "severity_score": result.get("severity_score", 0),
        "possible_lines": result.get("possible_lines", []),
        "explanation": result.get(
            "explanation",
            "Unable to determine"
        ),
        "suggested_fix": result.get(
            "suggested_fix",
            "Unable to determine"
        )
    }


def Single_File_Security_Test(worktree_path, changed_files):
    single_file_security_test_results = []

    if not REPO_PATH or not BASE_SHA or not worktree_path:
        raise ValueError("Set REPO_PATH and BASE_SHA in .env and pass worktree_path.")

    if not os.path.isdir(REPO_PATH):
        raise ValueError("REPO_PATH must point to a local Git repository.")

    worktree_path = os.path.abspath(worktree_path)

    if not os.path.isdir(worktree_path):
        raise ValueError("WORKTREE_PATH must point to the existing merged worktree.")

    for file in changed_files:
        filename = file["filename"]
        status = file.get("status", "modified")

        try:
            if (
                not filename
                or os.path.isabs(filename)
                or ".." in filename.split("/")
                or "\\" in filename
            ):
                raise ValueError("Invalid repository-relative filename.")

            original_result = subprocess.run(
                ["git", "show", f"{BASE_SHA}:{filename}"],
                cwd=REPO_PATH,
                capture_output=True,
                text=True,
                timeout=30
            )

            if original_result.returncode == 0:
                original_code = original_result.stdout
            elif status == "added":
                original_code = ""
            else:
                single_file_security_test_results.append({
                    "filename": filename,
                    "status": "skipped",
                    "vulnerability": "Original file not found",
                    "severity_score": 0,
                    "possible_lines": [],
                    "explanation": original_result.stderr,
                    "suggested_fix": "Verify the filename and base commit."
                })
                continue

            merged_file_path = os.path.join(worktree_path, filename)

            if os.path.isfile(merged_file_path):
                with open(merged_file_path, "r", encoding="utf-8") as f:
                    merged_code = f.read()
            elif status == "removed":
                merged_code = ""
            else:
                single_file_security_test_results.append({
                    "filename": filename,
                    "status": "skipped",
                    "vulnerability": "Resulting file not found",
                    "severity_score": 0,
                    "possible_lines": [],
                    "explanation": "The file was not found in the merged worktree.",
                    "suggested_fix": "Verify the worktree and filename."
                })
                continue

            if merged_code:
                semgrep_result = run_semgrep_security(
                    worktree_path=worktree_path,
                    filename=filename
                )
            else:
                semgrep_result = {
                    "status": "completed",
                    "findings": []
                }

            if semgrep_result["status"] != "completed":
                single_file_security_test_results.append({
                    "filename": filename,
                    "status": "failed",
                    "vulnerability": "Semgrep security analysis failed",
                    "severity_score": 0,
                    "possible_lines": [],
                    "explanation": semgrep_result.get(
                        "error", "Unknown Semgrep error."
                    ),
                    "suggested_fix": "Check Docker, Semgrep, and its configuration."
                })
                continue

            analysis = analyze_security_with_llm(
                filename=filename,
                original_code=original_code,
                merged_code=merged_code,
                semgrep_findings=semgrep_result["findings"]
            )

            single_file_security_test_results.append({
                **analysis,
                "status": "completed",
                "semgrep_findings": semgrep_result["findings"]
            })

        except Exception as e:
            single_file_security_test_results.append({
                "filename": filename,
                "status": "failed",
                "vulnerability": "Security analysis failed",
                "severity_score": 0,
                "possible_lines": [],
                "explanation": str(e),
                "suggested_fix": "Inspect the error and retry the analysis."
            })

    return {
        "single_file_security_test_Results": single_file_security_test_results
    }