const path = require("path");
require("dotenv").config()

const clientId = process.env.GITHUB_CLIENT_ID;
const clientSecret = process.env.GITHUB_CLIENT_SECRET;

const getGitAccess_Token = async (code) => { 

    // FOR SENDING THE TEMP TOKEN AND GETTING THE ACCESS TOKEN  

    const response = await fetch("https://github.com/login/oauth/access_token", {
        method: "POST",
        headers: {
            "Accept": "application/json",
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            client_id: clientId,
            client_secret: clientSecret,
            code:code

        })
    })
    const data=await response.json();

    return data.access_token;
}

module.exports={
    getGitAccess_Token
}