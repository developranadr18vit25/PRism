const axios=require('axios');
const mongoose=require("mongoose")


const fetch_differences=(async(req,res)=>{

    const repoName=req.body.repoName;
    const pullNo=req.body.pull_number;

    const response=await axios.get(`https://api.github.com/repos/developranadr18vit25/${repoName}/pulls/${pullNo}/files`);

    const pr_Files=response.data.map(file=>({
        filename:file.filename,
        status:file.status,
        additions:file.additions,
        deletions:file.deletions,
        patch:file.patch
    }));

    const result=axios.post("http://127.0.0.1:8000/review" , {
        pr_Files:pr_Files
    })

    return res.json({
        Message:"PR_Diff stored in langGraph state successfully"
    })
})

module.exports={
    fetch_differences
}