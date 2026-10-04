const express = require("express")
const app = express()
const cors = require("cors")
const authRouter = require("../backend/routes/auth_routes")
const repo_dataRouter = require("../backend/routes/repo_data_routes")
const cookieParser = require("cookie-parser");
const connectDB = require("./Database/connect")
const { spawn } = require("child_process");
// const loginRouter=require("../backend/routes/login_routes")


const chromaServer = spawn("chroma", ["run", "--path", "./chroma-db"], { stdio: "inherit" });

app.use(cors())
app.use(express.json())
app.use(cookieParser())
connectDB()

app.get("/", (req, res) => {
    res.send("Express is working")
})

app.use("/auth", authRouter);
app.use("/git", repo_dataRouter);
// app.use("/login" , loginRouter);

app.listen(4000, () => {
    console.log("Running on port 4000")
})