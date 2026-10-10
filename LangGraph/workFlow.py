import os 
from dotenv import load_dotenv
from fastapi import FastAPI
load_dotenv()

app=FastAPI()

from langchain_mistralai import ChatMistralAI , MistralAIEmbeddings
from langgraph.graph import StateGraph
from pydantic import BaseModel
from typing import List , TypedDict
from langchain_community.vectorstores import Chroma
from helper import make_js_tree , find_function_calls , get_language

llm=ChatMistralAI(model="mistral-small-latest")

embedding_model=MistralAIEmbeddings(model="mistral-embed")

vector_store = Chroma(
    persist_directory="./vectorStore/chroma-db",
    embedding_function=embedding_model
)

class PR_State(TypedDict):

    pr_Files:List[dict]
    single_file_logic_test_Results:List[dict]
    
    
    

    

@app.post("/review")

def review_pr(data: PR_State):

    initial_state = {
        "pr_Files": data["pr_Files"]
    }

    print(initial_state)

    return initial_state


    
