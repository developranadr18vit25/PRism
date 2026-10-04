const mongoose = require("mongoose");
const axios = require("axios");
const { response } = require("express");
const AdmZip = require("adm-zip");
const { Document } = require("@langchain/core/documents");
// const { QdrantVectorStore } = require("@langchain/qdrant");
const { MistralAIEmbeddings } = require("@langchain/mistralai");
const { Chroma } = require("@langchain/community/vectorstores/chroma");

const storeRepoData = (async (req, res) => {

    try {

        const token = req.cookies.github_access_token;
        const repoName = req.body.repoName;

        const response = await axios.get(`https://api.github.com/repos/developranadr18vit25/${repoName}/zipball/main`,
            {
                headers: {
                    Authorization: `Bearer ${token}`,
                },
                responseType: "arraybuffer"
            }
        );

        const zipBuffer = response.data;

        const zip = new AdmZip(zipBuffer);
        const entries = zip.getEntries();

        const documents = [];

        for (const entry of entries) {

            if (entry.isDirectory) {
                continue;
            }

            const fileName = entry.entryName;

            if (
                fileName.includes("node_modules/") ||
                fileName.endsWith("package-lock.json") ||
                fileName.endsWith(".png") ||
                fileName.endsWith(".jpg") ||
                fileName.endsWith(".jpeg") ||
                fileName.endsWith(".gif") ||
                fileName.endsWith(".svg")
            ) {
                continue;
            }

            const fileContent = entry
                .getData()
                .toString("utf8");

            documents.push(
                new Document({
                    pageContent: fileContent,

                    metadata: {
                        fileName: fileName,
                        repoName: repoName
                    }
                })
            );
        }

        const embeddings = new MistralAIEmbeddings({
            model: "mistral-embed",
            apiKey: process.env.MISTRAL_API_KEY
        });

        await Chroma.fromDocuments(
            documents,
            embeddings,
            {
                url: "http://localhost:8000",
                collectionName: repoName
            }
        );

        res.json({
            message: "Repository embedded successfully",
            files: documents.length
        });

    } catch (error) {

        console.error(error);

        res.status(500).json({
            error: "Failed to process repository"
        });
    }
})

module.exports = {
    storeRepoData
}