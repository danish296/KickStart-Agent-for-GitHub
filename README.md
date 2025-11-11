## KickStart - Code Sidekick Agent

Interactive Streamlit app powered by LangChain and Gemini to work with your own GitHub repositories. Each user connects with their own GitHub Personal Access Token (PAT), so actions are performed in the user’s repos under their account.

### Prerequisites
- Python 3.11+ on Windows (the Windows `py` launcher is used in commands)
- A Google Gemini API key
- A GitHub Personal Access Token (PAT) with `repo` scope

### Setup
1. Clone the repository.
2. Create a `.env` file in the project root with:
   - `GEMINI_API_KEY=your_gemini_key`
   - (Optional) `GITHUB_PAT=your_token` if you want a default token; users can still override in the UI.
3. Install dependencies:

```bash
py -m pip install -r requirements.txt
```

### Run the Streamlit UI

```bash
py -m streamlit run app.py --server.port 8501
```

Then open `http://localhost:8501` in your browser.

### Using the App
1. In the left sidebar, paste your GitHub PAT and click “Connect”.
   - The PAT should have `repo` scope to read/write your repositories.
2. After connecting, select one of your repositories from the dropdown.
3. Choose a task (feature, debug, create/update file, read file, delete file), provide inputs, and click “Run Agent”.
4. To switch accounts, click “Disconnect” and connect with a different PAT.

### Security Notes
- Your PAT is entered client-side in the Streamlit session and not written to disk by the app.
- The `.gitignore` prevents committing secrets like `.env` and Streamlit credentials.

### Optional: API Server (OAuth prototype)
There is an experimental FastAPI server in `api.py` showing an OAuth-based flow. The Streamlit app does not require it. If you explore it:
- Set `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` in `.env`.
- Start the API server (example, using uvicorn):

```bash
py -m pip install uvicorn fastapi httpx
py -m uvicorn api:app --reload --port 8000
```

### Troubleshooting
- If `pip` isn’t recognized on Windows, use the Python launcher: `py -m pip ...`.
- If the browser doesn’t open automatically, visit `http://localhost:8501` manually.

### Project Structure
```
KickStart/
  app.py              # Streamlit UI
  api.py              # Optional FastAPI OAuth prototype
  github_tools.py     # GitHub tools with dynamic PAT support
  requirements.txt    # Python dependencies
  .gitignore          # Git/IDE/cache/secrets ignore rules
  README.md           # This guide
```

### MADE BY DANISH AKHTAR(danish296 on github)
Visit Portfolio: https://www.danishakhtar.tech
