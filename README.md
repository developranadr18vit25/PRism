##  PRism — Multi-Perspective AI-Powered PR Reviewer

> **Currently in development** — PRism is an ongoing project, with new features and optimizations being actively implemented.

**PRism** is an agentic AI-powered Pull Request review system designed to **reduce PR review time** and provide developers with **clear, accurate, and actionable feedback** on whether a Pull Request is ready to merge or requires changes.

The name **PRism** comes from the idea of looking at a Pull Request through **multiple perspectives**, where different stages of the system analyze different aspects of the code before arriving at a final review decision.

### Agentic AI Workflow

The core of PRism is an **agentic AI workflow** built using **LangGraph and LangChain**.

Instead of relying on a single LLM call, the review process is divided into multiple specialized nodes. Each node performs a specific task, analyzes the available context, and updates a shared state that is passed through the workflow.

### RAG-Based Code Understanding

PRism uses **Retrieval-Augmented Generation (RAG)** to provide the AI agents with relevant context from the repository rather than relying only on the PR diff.

The repository is indexed so that the system can retrieve relevant code, dependencies, and surrounding context while reviewing a change. This helps the agents understand **how a change fits into the existing codebase**, rather than evaluating the changed lines in isolation.

### GitHub OAuth

PRism integrates with GitHub using **OAuth authorization**, allowing users to securely authenticate and give the application access to the repositories they want to review.

### MERN Stack Web Application

Alongside the Python-based AI system, I am building the PRism web application using the **MERN stack — MongoDB, Express.js, React, and Node.js**.

The web application serves as the interface through which users interact with the PR review system. It also provides an opportunity to implement and understand core MERN concepts along with practical **performance and optimization techniques** in a real-world application.

### Objective

The overall goal of PRism is to build a practical developer tool that combines:

**GitHub → Repository Context → RAG → Agentic AI Workflow → Multi-Perspective Analysis → Final PR Review**

The project is currently **under active development**, with the AI review pipeline and MERN-based web application being developed and improved incrementally.
