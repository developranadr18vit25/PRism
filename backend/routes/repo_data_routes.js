const express=require("express");
const router=express.Router()
const repo_dataController=require("../controllers/repo_dataController")
const PR_Controller=require("../controllers/PullRequestsController")
const PR_Diff_Controller=require("../controllers/PR_diffController")
const git_Clone_Controller=require("../controllers/gitCloneController")

router.route("/repos")
    .post(repo_dataController.storeRepoData , git_Clone_Controller.cloneRepo)

router.route("/PullRequests")
    .get(PR_Controller.fetch_Pull_Requests)

router.route("/PullRequests/diff")
    .get(PR_Diff_Controller.fetch_differences)

module.exports=router;