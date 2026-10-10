
import json
import subprocess
import os

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
WORKTREE_PATH = os.getenv("WORKTREE_PATH")


def run_semgrep_security(file_path):
    try:
        result = subprocess.run(
            [
                "semgrep", "scan",
                "--config", "p/security-audit",  # FOCUSED ON SECURITY
                "--json",
                "--no-git-ignore",
                file_path
            ],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode not in (0, 1):
            return {
                "status": "failed",
                "error": result.stderr or result.stdout
            }

        data = json.loads(result.stdout)
        findings = []

        for finding in data.get("results", []):
            extra = finding.get("extra", {})

            findings.append({
                "rule_id": finding.get("check_id"),
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

    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        return {
            "status": "failed",
            "error": str(e)
        }

    except FileNotFoundError:
        return {
            "status": "failed",
            "error": "Semgrep is not installed or not available in PATH."
        }


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


def Single_File_Security_Test(state: PR_State):
    pr_files = state["pr_Files"]

    single_file_security_test_results = []

    if not REPO_PATH or not BASE_SHA or not WORKTREE_PATH:
        raise ValueError(
            "Set REPO_PATH, BASE_SHA and WORKTREE_PATH in .env."
        )

    if not os.path.isdir(REPO_PATH):
        raise ValueError(
            "REPO_PATH must point to a local Git repository."
        )

    if not os.path.isdir(WORKTREE_PATH):
        raise ValueError(
            "WORKTREE_PATH must point to the existing worktree."
        )

    if not os.path.isdir(os.path.join(WORKTREE_PATH, ".git")):
        if not os.path.isfile(os.path.join(WORKTREE_PATH, ".git")):
            raise ValueError(
                "WORKTREE_PATH is not a valid Git worktree."
            )

    for file in pr_files:
        filename = file["filename"]
        patch = file.get("patch")
        status = file.get("status", "modified")

        try:
            if (
                os.path.isabs(filename)
                or ".." in filename.split("/")
                or "\\" in filename
            ):
                raise ValueError(
                    "Invalid repository-relative filename."
                )

            if not patch:
                single_file_security_test_results.append({
                    "filename": filename,
                    "status": "skipped",
                    "vulnerability": "Patch unavailable",
                    "severity_score": 0,
                    "possible_lines": [],
                    "explanation": "Semgrep and LLM analysis were skipped.",
                    "suggested_fix": "Retrieve the full diff for this file."
                })
                continue

            subprocess.run(
                [
                    "git", "-C", WORKTREE_PATH,
                    "reset", "--hard", BASE_SHA
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=30
            )

            subprocess.run(
                [
                    "git", "-C", WORKTREE_PATH,
                    "clean", "-fd"
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=30
            )

            original_file_path = os.path.join(
                WORKTREE_PATH, filename
            )

            if os.path.isfile(original_file_path):
                with open(
                    original_file_path, "r", encoding="utf-8"
                ) as f:
                    original_code = f.read()
            elif status == "added":
                original_code = ""
            else:
                single_file_security_test_results.append({
                    "filename": filename,
                    "status": "skipped",
                    "vulnerability": "Original file not found",
                    "severity_score": 0,
                    "possible_lines": [],
                    "explanation": "The file was not found at BASE_SHA.",
                    "suggested_fix": "Verify the filename and base commit."
                })
                continue

            patch_path = os.path.join(
                WORKTREE_PATH, ".prism_security_change.patch"
            )

            if status == "added":
                old_path = "/dev/null"
                new_path = f"b/{filename}"
            elif status == "removed":
                old_path = f"a/{filename}"
                new_path = "/dev/null"
            else:
                old_path = f"a/{filename}"
                new_path = f"b/{filename}"

            patch_content = (
                f"diff --git a/{filename} b/{filename}\n"
                f"--- {old_path}\n"
                f"+++ {new_path}\n"
                f"{patch.rstrip()}\n"
            )

            try:
                with open(
                    patch_path, "w", encoding="utf-8"
                ) as f:
                    f.write(patch_content)

                subprocess.run(
                    [
                        "git", "-C", WORKTREE_PATH,
                        "apply", "--check", patch_path
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                subprocess.run(
                    [
                        "git", "-C", WORKTREE_PATH,
                        "apply", patch_path
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30
                )

            finally:
                if os.path.exists(patch_path):
                    os.remove(patch_path)

            merged_file_path = os.path.join(
                WORKTREE_PATH, filename
            )

            if os.path.isfile(merged_file_path):
                with open(
                    merged_file_path, "r", encoding="utf-8"
                ) as f:
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
                    "explanation": "The patched file could not be read.",
                    "suggested_fix": "Check the patch and file status."
                })
                continue

            if not merged_code:
                semgrep_result = {
                    "status": "completed",
                    "findings": []
                }
            else:
                semgrep_result = run_semgrep_security(
                    merged_file_path
                )

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
                    "suggested_fix": "Check Semgrep installation and configuration."
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

        except subprocess.CalledProcessError as e:
            single_file_security_test_results.append({
                "filename": filename,
                "status": "failed",
                "vulnerability": "Git operation or patch application failed",
                "severity_score": 0,
                "possible_lines": [],
                "explanation": e.stderr or str(e),
                "suggested_fix": "Verify the base commit and PR patch."
            })

        except (
            OSError,
            ValueError,
            json.JSONDecodeError
        ) as e:
            single_file_security_test_results.append({
                "filename": filename,
                "status": "failed",
                "vulnerability": "Security analysis incomplete",
                "severity_score": 0,
                "possible_lines": [],
                "explanation": str(e),
                "suggested_fix": "Check the file, patch, and LLM JSON response."
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
        "single_file_security_test_Results": (
            single_file_security_test_results
        )
    }
