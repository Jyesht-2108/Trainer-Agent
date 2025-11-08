🧠 Planner Agent — Architecture Document
(Team Member 1 Ownership)
________________________________________
📘 Overview
The Planner Agent is the entry point of the AutoML pipeline.
It listens to the user’s chat messages via the MCP Server, uses the Gemini LLM to interpret intent, and produces a structured project plan that’s stored in Supabase.
Other agents (Dataset → Training → Evaluation) consume this plan by watching Supabase status fields.
________________________________________
⚙️ Core Responsibilities
Task	Description
Intent Parsing	Use Gemini to understand the user’s goal from chat text.
Plan Creation	Build a validated JSON project plan (task_type=image_classification, framework=pytorch).
Persistence	Insert plan into Supabase projects table and set status='pending_dataset'.
User Guidance	Send chat reply via MCP to request Kaggle login/upload (kaggle.json).
Error Handling	Validate Gemini output against schema and log issues to agent_logs.
________________________________________
🧩 System Context
User → MCP Server (chatbot) → Planner Agent
      ↓
   Supabase (projects)
      ↓
   Dataset Agent (polls projects.status='pending_dataset')
________________________________________
🧱 Technology Stack
•	Language: Python 3.10+
•	Framework: FastAPI (for agent service endpoints)
•	LLM: Gemini (API key from MCP env)
•	Database: Supabase (Postgres via supabase-py)
•	Orchestration: MCP Server (tool registration)
•	Validation: Pydantic JSON schemas
•	Logging: JSON structured to stdout + Supabase agent_logs
________________________________________
🧮 Database Integration
Tables Used
Table	Action	Purpose
users	read	Resolve user_id from chat session
messages	read/write	Read recent chat history, write assistant reply
projects	insert/update	Store project plan and status
agent_logs	insert	Debug and audit trail
Projects Schema Reference
create table if not exists projects (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id) on delete cascade,
  name text not null,
  task_type text not null,
  framework text default 'pytorch',
  dataset_source text default 'kaggle',
  search_keywords text[],
  status text default 'draft',
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
________________________________________
🧠 Planner Workflow
Step 1 – Receive User Message
MCP Server forwards:
{
  "user_id": "uuid",
  "session_id": "uuid",
  "message_text": "Train a model to classify tomato leaf diseases"
}
Step 2 – LLM Prompting (Gemini)
Prompt template (enforced JSON schema):
You are a Planner Agent. Convert the following user request into a
structured JSON object conforming to this schema:
{
  "name": string,
  "task_type": "image_classification",
  "framework": "pytorch",
  "dataset_source": "kaggle",
  "search_keywords": [string],
  "preferred_model": string,
  "target_metric": "accuracy",
  "target_value": number,
  "max_dataset_size_gb": number
}
Step 3 – Validate Plan
Use Pydantic model to validate.
If invalid, log error → reply via MCP: “Please rephrase or add dataset details.”
Step 4 – Insert into Supabase
supabase.table("projects").insert({
  "user_id": user_id,
  "name": plan["name"],
  "task_type": plan["task_type"],
  "framework": "pytorch",
  "dataset_source": "kaggle",
  "search_keywords": plan["search_keywords"],
  "status": "pending_dataset",
  "metadata": plan
}).execute()
Step 5 – Acknowledge to User
MCP Server posts assistant message to messages table:
Project created successfully ✅ Please upload your Kaggle API file (kaggle.json) to continue.
________________________________________
🧾 API Endpoints (Agent Service)
Method	Path	Description
POST	/agents/planner/handle_message	Main entrypoint for MCP Server
GET	/agents/planner/project/{id}	Fetch project details
GET	/health	Health check
________________________________________
🧩 Example Output (JSON Plan)
{
  "name": "Tomato Leaf Disease Classifier",
  "task_type": "image_classification",
  "framework": "pytorch",
  "dataset_source": "kaggle",
  "search_keywords": ["tomato leaf disease", "plantvillage"],
  "preferred_model": "resnet18",
  "target_metric": "accuracy",
  "target_value": 0.9,
  "max_dataset_size_gb": 50
}
________________________________________
🧰 Code Skeleton
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ValidationError
import uuid
from supabase import create_client, Client
from gemini_wrapper import GeminiClient  # wrapper in MCP repo

app = FastAPI()
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
gemini = GeminiClient(api_key=os.getenv("GEMINI_API_KEY"))

class PlannerInput(BaseModel):
    user_id: str
    session_id: str
    message_text: str

@app.post("/agents/planner/handle_message")
async def handle_message(payload: PlannerInput):
    prompt = build_prompt(payload.message_text)
    response = gemini.generate(prompt)
    try:
        plan = ProjectPlan.parse_raw(response)
    except ValidationError as e:
        log_error(payload.user_id, str(e))
        raise HTTPException(status_code=400, detail="Invalid LLM output")
    supabase.table("projects").insert({
        "user_id": payload.user_id,
        "name": plan.name,
        "task_type": plan.task_type,
        "framework": plan.framework,
        "dataset_source": plan.dataset_source,
        "search_keywords": plan.search_keywords,
        "status": "pending_dataset",
        "metadata": plan.dict()
    }).execute()
    return {"success": True, "project_id": str(uuid.uuid4())}
________________________________________
🧱 Environment Variables
SUPABASE_URL=
SUPABASE_KEY=
GEMINI_API_KEY=
MCP_API_KEY=
LOG_LEVEL=INFO
________________________________________
🧩 Integration with MCP Server
1.	Add Planner Agent tool entry to MCP config:
2.	tools:
3.	  - name: planner
4.	    path: ./agents/planner/main.py
5.	The chatbot routes user messages to this agent based on intent.
6.	MCP handles Supabase auth and session context for the agent.
________________________________________
🧭 Testing Checklist
Test Case	Expected Result
Valid chat message	Project plan inserted in Supabase, status pending_dataset
Ambiguous message	Planner asks clarifying question
Invalid LLM JSON	Handled with 400 error + logged
Supabase insert fail	Retry once, log error
Integration	Dataset Agent detects new project entry
________________________________________
✅ Deliverables for Member 1
•	 FastAPI service with LLM → Supabase integration
•	 JSON schema validation + error logging
•	 Chat reply insert into Supabase messages
•	 Unit tests for valid/invalid inputs
•	 Dockerfile & README for local run
•	 One demo run: message → project row in Supabase

