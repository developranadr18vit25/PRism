const express=require("express")
const router=express.Router()
const authGitController=require("../controllers/authGitController");
const userGitController=require("../controllers/userGitDetailsController")

router.route("/github")
    .get(authGitController.gitAuthorization)

router.route("/github/callback")
    .get(authGitController.gitTempToken , userGitController.fetchUserDetails)

module.exports=router;