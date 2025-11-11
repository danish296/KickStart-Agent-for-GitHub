import os
from github import Github, Auth
from langchain.tools import tool
from dotenv import load_dotenv

# --- GitHub Client Initialization (Dynamic) ---
load_dotenv()
github_client = None

def _init_client_from_env() -> None:
    """Initializes the global github_client from env if available."""
    global github_client
    token = os.getenv("GITHUB_PAT")
    if token:
        auth = Auth.Token(token)
        github_client = Github(auth=auth)

def set_github_token(token: str | None) -> None:
    """Sets or clears the GitHub token for this process and reinitializes the client."""
    global github_client
    if token:
        os.environ["GITHUB_PAT"] = token
        auth = Auth.Token(token)
        github_client = Github(auth=auth)
    else:
        # Clear token and client
        if "GITHUB_PAT" in os.environ:
            del os.environ["GITHUB_PAT"]
        github_client = None

def _ensure_client() -> Github:
    """Returns an initialized Github client or raises a RuntimeError."""
    global github_client
    if github_client is None:
        _init_client_from_env()
    if github_client is None:
        raise RuntimeError("GitHub token not configured. Please set a token to continue.")
    return github_client

# --- Tool Definitions ---
# Each tool now uses the globally available 'github_client'.

@tool
def list_my_repositories() -> list[str]:
    """Lists all repositories the authenticated user has access to."""
    print("🛠️ TOOL: Listing all accessible repositories...")
    try:
        client = _ensure_client()
        repos = client.get_user().get_repos()
        return [repo.full_name for repo in repos]
    except Exception as e:
        return [f"Error listing repositories: {e}"]

@tool
def list_repository_files(repo_name: str) -> str:
    """Lists all files in a repository recursively."""
    print(f"🛠️ TOOL: Listing files in {repo_name}...")
    try:
        client = _ensure_client()
        repo = client.get_repo(repo_name)
        tree = repo.get_git_tree(repo.default_branch, recursive=True).tree
        files = [element.path for element in tree if element.type == 'blob']
        return "\\n".join(files)
    except Exception as e:
        return f"Error listing files: {e}"

@tool
def read_file(repo_name: str, file_path: str) -> str:
    """Reads the content of a file in the repository."""
    print(f"🛠️ TOOL: Reading {file_path} from {repo_name}...")
    try:
        client = _ensure_client()
        repo = client.get_repo(repo_name)
        file_content = repo.get_contents(file_path, ref=repo.default_branch)
        return file_content.decoded_content.decode('utf-8')
    except Exception as e:
        return f"Error reading file: {e}"

@tool
def create_or_update_file(repo_name: str, file_path: str, content: str, commit_message: str) -> str:
    """Creates a new file or updates an existing one in the repository."""
    print(f"🛠️ TOOL: Writing to {file_path} in {repo_name}...")
    try:
        client = _ensure_client()
        repo = client.get_repo(repo_name)
        try:
            existing_file = repo.get_contents(file_path, ref=repo.default_branch)
            repo.update_file(
                path=existing_file.path, message=commit_message,
                content=content, sha=existing_file.sha, branch=repo.default_branch
            )
            return f"Successfully updated file '{file_path}'."
        except Exception:
            repo.create_file(
                path=file_path, message=commit_message,
                content=content, branch=repo.default_branch
            )
            return f"Successfully created file '{file_path}'."
    except Exception as e:
        return f"Error creating or updating file: {e}"

@tool
def delete_file(repo_name: str, file_path: str, commit_message: str) -> str:
    """Deletes a file from the repository."""
    print(f"🛠️ TOOL: Deleting {file_path} from {repo_name}...")
    try:
        client = _ensure_client()
        repo = client.get_repo(repo_name)
        file = repo.get_contents(file_path, ref=repo.default_branch)
        repo.delete_file(
            path=file.path, message=commit_message,
            sha=file.sha, branch=repo.default_branch
        )
        return f"Successfully deleted file '{file_path}'."
    except Exception as e:
        return f"Error deleting file: {e}"
        
@tool
def create_branch(repo_name: str, branch_name: str) -> str:
    """Creates a new branch from the main branch of the repo."""
    print(f"🛠️ TOOL: Creating branch '{branch_name}' in '{repo_name}'...")
    try:
        client = _ensure_client()
        repo = client.get_repo(repo_name)
        source_branch = repo.get_branch(repo.default_branch)
        repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=source_branch.commit.sha)
        return f"Successfully created branch '{branch_name}'."
    except Exception as e:
        return f"Error creating branch: {e}"

@tool
def create_pull_request(repo_name: str, title: str, body: str, head_branch: str) -> str:
    """Creates a pull request."""
    print(f"🛠️ TOOL: Creating PR in {repo_name} from '{head_branch}'...")
    try:
        client = _ensure_client()
        repo = client.get_repo(repo_name)
        base_branch = repo.default_branch
        pr = repo.create_pull(title=title, body=body, head=head_branch, base=base_branch)
        return f"Successfully created Pull Request #{pr.number}: {pr.html_url}"
    except Exception as e:
        return f"Error creating pull request: {e}"

@tool
def get_issue_details(repo_name: str, issue_number: int) -> str:
    """Fetches the title and body of a specific GitHub issue."""
    print(f"🛠️ TOOL: Getting issue #{issue_number} from {repo_name}...")
    try:
        client = _ensure_client()
        repo = client.get_repo(repo_name)
        issue = repo.get_issue(number=issue_number)
        return f"Issue Title: {issue.title}\\nIssue Body: {issue.body}"
    except Exception as e:
        return f"Error getting issue details: {e}"

