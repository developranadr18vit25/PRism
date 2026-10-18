
import os
import subprocess
import tempfile
import shutil
from dotenv import load_dotenv

load_dotenv()


def run_git(command, cwd):
    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Git command failed:\n"
            f"Command: {' '.join(command)}\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

    return result


def simulate_merge():

    repo_path = os.getenv("REPO_PATH")
    pr_number = 2
    target_branch = "main"

    temp_dir = tempfile.mkdtemp(
        prefix=f"pr-{pr_number}-"
    )
    print("Worktree path:", temp_dir)

    worktree_created = False

    try:
        run_git(
            [
                "git",
                "fetch",
                "origin",
                f"pull/{pr_number}/head:refs/prism/pr-{pr_number}"
            ],
            repo_path
        )

        pr_ref = f"refs/prism/pr-{pr_number}"

        run_git(
            [
                "git",
                "worktree",
                "add",
                "--detach",
                temp_dir,
                target_branch
            ],
            repo_path
        )

        worktree_created = True

        merge_result = subprocess.run(
            [
                "git",
                "merge",
                "--no-commit",
                "--no-ff",
                pr_ref
            ],
            cwd=temp_dir,
            capture_output=True,
            text=True
        )

        if merge_result.returncode != 0:

            conflict_result = subprocess.run(
                [
                    "git",
                    "diff",
                    "--name-only",
                    "--diff-filter=U"
                ],
                cwd=temp_dir,
                capture_output=True,
                text=True
            )

            conflicts = [
                line.strip()
                for line in conflict_result.stdout.splitlines()
                if line.strip()
            ]

            run_git(
                [
                    "git",
                    "merge",
                    "--abort"
                ],
                temp_dir
            )

            run_git(
                [
                    "git",
                    "worktree",
                    "remove",
                    "--force",
                    temp_dir
                ],
                repo_path
            )

            worktree_created = False

            return {
                "simulated_merge": {
                    "success": False,
                    "merge_conflict": True,
                    "conflicting_files": conflicts,
                    "error": (
                        merge_result.stdout
                        + merge_result.stderr
                    ),
                    "worktree": None
                },
                "analysis_stopped": True
            }

        status_result = run_git(
            [
                "git",
                "status",
                "--short"
            ],
            temp_dir
        )

        diff_result = run_git(
            [
                "git",
                "diff",
                "--name-only",
                target_branch
            ],
            temp_dir
        )

        merged_files = [
            line.strip()
            for line in diff_result.stdout.splitlines()
            if line.strip()
        ]

        return {
            "simulated_merge": {
                "success": True,
                "merge_conflict": False,
                "worktree": temp_dir,
                "merged_files": merged_files,
                "status": status_result.stdout
            },
            "worktree_path": temp_dir,
            "analysis_stopped": False
        }

    except Exception as e:

        if worktree_created:
            try:
                subprocess.run(
                    [
                        "git",
                        "merge",
                        "--abort"
                    ],
                    cwd=temp_dir,
                    capture_output=True,
                    text=True
                )

                run_git(
                    [
                        "git",
                        "worktree",
                        "remove",
                        "--force",
                        temp_dir
                    ],
                    repo_path
                )

            except Exception:
                pass

        else:
            shutil.rmtree(
                temp_dir,
                ignore_errors=True
            )

        return {
            "simulated_merge": {
                "success": False,
                "merge_conflict": False,
                "error": str(e),
                "worktree": None
            },
            "analysis_stopped": True
        }



result = simulate_merge()
print(result)