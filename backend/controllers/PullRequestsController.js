const moongoose=require("mongoose")
const axios=require("axios")

const fetch_Pull_Requests=(async(req,res)=>{

    const token=req.cookies.github_access_token; 
    const repoName=req.body.repoName;

    const response=await axios.get(`https://api.github.com/repos/developranadr18vit25/${repoName}/pulls`);

    return res.json({
        PR:response.data
    })

})

module.exports={
    fetch_Pull_Requests
}