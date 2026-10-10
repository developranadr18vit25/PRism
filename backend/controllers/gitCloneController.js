const { execFile } = require("child_process");
const { promisify } = require("util");
const fs = require("fs");
const os = require("os");
const path = require("path");

const execFileAsync = promisify(execFile);

const cloneRepo = async (req, res) => {
    try {
        const { username, repoName } = req.body;

        const tempDir = await fs.promises.mkdtemp(
            path.join(os.tmpdir(), "prism-")
        );

        const repoPath = path.join(__dirname, "..", "repos", repoName);

        await execFileAsync("git", [
            "clone",
            `https://github.com/${username}/${repoName}.git`,
            repoPath
        ]);

        res.json({ repoPath });

    } catch (error) {
        res.status(500).json({ message: "Failed to clone repository" });
    }
};

module.exports={cloneRepo}