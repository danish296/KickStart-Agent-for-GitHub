# api.py
import os
import httpx
import io
from contextlib import redirect_stdout
from functools import partial

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from github import Github

from langchain_google_genai import ChatGoogleGenerativeAI
# LangChain import compatibility (0.3 moved agents to langchain-classic)
try:
    from langchain.agents import AgentExecutor, create_tool_calling_agent
except Exception:
    from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain import hub

from functools import update_wrapper

from github_tools import (
    list_repository_files, read_file,
    create_or_update_file, delete_file, create_branch,
    create_pull_request, get_issue_details
)

# --- App & Environment Setup ---
load_dotenv()
app = FastAPI(title="Code Sidekick API")

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

user_sessions = {}

# --- Helper Functions ---
def get_github_client(session_id: str) -> Github:
    """Authenticates and returns a PyGithub client for the user."""
    access_token = user_sessions.get(session_id)
    if not access_token:
        raise HTTPException(status_code=401, detail="User not authenticated.")
    return Github(access_token)

# --- OAuth Endpoints ---
@app.get("/login")
def login_via_github():
    return RedirectResponse(f"https://github.com/login/oauth/authorize?client_id={GITHUB_CLIENT_ID}&scope=repo")

@app.get("/callback")
async def github_callback(code: str):
    params = {"client_id": GITHUB_CLIENT_ID, "client_secret": GITHUB_CLIENT_SECRET, "code": code}
    headers = {"Accept": "application/json"}
    
    async with httpx.AsyncClient() as client:
        response = await client.post("https://github.com/login/oauth/access_token", params=params, headers=headers)
    
    response_json = response.json()
    access_token = response_json.get("access_token")
    
    session_id = os.urandom(24).hex()
    user_sessions[session_id] = access_token
    
    return RedirectResponse(f"http://localhost:8501?session_id={session_id}")

# --- NEW: Logout Endpoint ---
class SessionRequest(BaseModel):
    session_id: str
    
@app.post("/logout")
def logout(request: SessionRequest):
    if request.session_id in user_sessions:
        del user_sessions[request.session_id]
        return {"status": "success", "message": "Logged out successfully."}
    return {"status": "error", "message": "Session not found."}


# --- NEW: Repositories Endpoint ---
@app.post("/user/repos")
def get_user_repos(request: SessionRequest):
    """Fetches the list of repositories for the logged-in user."""
    try:
        github_client = get_github_client(request.session_id)
        repos = github_client.get_user().get_repos()
        repo_list = [repo.full_name for repo in repos]
        return {"status": "success", "repos": repo_list}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- Agent API Endpoint ---
class AgentRequest(BaseModel):
    session_id: str
    goal: str

def run_agent(goal: str, github_client: Github):
    """Initializes and runs the LangChain agent."""
    all_tools = [
        partial(list_repository_files, github_client=github_client),
        partial(read_file, github_client=github_client),
        partial(create_or_update_file, github_client=github_client),
        partial(delete_file, github_client=github_client),
        partial(create_branch, github_client=github_client),
        partial(create_pull_request, github_client=github_client),
        partial(get_issue_details, github_client=github_client),
    ]
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", google_api_key=GEMINI_API_KEY)
    prompt = hub.pull("hwchase17/openai-tools-agent")
    agent = create_tool_calling_agent(llm, all_tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=all_tools, verbose=True)

    log_stream = io.StringIO()
    with redirect_stdout(log_stream):
        try:
            result = agent_executor.invoke({"input": goal})
            logs = log_stream.getvalue()
            return {"output": result.get("output", "No output returned."), "logs": logs}
        except Exception as e:
            logs = log_stream.getvalue()
            return {"output": f"An error occurred: {e}", "logs": logs}

@app.post("/run-agent")
def run_agent_endpoint(request: AgentRequest):
    try:
        github_client = get_github_client(request.session_id)
        result = run_agent(request.goal, github_client)
        return {"status": "success", "result": result}
    except HTTPException as e:
        return {"status": "error", "message": e.detail}