import os
import uuid
from langsmith.client import Client
from datetime import datetime, timezone

# --- Configuration ---
client = Client()
SESSION_DISPLAY_LIMIT = 10

# Store the global project_id once it's fetched
current_project_id = None

def get_timestamp_from_run(run):
    """Safely gets a timestamp from a run object, trying multiple attributes."""
    if hasattr(run, 'start_time') and run.start_time is not None:
        return run.start_time
    if hasattr(run, 'created_at') and run.created_at is not None:
        return run.created_at
    if hasattr(run, 'extra') and isinstance(run.extra, dict):
        if 'start_time' in run.extra and run.extra['start_time'] is not None:
            return run.extra['start_time']
        if 'created_at' in run.extra and run.extra['created_at'] is not None:
            return run.extra['created_at']
    return datetime.now(timezone.utc)

def get_last_n_sessions(limit: int = SESSION_DISPLAY_LIMIT):
    """
    Fetches the latest N sessions by listing runs from the default project
    and grouping them by their session_id.
    """
    global current_project_id # Declare intent to modify global variable
    print(f"Fetching last {limit} sessions...")
    try:
        projects = list(client.list_projects(limit=1))
        if not projects:
            print("❌ No projects found in your LangSmith account.")
            print("   Please ensure you have created at least one project.")
            return []
        
        current_project_id = str(projects[0].id) # Store the project ID
        print(f"Using Project ID: {current_project_id} (Name: {projects[0].name})")

        all_runs = list(client.list_runs(
            project_id=current_project_id, # Filter by project_id here
            limit=limit * 10,
        ))
        
        sessions_map = {}
        for run in all_runs:
            # The 'session_id' for runs in LangSmith typically refers to the
            # ID of the "session" run or the implicit session created by LangChain.
            # It should be different from the project_id.
            if run.session_id and str(run.session_id) != current_project_id:
                session_uuid = str(run.session_id)
                
                if session_uuid not in sessions_map:
                    session_timestamp = get_timestamp_from_run(run)
                    sessions_map[session_uuid] = {
                        "id": uuid.UUID(session_uuid),
                        "name": f"Session {session_uuid[:8]}...",
                        "created_at": session_timestamp,
                        "start_time": getattr(run, 'start_time', None),
                        "end_time": getattr(run, 'end_time', None)
                    }
                
                if getattr(run, 'run_type', None) == 'session' and getattr(run, 'name', None):
                    sessions_map[session_uuid]["name"] = run.name
        
        # If no distinct sessions are found, we might be looking at a project where
        # runs don't explicitly declare sessions, or their session_id is the project_id.
        # In such a case, we can create a "mock session" representing the whole project.
        if not sessions_map and all_runs:
            # Create a "Project Session" if no explicit sessions are found
            print("⚠️ No distinct sessions found, displaying runs directly from the project as a single session.")
            project_start_time = min(get_timestamp_from_run(r) for r in all_runs) if all_runs else datetime.now(timezone.utc)
            sessions_map[current_project_id] = {
                "id": uuid.UUID(current_project_id),
                "name": projects[0].name or "Default Project Session",
                "created_at": project_start_time,
                "start_time": project_start_time,
                "end_time": max(get_timestamp_from_run(r) for r in all_runs) if all_runs else None
            }


        class MockSession:
            """A simple class to mimic LangSmith Session objects for display."""
            def __init__(self, data):
                for k, v in data.items():
                    setattr(self, k, v)
        
        sessions = sorted(list(sessions_map.values()), key=lambda x: x["created_at"], reverse=True)[:limit]
        
        return [MockSession(s) for s in sessions]

    except Exception as e:
        print(f"❌ Error fetching sessions: {e}")
        print("   Please ensure your LangSmith API key is correct and has the necessary permissions.")
        print("   Also confirm that your LangSmith account has active projects and runs.")
        return []

# --- get_runs_for_session ---
# This function's call to list_runs needs to differentiate:
# Is the provided ID a true session_id or the project_id?
def get_runs_for_session(target_id: str):
    """
    Fetches all runs based on a provided ID.
    If the ID matches the current project ID, it fetches runs for the project.
    Otherwise, it fetches runs for the specific session ID.
    """
    print(f"Fetching runs for ID: {target_id}...")
    try:
        if current_project_id and target_id == current_project_id:
            print(f"   (Detected as Project ID, fetching all runs for project {target_id})")
            runs = list(client.list_runs(project_id=target_id))
        else:
            print(f"   (Detected as Session ID, fetching runs for session {target_id})")
            runs = list(client.list_runs(session_id=target_id))
        return runs
    except Exception as e:
        print(f"❌ Error fetching runs for ID {target_id}: {e}")
        print("   This might happen if the ID is invalid or no runs are associated.")
        return []

# --- get_feedback_for_run, create_new_annotation (unchanged) ---

def get_feedback_for_run(run_id: str):
    """Fetches all feedback (annotations) for a given run ID."""
    try:
        feedback_list = list(client.list_feedback(run_ids=[run_id]))
        return feedback_list
    except Exception as e:
        print(f"❌ Error fetching feedback for run {run_id}: {e}")
        return []

def create_new_annotation(run_id: str, key: str, value: str):
    """Creates a new annotation (feedback) for a specific run."""
    print(f"Adding annotation to run {run_id} (Key: '{key}', Value: '{value}')...")
    try:
        feedback = client.create_feedback(
            run_id=run_id,
            key=key,
            value=value
        )
        print("✅ Annotation added successfully!")
        print(f"  Feedback ID: {feedback.id}")
        return feedback
    except Exception as e:
        print(f"❌ Failed to add annotation to run {run_id}. Error: {e}")
        print(f"   Details: {e}")
        return None

# --- Display and User Interface Functions (mostly unchanged, ensuring getattr) ---

def display_session_details(session):
    """
    Displays details of a selected session, its runs, and any existing annotations.
    Allows the user to select a run to annotate.
    """
    print("\n" + "="*50)
    print(f"Session Name: {getattr(session, 'name', 'Unnamed Session')}")
    print(f"Session ID: {getattr(session, 'id', 'N/A')}")
    
    created_at = getattr(session, 'created_at', None)
    start_time = getattr(session, 'start_time', None)
    end_time = getattr(session, 'end_time', None)

    print(f"Created At: {created_at.strftime('%Y-%m-%d %H:%M:%S UTC') if created_at else 'N/A'}")
    print(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S UTC') if start_time else 'N/A'}")
    print(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S UTC') if end_time else 'N/A'}")
    print("="*50)

    # Pass the session's ID (which might be a project ID if no sessions are distinct)
    runs = get_runs_for_session(str(session.id)) 

    if not runs:
        print("No runs found for this session.")
        return

    print("\n--- Runs in this Session ---")
    run_map = {}

    for i, run in enumerate(runs):
        run_map[i+1] = run
        print(f"\n[{i+1}] Run ID: {run.id}")
        print(f"    Type: {getattr(run, 'run_type', 'N/A')}")
        print(f"    Name: {getattr(run, 'name', 'Unnamed Run')}")
        
        run_start_time = getattr(run, 'start_time', None)
        run_end_time = getattr(run, 'end_time', None)
        print(f"    Start Time: {run_start_time.strftime('%H:%M:%S UTC') if run_start_time else 'N/A'}")
        print(f"    End Time: {run_end_time.strftime('%H:%M:%S UTC') if run_end_time else 'N/A'}")

        if getattr(run, 'inputs', None):
            print("    Inputs:")
            if isinstance(run.inputs, dict) and 'messages' in run.inputs:
                for msg in run.inputs['messages']:
                    if isinstance(msg, dict) and 'content' in msg:
                        print(f"      - {msg.get('role', 'System')}: {msg['content']}")
                    else:
                        print(f"      - {msg}")
            else:
                print(f"      {run.inputs}")
        if getattr(run, 'outputs', None):
            print("    Outputs:")
            if isinstance(run.outputs, dict) and 'content' in run.outputs:
                 print(f"      - {run.outputs['content']}")
            else:
                print(f"      {run.outputs}")

        feedback_list = get_feedback_for_run(str(run.id))
        if feedback_list:
            print("    Existing Annotations:")
            for fb in feedback_list:
                print(f"      - Key: '{fb.key}', Value: '{fb.value}' (ID: {fb.id})")
                if fb.score is not None:
                    print(f"        Score: {fb.score}")
                if fb.comment:
                    print(f"        Comment: {fb.comment}")
        else:
            print("    No existing annotations.")

    while True:
        try:
            choice = input("\nEnter the number of a Run to annotate, or 'b' to go back to sessions: ").strip().lower()
            if choice == 'b':
                break

            run_index = int(choice)
            if run_index in run_map:
                selected_run = run_map[run_index]
                print(f"\n--- Annotating Run {run_index} (ID: {selected_run.id}) ---")
                annotation_key = input("Enter annotation key (e.g., 'quality', 'feedback'): ").strip()
                annotation_value = input("Enter annotation value: ").strip()

                if annotation_key and annotation_value:
                    create_new_annotation(str(selected_run.id), annotation_key, annotation_value)
                    input("\nAnnotation submitted. Press Enter to refresh session details...")
                    display_session_details(session) 
                    break
                else:
                    print("🚫 Annotation key and value cannot be empty. Please try again.")
            else:
                print("⚠️ Invalid run number. Please try again.")
        except ValueError:
            print("⚠️ Invalid input. Please enter a number or 'b'.")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")


def main_menu():
    """The main interactive menu loop for the CLI application."""
    while True:
        print("\n" + "="*50)
        print(" LangSmith Session Annotator CLI ")
        print("="*50)
        print("1. View Last 10 Sessions")
        print("2. Exit")
        print("="*50)

        choice = input("Enter your choice (1-2): ").strip()

        if choice == '1':
            sessions = get_last_n_sessions()
            if not sessions:
                print("No sessions found or an error occurred. Please check your API key and network.")
                input("Press Enter to return to main menu...")
                continue

            print("\n--- Latest Sessions ---")
            session_map = {}
            for i, session in enumerate(sessions):
                session_map[i+1] = session
                session_name = getattr(session, 'name', f"Session {str(session.id)[:8]}...")
                created_at = getattr(session, 'created_at', None)
                created_at_str = created_at.strftime('%Y-%m-%d %H:%M:%S UTC') if created_at else 'N/A'
                print(f"[{i+1}] {session_name} (ID: {session.id}) - Created: {created_at_str}")

            while True:
                session_choice = input("\nEnter the number of a session to view its details, or 'm' for main menu: ").strip().lower()
                if session_choice == 'm':
                    break
                try:
                    session_index = int(session_choice)
                    if session_index in session_map:
                        display_session_details(session_map[session_index])
                        continue
                    else:
                        print("⚠️ Invalid session number. Please try again.")
                except ValueError:
                    print("⚠️ Invalid input. Please enter a number or 'm'.")
                except Exception as e:
                    print(f"An unexpected error occurred: {e}")

        elif choice == '2':
            print("Exiting LangSmith Annotator. Goodbye!")
            break
        else:
            print("⚠️ Invalid choice. Please enter 1 or 2.")

if __name__ == "__main__":
    main_menu()