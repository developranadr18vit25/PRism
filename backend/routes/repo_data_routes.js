const express=require("express");
const router=express.Router()
const repo_dataController=require("../controllers/repo_dataController")
const PR_Controller=require("../controllers/PullRequestsController")
const repo_cloneController=require("../controllers/repoCloneController")
const PR_Diff_Controller=require("../controllers/PR_diffController")

router.route("/repos")
    .post(repo_dataController.storeRepoData)

router.route("/cloneRepo")
    .post(repo_cloneController.cloneRepo)

router.route("/PullRequests")
    .get(PR_Controller.fetch_Pull_Requests)

router.route("/PullRequests/diff")
    .get(PR_Diff_Controller.fetch_differences)

module.exports=router;