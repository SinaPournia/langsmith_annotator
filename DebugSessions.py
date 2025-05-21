from langsmith import Client

client = Client()

PROJECT_ID = "7850c373-f1e7-4138-94b9-05253ecee199"
PROJECT_NAME = "langsmtih_stefan"

# Fetch recent runs
runs = list(client.list_runs(project_id=PROJECT_ID, limit=50))

# Print run details
print(f"\n🔎 Found {len(runs)} runs in project '{PROJECT_NAME}':\n")
for run in runs:
    print(f"- Run ID: {run.id}")
    print(f"  Session ID: {run.session_id}")
    print(f"  Run Type: {run.run_type}")
    print(f"  Name: {run.name}")
    print(f"  Start: {run.start_time} | End: {run.end_time}")
    print("-" * 60)
