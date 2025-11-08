📦 Dataset Agent — Architecture Document
(Team Member 2 Ownership)
________________________________________
🧭 Overview
The Dataset Agent is responsible for finding, downloading, and registering the dataset required for a project that the Planner Agent has created.
It automates:
1.	Asking the user for Kaggle API authentication (kaggle.json).
2.	Searching Kaggle datasets based on search_keywords.
3.	Selecting the best dataset (with Gemini’s reasoning optional).
4.	Downloading it and uploading to the team’s GCP Storage Bucket.
5.	Updating the datasets table in Supabase.
6.	Updating the projects table → status = 'pending_training'.
This agent runs as an independent micro-service and communicates only through Supabase and the MCP Server.
________________________________________
⚙️ Responsibilities
Task	Description
Kaggle Auth Flow	Request user to upload kaggle.json, parse it, authenticate Kaggle API.
Dataset Discovery	Search for public Kaggle datasets using the keywords from the project plan.
Dataset Ranking (Optional)	Use a simple scoring (download count, size < limit, description match).
Dataset Transfer	Download dataset → upload to GCP Bucket (stream upload).
Metadata Update	Record dataset URL and size in Supabase datasets table.
Project Status Update	Set project status → pending_training.
________________________________________
🧱 Technology Stack
•	Language: Python 3.10+
•	Framework: FastAPI (for agent service)
•	Storage SDK: google-cloud-storage
•	Database SDK: supabase-py
•	External API: Kaggle API (kaggle Python package)
•	Auth Handling: User-uploaded kaggle.json (saved temporarily)
•	Orchestration: MCP Server
•	LLM: Gemini (optional, for dataset ranking)
________________________________________
🗃️ Supabase Tables Used
Table	Action	Purpose
projects	read + update	Read project plan and keywords; update status.
datasets	insert	Record dataset metadata (name, URL, size).
messages	write	Send chatbot instructions (“Please upload Kaggle API file”).
agent_logs	insert	Debug and monitoring logs.
________________________________________
🧩 Workflow
1️⃣ Trigger
•	Watches for projects.status = 'pending_dataset' in Supabase.
•	MCP Server calls POST /agents/dataset/start with project_id.
2️⃣ Check Kaggle Auth
•	Queries Supabase messages for user’s uploaded kaggle.json (handled via chatbot upload endpoint).
•	If not present → posts assistant message:
“Please visit [Kaggle → Account → Create API Token] and upload kaggle.json here.”
3️⃣ Authenticate Kaggle
from kaggle.api.kaggle_api_extended import KaggleApi
api = KaggleApi()
api.authenticate()  # uses uploaded credentials
4️⃣ Dataset Search
datasets = api.dataset_list(search=keywords, sort_by='hottest', file_type='zip')
•	Filter datasets with reasonable size (< max_dataset_size_gb from metadata).
•	Optional: score datasets by downloads, votes, and relevance.
5️⃣ Download & Upload to GCP
api.dataset_download_files(dataset_ref, path="/tmp/data", unzip=False)
upload_to_gcp(bucket_name, "/tmp/data.zip", f"raw/{dataset_ref}.zip")
Upload Function
from google.cloud import storage
def upload_to_gcp(bucket, src, dest):
    client = storage.Client()
    blob = client.bucket(bucket).blob(dest)
    blob.upload_from_filename(src)
    return f"gs://{bucket}/{dest}"
6️⃣ Record in Supabase
supabase.table("datasets").insert({
  "project_id": project_id,
  "name": dataset_name,
  "gcs_url": gcs_path,
  "size": "4.2 GB",
  "source": "kaggle"
}).execute()
7️⃣ Update Project Status
supabase.table("projects").update({
  "status": "pending_training",
  "updated_at": "now()"
}).eq("id", project_id).execute()
8️⃣ Notify User
MCP Server adds assistant message:
“Dataset ✅ uploaded to GCP Bucket. Training Agent can now begin.”
________________________________________
🧮 Environment Variables
SUPABASE_URL=
SUPABASE_KEY=
GCP_BUCKET_NAME=
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service_account.json
MCP_API_KEY=
________________________________________
🧠 API Endpoints (Agent)
Method	Path	Description
POST	/agents/dataset/start	Trigger dataset search and upload by project_id.
GET	/agents/dataset/status/{project_id}	Return progress (logs, dataset URL).
GET	/health	Health check.
________________________________________
🧰 Code Skeleton
from fastapi import FastAPI, HTTPException
from supabase import create_client
from kaggle.api.kaggle_api_extended import KaggleApi
from google.cloud import storage
import os

app = FastAPI()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
bucket = os.getenv("GCP_BUCKET_NAME")

@app.post("/agents/dataset/start")
def start_dataset(job: dict):
    project_id = job["project_id"]
    project = supabase.table("projects").select("*").eq("id", project_id).execute().data[0]
    keywords = project["search_keywords"]

    api = KaggleApi(); api.authenticate()
    dataset = api.dataset_list(search=" ".join(keywords), sort_by="hottest")[0]
    ref = dataset.ref
    api.dataset_download_files(ref, path="/tmp", unzip=False)
    gcs_url = upload_to_gcp(bucket, f"/tmp/{ref}.zip", f"raw/{ref}.zip")

    supabase.table("datasets").insert({
        "project_id": project_id,
        "name": ref,
        "gcs_url": gcs_url,
        "size": f"{dataset.size} GB"
    }).execute()
    supabase.table("projects").update({"status": "pending_training"}).eq("id", project_id).execute()
    return {"success": True, "gcs_url": gcs_url}
________________________________________
🔐 Security Notes
•	Never store the user’s kaggle.json permanently; delete after use.
•	Use service-account with upload-only permissions to GCP bucket.
•	Validate file names to prevent path traversal.
•	Ensure SUPABASE_KEY is service role key restricted to insert/update.
________________________________________
🧩 Integration with MCP Server
1.	Register Dataset Agent as a tool:
2.	tools:
3.	  - name: dataset
4.	    path: ./agents/dataset/main.py
5.	MCP Server triggers /agents/dataset/start when project status = pending_dataset.
6.	Dataset Agent logs status to agent_logs and sends progress messages to chatbot.
________________________________________
🧾 Testing Checklist
Test	Expected Outcome
No kaggle.json available	User prompt sent to upload file
Valid key + keywords	Dataset downloaded and uploaded to GCP
Large dataset > limit	Warning message and confirmation needed
Upload failure	Error logged in agent_logs and status=failed
Success case	New row in datasets table + project status pending_training
________________________________________
✅ Deliverables for Member 2
•	 FastAPI service for dataset search + upload
•	 Kaggle API integration with temporary kaggle.json auth
•	 GCP upload functionality verified
•	 Supabase updates (datasets + projects)
•	 Error handling + logging
•	 Demo: “pending_dataset” → “pending_training” transition

