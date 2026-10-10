import json
import shutil
import tempfile
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


def run_semgrep(file_path):
    try:
        result = subprocess.run(
            [
                "semgrep", "scan",
                "--config", "auto",  #GENERAL TEST
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
                "error": result.stderr
            }

        data = json.loads(result.stdout)
        findings = []

        for finding in data.get("results", []):
            findings.append({
                "rule_id": finding.get("check_id"),
                "message": finding.get("extra", {}).get("message"),
                "severity": finding.get("extra", {}).get("severity"),
                "start_line": finding.get("start", {}).get("line"),
                "end_line": finding.get("end", {}).get("line"),
                "code": finding.get("extra", {}).get("lines")
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
3. The static analysis findings from Semgrep.

Do not assume every Semgrep finding is a logic error.
Semgrep findings are evidence, not proof.

Identify actual or plausible logic errors introduced by the patch.
Focus on incorrect conditions, boundary cases, calculations,
return values, broken assumptions, and unintended behavior.

Do not invent bugs. If you cannot identify a plausible logic error,
return "No logic errors".

Severity score is your assessment from 0 to 10:
0 = no apparent logic error
1-3 = low impact
4-6 = moderate impact
7-8 = high impact
9-10 = critical impact

Possible lines must refer to line numbers in the resulting file.
If you cannot determine exact lines, say so rather than inventing them.
Propose minimal, relevant fixes.

Return ONLY valid JSON in this exact format:

{{
    "filename": "{filename}",
    "logic error": "Description of the error or No logic errors",
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


def Logic_Bug_Test(state: PR_State):
    pr_files = state["pr_Files"]
    single_file_logic_test_results = []

    if not REPO_PATH or not BASE_SHA:
        raise ValueError(
            "Set REPO_PATH and BASE_SHA in your .env file."
        )

    if not os.path.isdir(REPO_PATH):
        raise ValueError(
            "REPO_PATH must point to a local Git repository."
        )

    temp_dir = tempfile.mkdtemp(prefix="prism_")
    worktree_path = os.path.join(temp_dir, "worktree")
    worktree_created = False

    try:
        subprocess.run(
            [
                "git", "-C", REPO_PATH,
                "worktree", "add", "--detach",
                worktree_path, BASE_SHA
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=120
        )

        worktree_created = True

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
                    single_file_logic_test_results.append({
                        "filename": filename,
                        "status": "skipped",
                        "logic error": "Patch unavailable",
                        "severity score": 0,
                        "possible lines": [],
                        "Suggested_changes": (
                            "Retrieve the full diff for this file."
                        )
                    })
                    continue

                subprocess.run(
                    [
                        "git", "-C", worktree_path,
                        "reset", "--hard", BASE_SHA
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                subprocess.run(
                    [
                        "git", "-C", worktree_path,
                        "clean", "-fd"
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                original_file_path = os.path.join(
                    worktree_path, filename
                )

                if os.path.isfile(original_file_path):
                    with open(
                        original_file_path, "r", encoding="utf-8"
                    ) as f:
                        original_code = f.read()
                elif status == "added":
                    original_code = ""
                else:
                    single_file_logic_test_results.append({
                        "filename": filename,
                        "status": "skipped",
                        "logic error": "Original file not found",
                        "severity score": 0,
                        "possible lines": [],
                        "Suggested_changes": (
                            "Verify the filename and base commit."
                        )
                    })
                    continue

                patch_path = os.path.join(
                    temp_dir, "change.patch"
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

                with open(
                    patch_path, "w", encoding="utf-8"
                ) as f:
                    f.write(patch_content)

                subprocess.run(
                    [
                        "git", "-C", worktree_path,
                        "apply", "--check", patch_path
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                subprocess.run(
                    [
                        "git", "-C", worktree_path,
                        "apply", patch_path
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                merged_file_path = os.path.join(
                    worktree_path, filename
                )

                if os.path.isfile(merged_file_path):
                    with open(
                        merged_file_path, "r", encoding="utf-8"
                    ) as f:
                        merged_code = f.read()
                elif status == "removed":
                    merged_code = ""
                else:
                    single_file_logic_test_results.append({
                        "filename": filename,
                        "status": "skipped",
                        "logic error": "Resulting file not found",
                        "severity score": 0,
                        "possible lines": [],
                        "Suggested_changes": (
                            "Check whether the file was deleted or renamed."
                        )
                    })
                    continue

                if not merged_code:
                    semgrep_result = {
                        "status": "completed",
                        "findings": []
                    }
                else:
                    semgrep_result = run_semgrep(
                        merged_file_path
                    )

                if semgrep_result["status"] != "completed":
                    single_file_logic_test_results.append({
                        "filename": filename,
                        "status": "failed",
                        "logic error": "Semgrep analysis failed",
                        "severity score": 0,
                        "possible lines": [],
                        "Suggested_changes": semgrep_result.get(
                            "error", "Check Semgrep configuration."
                        )
                    })
                    continue

                analysis = analyze_logic_with_llm(
                    filename=filename,
                    original_code=original_code,
                    merged_code=merged_code,
                    semgrep_findings=semgrep_result["findings"]
                )

                single_file_logic_test_results.append({
                    **analysis,
                    "status": "completed",
                    "semgrep_findings": semgrep_result["findings"]
                })

            except subprocess.CalledProcessError as e:
                single_file_logic_test_results.append({
                    "filename": filename,
                    "status": "failed",
                    "logic error": "Git operation or patch application failed",
                    "severity score": 0,
                    "possible lines": [],
                    "Suggested_changes": e.stderr or str(e)
                })

            except (
                OSError,
                ValueError,
                json.JSONDecodeError
            ) as e:
                single_file_logic_test_results.append({
                    "filename": filename,
                    "status": "failed",
                    "logic error": "Analysis incomplete",
                    "severity score": 0,
                    "possible lines": [],
                    "Suggested_changes": str(e)
                })

            except Exception as e:
                single_file_logic_test_results.append({
                    "filename": filename,
                    "status": "failed",
                    "logic error": "Analysis failed",
                    "severity score": 0,
                    "possible lines": [],
                    "Suggested_changes": str(e)
                })

    finally:
        if worktree_created:
            try:
                subprocess.run(
                    [
                        "git", "-C", REPO_PATH,
                        "worktree", "remove",
                        "--force", worktree_path
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
            except subprocess.TimeoutExpired:
                pass

        shutil.rmtree(temp_dir, ignore_errors=True)

    return {
        "single_file_logic_test_Results": single_file_logic_test_results
    }
    
    
    
    
    
# CREATING A TEMPORARY WORKTREE ONLY ONCE AND THEN PERFORMING MERGE FOR EACH OF THE FILE AND RUNNING SEMGREP ON IT . THEN PASSING THE FINDINGS TO THE LLM AND PROVIDING THE CONCLUSION OF EACH FILE IN LOGICAL RESULTS 