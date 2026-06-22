import streamlit as st
import time
import os
from dual_agent_core import developer_generate_script, auditor_check_script, safe_execute_script_from_code, demo_sample_script

st.set_page_config(page_title="Dual-Agent Control Panel", layout="wide")
st.title("OMPT-Driven Dual-Agent Execution Control")

# 1. Initialize session state value for code if not present
if "code_content" not in st.session_state:
    st.session_state["code_content"] = demo_sample_script()

col1, col2 = st.columns([1, 1])

with col1:
    st.header("Developer: Script Editor / Prompts")
    
    row1a, row1b = st.columns(2)
    with row1a:
        if st.button("Generate Safe Sample Script"):
            st.session_state["code_content"] = demo_sample_script()
            st.rerun()
            
    with row1b:
        if st.button("Introduce Syntax Error (for testing)"):
            st.session_state["code_content"] = st.session_state["code_content"] + "\n\nthis is a syntax error"
            st.rerun()

    # 2. Key tracks state cleanly without passing dual arguments
    code_input = st.text_area("Enter Python script (raw):", key="code_content", height=320)
    
    script_name = st.text_input("Script filename:", value="workspace_agent.py")
    st.markdown("Run settings")
    max_retries = st.number_input("Max retries (self-heal)", min_value=1, max_value=10, value=3)
    timeout_s = st.number_input("Per-attempt timeout (seconds)", min_value=1, max_value=300, value=30)
    
    if st.button("Run Script (Audit -> Execute)"):
        # Auditor check
        audit = auditor_check_script(code_input)
        st.session_state["last_audit"] = audit
        
        if audit["status"] != "APPROVED":
            st.error(f"Auditor verdict: {audit['status']}")
            for r in audit.get("reasons", []):
                st.write("- " + r)
        else:
            st.success("Auditor verdict: APPROVED")
            with st.spinner("Executing with self-healing loop..."):
                result = safe_execute_script_from_code(
                    code_str=code_input,
                    name=script_name,
                    out_dir=".",
                    max_retries=int(max_retries),
                    timeout_s=int(timeout_s),
                )
            st.session_state["last_exec"] = result

with col2:
    st.header("Auditor & Execution Logs")
    if "last_audit" in st.session_state:
        audit = st.session_state["last_audit"]
        st.subheader("Last Auditor Verdict")
        if audit["status"] == "APPROVED":
            st.success("APPROVED")
        else:
            st.error("REJECTED")
        if audit.get("reasons"):
            st.write("Reasons:")
            for r in audit["reasons"]:
                st.write("- " + r)
                
    if "last_exec" in st.session_state:
        res = st.session_state["last_exec"]
        st.subheader("Execution Result")
        st.write("Executed:", res.get("executed", False))
        if res.get("executed"):
            st.write("Script path:", res.get("script_path"))
            exec_result = res.get("execution_result", {})
            st.write("Final status:", exec_result.get("final_status"))
            st.markdown("### Attempts")
            for att in exec_result.get("attempts", []):
                st.markdown(f"**Attempt {att['attempt']}** — returncode: {att['returncode']}, timed_out: {att['timed_out']}")
                with st.expander(f"Stdout (Attempt {att['attempt']})"):
                    st.code(att.get("stdout", "") or "<empty>")
                with st.expander(f"Stderr (Attempt {att['attempt']})"):
                    st.code(att.get("stderr", "") or "<empty>")
    else:
        st.info("No execution attempts yet. Use the left panel to generate and run a script.")

st.sidebar.header("Quick actions")
st.sidebar.markdown("Notes:")
st.sidebar.markdown("- Auditor blocks scripts containing obvious dangerous patterns or syntax errors.")
st.sidebar.markdown("- Execution enforces a per-attempt 30s timeout and a configurable retry limit.")
    
