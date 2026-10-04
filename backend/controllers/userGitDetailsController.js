const mongoose = require("mongoose")
const { currUser } = require("../Database/schema")
const axios = require("axios")

const fetchUserDetails = (async (req, res) => {

    const token = req.cookies.github_access_token;
    console.log("TOKEN:", token);

    const response = await axios.get("https://api.github.com/user",
        {
            headers: {
                Authorization: `Bearer ${token}`
            }
        }
    );

    const user = await currUser.findOneAndUpdate(

        {
            GithubId: response.id
        },
        {
            GithubId: response.data.id,
            Username: response.data.login,
            Name: response.data.name,
            PublicRepoCount: response.data.public_repos,
            ReposUrl: response.data.repos_url,
            Email: response.data.email
        },
        {
            new: true,
            upsert: true
        }
    )

    return res.json({
        Message:"User Saved Successfully",
        UserData:user
    })
})

module.exports = {
    fetchUserDetails
}