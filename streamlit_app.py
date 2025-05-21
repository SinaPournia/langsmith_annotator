import streamlit as st

# Must be the first Streamlit command
st.set_page_config(layout="wide", page_title="LangSmith Session Annotator")
st.session_state.project_id = "7850c373-f1e7-4138-94b9-05253ecee199"
st.session_state.project_name = "langsmtih_stefan"
import os
import streamlit as st

# Set environment variables from Streamlit secrets
os.environ["LANGSMITH_API_KEY"] = st.secrets["LANGSMITH_API_KEY"]
os.environ["LANGCHAIN_TRACING_V2"] = st.secrets.get("LANGCHAIN_TRACING_V2", "true")

import uuid
from langsmith.client import Client
from datetime import datetime, timezone
client = Client()

# --- MockSession class moved to global scope for Streamlit caching compatibility ---
class MockSession:
    def __init__(self, data):
        for k, v in data.items():
            setattr(self, k, v)

# --- LangSmith Client Initialization ---
# try:
#     client = Client()
#     test_projects = list(client.list_projects(limit=3))
#     if not test_projects:
#         st.error("❌ No LangSmith projects found. Please ensure your API key is correct and you have projects in LangSmith.")
#         st.stop()
#     st.session_state.project_id = str(test_projects[1].id)
#     st.session_state.project_name = test_projects[0].name
#     st.success(f"Connected to LangSmith! Using Project: {st.session_state.project_name} (ID: {st.session_state.project_id})")
# except Exception as e:
#     st.error("❌ Failed to connect to LangSmith. Please check your `LANGSMITH_API_KEY` or `secrets.toml`.")
#     st.error(f"Error details: {e}")
#     st.stop()

# --- Global State ---
if 'current_project_id' not in st.session_state:
    st.session_state.current_project_id = None
if 'selected_session' not in st.session_state:
    st.session_state.selected_session = None
if 'all_sessions' not in st.session_state:
    st.session_state.all_sessions = []

SESSION_DISPLAY_LIMIT = 10

def get_timestamp_from_run(run):
    if hasattr(run, 'start_time') and run.start_time:
        return run.start_time
    if hasattr(run, 'created_at') and run.created_at:
        return run.created_at
    if hasattr(run, 'extra') and isinstance(run.extra, dict):
        if run.extra.get('start_time'):
            return run.extra['start_time']
        if run.extra.get('created_at'):
            return run.extra['created_at']
    return datetime.now(timezone.utc)

@st.cache_data(ttl=300)
def get_last_n_sessions(limit: int = 10):
    """
    Return the last N top-level AgentExecutor runs as 'sessions'.
    """
    try:
        runs = list(client.list_runs(
            project_id=st.session_state.project_id,
            execution_order=1,  # Top-level only
            limit=limit * 2
        ))

        sessions = []
        for run in runs:
            if run.run_type == "chain" and "AgentExecutor" in run.name:
                sessions.append({
                    "id": run.id,
                    "name": run.name or f"Session {str(run.id)[:8]}",
                    "created_at": run.start_time or run.created_at,
                    "start_time": run.start_time,
                    "end_time": run.end_time
                })
            if len(sessions) >= limit:
                break

        return [MockSession(s) for s in sessions]

    except Exception as e:
        st.error(f"❌ Failed to fetch sessions: {e}")
        return []


@st.cache_data(ttl=300)
def get_runs_for_id(target_id: str):
    """
    Fetches all child runs of a top-level AgentExecutor run using parent_run_id.
    """
    st.info(f"Fetching child runs for session (AgentExecutor): {target_id}...")
    try:
        return list(client.list_runs(parent_run_id=target_id))
    except Exception as e:
        st.error(f"❌ Error fetching child runs: {e}")
        return []



@st.cache_data(ttl=60)
def get_feedback_for_run(run_id: str):
    try:
        return list(client.list_feedback(run_ids=[run_id]))
    except Exception as e:
        st.error(f"❌ Error fetching feedback for run {run_id}: {e}")
        return []

def create_new_annotation(run_id: str, key: str, value: str):
    st.info(f"Adding annotation to run {run_id} (Key: '{key}', Value: '{value}')...")
    try:
        feedback = client.create_feedback(run_id=run_id, key=key, value=value)
        st.success("✅ Annotation added successfully!")
        st.write(f"Feedback ID: {feedback.id}")
        get_runs_for_id.clear()
        get_feedback_for_run.clear()
        return feedback
    except Exception as e:
        st.error(f"❌ Failed to add annotation. Error: {e}")
        return None

# --- UI ---
st.title("LangSmith Session Annotator")

st.markdown("""
This application allows you to browse your LangSmith project's runs (sessions)
and add custom annotations (feedback) directly from a web UI.
""")

# Sidebar
with st.sidebar:
    st.header("Chat Sessions")

    if st.button("🔄 Refresh"):
        get_last_n_sessions.clear()
        st.session_state.all_sessions = get_last_n_sessions()

    if not st.session_state.all_sessions:
        st.session_state.all_sessions = get_last_n_sessions()

    if st.session_state.all_sessions:
        session_names = [
            f"{s.name} ({str(s.id)[:8]})" for s in st.session_state.all_sessions
        ]
        selected_index = st.selectbox(
            "🧠 Select a recent chat session:",
            options=range(len(session_names)),
            format_func=lambda i: session_names[i],
            key="session_selector"
        )
        st.session_state.selected_session = st.session_state.all_sessions[selected_index]

        s = st.session_state.selected_session
        st.markdown("---")
        st.subheader("Session Info")
        st.write(f"**Name:** {s.name}")
        st.write(f"**ID:** `{s.id}`")
        st.write(f"**Created At:** {s.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    else:
        st.info("No recent chat sessions found.")

    # Display selected session info
    if st.session_state.selected_session:
        s = st.session_state.selected_session
        st.markdown("---")
        st.subheader("Selected Session Info")
        st.write(f"**Name:** {s.name}")
        st.write(f"**ID:** `{s.id}`")
        st.write(f"**Created At:** {s.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")

    st.markdown("### 💡 Recent Sessions")
    for s in st.session_state.all_sessions:
        st.write(f"• `{str(s.id)[:8]}` → **{s.name}**")

# Main content
if st.session_state.selected_session:
    s = st.session_state.selected_session
    st.header(f"Runs in Session: {s.name}")
    st.markdown("---")
    runs = get_runs_for_id(str(s.id))

    if runs:
        st.subheader("Run Details")
        run_dict = {str(r.id): r for r in runs}
        run_options = [f"{i+1}. {r.name} ({r.run_type}) - {str(r.id)[:8]}..." for i, r in enumerate(runs)]

        selected_run_option = st.selectbox("Select a Run:", run_options, key="run_selector")
        selected_run_id_prefix = selected_run_option.split(" - ")[1][:8]

        selected_run = next((r for r in runs if str(r.id).startswith(selected_run_id_prefix)), None)

        if selected_run:
            st.markdown(f"#### Run: {selected_run.name} (ID: `{selected_run.id}`)")
            col1, col2, col3 = st.columns(3)
            col1.write(f"**Type:** {selected_run.run_type}")
            col2.write(f"**Start Time:** {selected_run.start_time.strftime('%H:%M:%S UTC') if selected_run.start_time else 'N/A'}")
            col3.write(f"**End Time:** {selected_run.end_time.strftime('%H:%M:%S UTC') if selected_run.end_time else 'N/A'}")

            if selected_run.inputs:
                user_input = None
                if isinstance(selected_run.inputs, dict):
                    # Check for chat history format
                    if "chat_history" in selected_run.inputs and isinstance(selected_run.inputs["chat_history"], list):
                        for msg in selected_run.inputs["chat_history"]:
                            if msg.get("type") == "human":
                                user_input = msg.get("content")
                                break
                    # Or fallback to a general 'input' key
                    if not user_input and "input" in selected_run.inputs:
                        user_input = selected_run.inputs["input"]

                if user_input:
                    st.markdown("### 🧠 User Input")
                    st.code(user_input, language="markdown")

            if selected_run.outputs:
                final_output = None

                if isinstance(selected_run.outputs, dict):
                    output_wrapper = selected_run.outputs.get("output")
                    if isinstance(output_wrapper, dict):
                        return_values = output_wrapper.get("return_values")
                        if isinstance(return_values, dict):
                            final_output = return_values.get("output")

                if final_output:
                    st.markdown("### 🤖 Assistant's Final Response")
                    st.code(final_output, language="markdown")
                else:
                    st.warning("⚠️ Could not extract the final output.")
                    st.json(selected_run.outputs)



            st.subheader("📝 Existing Annotations")
            feedback_list = get_feedback_for_run(str(selected_run.id))

            if feedback_list:
                for i, fb in enumerate(feedback_list, 1):
                    with st.expander(f"Annotation #{i}"):
                        st.markdown(f"**🔑 Key:** {fb.key}")
                        st.markdown(f"**💬 Value:** {fb.value}")
                        st.markdown(f"**🆔 ID:** `{fb.id}`")
                        st.markdown(f"**📊 Score:** {fb.score if fb.score is not None else '—'}")
                        st.markdown(f"**🗒️ Comment:** {fb.comment if fb.comment else '—'}")
            else:
                st.info("No existing annotations for this run.")
                

            st.subheader("Add New Annotation")
            with st.form("annotation_form"):
                annotation_key = st.text_input("Key (e.g., quality)")
                annotation_value = st.text_input("Value (e.g., good)")
                if st.form_submit_button("Submit"):
                    if annotation_key and annotation_value:
                        create_new_annotation(str(selected_run.id), annotation_key, annotation_value)
                        st.rerun()
                    else:
                        st.warning("Please fill in both key and value.")
