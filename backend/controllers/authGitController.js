const path = require("path");
const { getGitAccess_Token } = require("../controllers/loginController")
require("dotenv").config()

const clientId = process.env.GITHUB_CLIENT_ID;

const gitAuthorization = ((req, res) => {

    console.log("Client ID:", process.env.GITHUB_CLIENT_ID);

    const gitAuthUrl = `https://github.com/login/oauth/authorize?client_id=${clientId}&redirect_uri=http://localhost:4000/auth/github/callback&scope=repo&state=random123`;

    res.redirect(gitAuthUrl)

    // return res.json({
    //     Message:"Temporary token fetched from github"
    // })
});

const gitTempToken = (async (req, res ,next) => {

    const code = req.query.code;

    const accessToken = await getGitAccess_Token(code);

    res.cookie(
        "github_access_token",
        accessToken,
        {
            httpOnly: true,
            secure: false,
            sameSite: "lax"
        }
    );

    console.log("Calling next()");
    console.log(accessToken)

    next()

})

module.exports = {
    gitAuthorization,
    gitTempToken
}