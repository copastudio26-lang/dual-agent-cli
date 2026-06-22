OMPT-DRIVEN AUTONOMOUS EXECUTION BLUEPRINT
Quick start

1) Create and activate a virtual environment
   - Linux / macOS:
       python3 -m venv venv
       source venv/bin/activate
   - Windows (PowerShell):
       python -m venv venv
       .\\venv\\Scripts\\Activate.ps1

2) Install dependencies
       pip install -r requirements.txt

   Or run the single CLI command from the spec:
       pip install google-genai streamlit

3) Files included
   - dual_agent_core.py   (core engine: Developer + Auditor + executor)
   - app.py               (Streamlit UI)
   - requirements.txt
   - README.md

4) Run the Streamlit UI
       streamlit run app.py

   The app exposes:
   - a script editor where the Developer persona produces raw Python scripts,
   - an Auditor that returns APPROVED / REJECTED verdicts with reasons,
   - a runner that executes approved scripts with a 30s per-attempt timeout and up to 3 retries (configurable).

5) Test cases
   - Click "Generate Safe Sample Script" then "Run Script" — expect Auditor APPROVED and execution SUCCESS.
   - Click "Introduce Syntax Error" then "Run Script" — expect Auditor REJECTED with SyntaxError displayed.
   - Lower timeout or set retries to 1 and run long-sleep scripts to observe timeout behavior.

Security note: This system executes code on the host. Only run scripts you trust or run inside an isolated test environment / container. The Auditor performs heuristic checks and simple pattern blocking, not a formal sandbox.
