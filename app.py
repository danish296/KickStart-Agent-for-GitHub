import streamlit as st
import os
import io
from contextlib import redirect_stdout
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
# LangChain import compatibility (0.3 moved agents to langchain-classic)
try:
    from langchain.agents import AgentExecutor, create_tool_calling_agent
except Exception:  # ImportError or others
    from langchain_classic.agents import AgentExecutor, create_tool_calling_agent

# Hub import compatibility (requires langchainhub package in newer setups)
try:
    from langchain import hub
except Exception:
    from langchainhub import pull as hub_pull
    # Create a hub-like object for compatibility
    class hub:
        pull = staticmethod(hub_pull)

# Import all the tools from your github_tools.py file
from github_tools import (
    list_my_repositories, list_repository_files, read_file,
    create_or_update_file, delete_file, create_branch,
    create_pull_request, get_issue_details
)
from github_tools import set_github_token

# --- Page & Agent Configuration ---
st.set_page_config(
    page_title="Code Sidekick Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Use Streamlit's caching to load the agent once and reuse it
@st.cache_resource
def load_agent():
    """Loads and initializes the LangChain agent and its tools."""
    print("Loading agent...")
    load_dotenv()
    
    # Check for required API key (GitHub PAT will be provided dynamically by the user)
    if not os.getenv("GEMINI_API_KEY"):
        return None, "GEMINI_API_KEY not found. Please add it to your .env file."

    # Define the list of tools the agent can use
    tools = [
        list_my_repositories, list_repository_files, read_file,
        create_or_update_file, delete_file, create_branch,
        create_pull_request, get_issue_details
    ]
    
    # Initialize the LLM
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-lite", google_api_key=os.getenv("GEMINI_API_KEY"))
    
    # Create the agent
    prompt = hub.pull("hwchase17/openai-tools-agent")
    agent = create_tool_calling_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True)
    
    return agent_executor, None

# --- Main Application UI ---
st.title("Code Sidekick Agent 🤖")

# Load the agent
agent_executor, error = load_agent()

if error:
    st.error(error)
else:
    # --- Sidebar Configuration ---
    st.sidebar.title("Configuration")
    st.sidebar.markdown("Authenticate with GitHub and select a repository.")

    # --- GitHub Authentication (Dynamic PAT) ---
    if "github_pat" not in st.session_state:
        st.session_state.github_pat = os.getenv("GITHUB_PAT", "")

    with st.sidebar.form("github_auth_form", clear_on_submit=False):
        pat_input = st.text_input("GitHub Personal Access Token", value=st.session_state.github_pat, type="password", help="Token requires repo scope to read/write to your repos.")
        col_a, col_b = st.columns(2)
        connect_clicked = col_a.form_submit_button("Connect", type="primary")
        disconnect_clicked = col_b.form_submit_button("Disconnect")

    if connect_clicked:
        st.session_state.github_pat = pat_input.strip()
        try:
            set_github_token(st.session_state.github_pat or None)
            st.sidebar.success("Connected to GitHub.")
        except Exception as e:
            st.sidebar.error(f"Failed to set token: {e}")

    if disconnect_clicked:
        st.session_state.github_pat = ""
        try:
            set_github_token(None)
            st.sidebar.info("Disconnected from GitHub.")
        except Exception as e:
            st.sidebar.error(f"Failed to clear token: {e}")

    try:
        # Use the tool directly to fetch repositories
        repos = list_my_repositories.invoke({}) if st.session_state.github_pat else []
        if not st.session_state.github_pat:
            st.sidebar.warning("Enter and connect a GitHub PAT to list repositories.")
            selected_repo = None
        else:
            selected_repo = st.sidebar.selectbox(
                "Select a Repository:", 
                options=repos, 
                index=None, 
                placeholder="Choose a repository..."
            )
    except Exception as e:
        st.sidebar.error(f"Failed to fetch repositories: {e}")
        selected_repo = None

    # --- Main Page: Task Selection and Input ---
    st.markdown("Select a task and provide the details below.")
    task_options = {
        "Implement New Feature ✨": "feature",
        "Debug and Fix an Issue 🐞": "debug",
        "Create or Update a File 📝": "file_write",
        "Read a File's Content 📖": "file_read",
        "Delete a File 🗑️": "file_delete",
    }
    selected_task_label = st.selectbox("Choose a task:", options=task_options.keys())
    selected_task_key = task_options[selected_task_label]

    goal_to_run = None

    with st.form("task_form"):
        # Dynamic UI based on selected task
        if selected_task_key == "feature":
            st.subheader("Feature Description")
            feature_desc = st.text_area("Describe the new feature in detail:", height=150, placeholder="For example: Add a FastAPI endpoint to /users/{user_id} that returns the user's details.")
            if feature_desc and selected_repo:
                goal_to_run = f"""
                You are an expert AI software developer. Your task is to implement a new feature in the repo '{selected_repo}'.
                Feature Description: '{feature_desc}'.

                Follow these steps precisely:
                1. **Create a Branch:** Create a new branch named 'feature/' followed by a short, descriptive name based on the feature description.
                2. **Explore the Code:** Use `list_repository_files` to analyze the existing file structure and decide where to best implement the changes or add new files.
                3. **Implement the Feature:** Use the `create_or_update_file` tool to write the new code. The commit message for this change MUST be a conventional commit message starting with 'feat:', for example: 'feat: Add user detail endpoint'.
                4. **Create a Pull Request:** After committing the new feature, create a pull request to merge the feature branch into the main branch. The PR title and body must clearly describe the new feature.
                5. **Final Answer:** Your final answer must be a confirmation message stating that the pull request has been created, including the PR number and URL. If you fail at any step, provide a clear reason for the failure.
                """

        elif selected_task_key == "debug":
            st.subheader("Issue Details")
            issue_number = st.number_input("Enter the GitHub Issue Number:", min_value=1, step=1)
            user_guidance = st.text_area("Optional: Suggest relevant files or a possible cause for the bug:", height=100, placeholder="e.g., 'I think the issue is in src/logic.py, in the calculate function.'")
            if issue_number and selected_repo:
                goal_to_run = f"""
                You are an expert AI software developer. Your task is to debug and fix issue #{issue_number} in the repo '{selected_repo}'.
                User guidance: '{user_guidance if user_guidance else 'None provided.'}'

                Follow these steps precisely:
                1. **Understand the Bug:** Use the `get_issue_details` tool for issue #{issue_number} to understand the problem.
                2. **Create a Branch:** Create a new branch named exactly 'fix/issue-{issue_number}'.
                3. **Explore the Code:** Use `list_repository_files` to see the repository structure. Based on the issue details and user guidance, use `read_file` to examine the contents of the most relevant file(s).
                4. **Implement the Fix:** Once you have analyzed the code, use the `create_or_update_file` tool to apply the necessary code changes to the relevant file. The commit message for this change MUST be 'fix: Resolve issue #{issue_number}'.
                5. **Create a Pull Request:** After committing the fix, create a pull request to merge the 'fix/issue-{issue_number}' branch into the main branch. The title of the pull request MUST be 'Fix: Resolve issue #{issue_number}'.
                6. **Final Answer:** Your final answer must be a confirmation message stating that the pull request has been created, including the PR number and URL. If you fail at any step, provide a clear reason for the failure.
                """

        elif selected_task_key == "file_write":
            st.subheader("File Details")
            file_path = st.text_input("File path (e.g., 'src/main.py'):")
            file_content = st.text_area("File content:", height=200)
            commit_message = st.text_input("Commit message:", value=f"feat: Create or update {file_path}")
            if file_path and file_content and commit_message and selected_repo:
                goal_to_run = f"In the repository '{selected_repo}', create or update the file at path '{file_path}' with the provided content. Use the commit message: '{commit_message}'."

        elif selected_task_key == "file_read":
            st.subheader("File to Read")
            file_path_read = st.text_input("Enter the full path of the file to read:")
            if file_path_read and selected_repo:
                goal_to_run = f"In the repository '{selected_repo}', read the content of the file at path '{file_path_read}' and present it as your final answer."
        
        elif selected_task_key == "file_delete":
            st.subheader("File to Delete")
            file_path_delete = st.text_input("Enter the full path of the file to delete:")
            commit_msg_delete = st.text_input("Commit message for deletion:", value=f"refactor: Delete {file_path_delete}")
            if file_path_delete and commit_msg_delete and selected_repo:
                goal_to_run = f"In the repository '{selected_repo}', delete the file at path '{file_path_delete}'. Use the commit message: '{commit_msg_delete}'."

        submitted = st.form_submit_button("Run Agent", type="primary", disabled=(not selected_repo))

    if submitted and goal_to_run:
        with st.status("🚀 Agent is working on your task...", expanded=True) as status:
            st.write("Constructing agent prompt...")
            st.code(goal_to_run, language="markdown")
            
            st.write("Running agent... (You can see the detailed logs below)")
            log_container = st.empty()
            log_stream = io.StringIO()
            
            with redirect_stdout(log_stream):
                try:
                    result = agent_executor.invoke({"input": goal_to_run})
                    
                    st.subheader("✅ Agent's Final Response")
                    st.markdown(result.get("output", "No output from agent."))
                    status.update(label="✅ Task Completed!", state="complete", expanded=False)

                except Exception as e:
                    st.error(f"An error occurred while running the agent: {e}")
                    status.update(label="❌ Task Failed!", state="error")
                
                # Always display the logs, whether it succeeded or failed
                logs = log_stream.getvalue()
                log_container.code(logs, language="text")

    elif submitted and not selected_repo:
        st.error("Please select a repository from the sidebar first.")

    st.sidebar.info("You can change the app's theme from the 'Settings' menu (⋮) in the top-right corner.", icon="🎨")

