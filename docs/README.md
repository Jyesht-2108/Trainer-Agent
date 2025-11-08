🧠 AutoML Multi-Agent System (MCP + Supabase + PyTorch + GCP)
📍 Team Size: 4 Members
Each member builds one independent AI Agent.
________________________________________
🚀 Overview
This project is a multi-agent AutoML pipeline built using:
•	MCP Server (for orchestration and chatbot integration)
•	Supabase (for centralized database + message storage)
•	Google Cloud Storage (GCP) (for dataset & model storage)
•	PyTorch (for model training & evaluation)
•	Gemini LLM (for reasoning in Planner Agent)
Each agent handles one stage of the ML workflow — from dataset discovery to final evaluation — and all communication happens through Supabase tables (no direct API calls between agents).
________________________________________
⚙️ System Architecture
User
 ↓
MCP Server (chatbot)
 ├── Planner Agent → creates project plan
 ├── Dataset Agent → fetches & uploads dataset
 ├── Training Agent → trains model locally
 └── Evaluation Agent → evaluates trained model
 ↓
Supabase (Database)
 ↓
GCP Bucket (Storage)
________________________________________
🧩 Agent Responsibilities
Agent	Member	Description
🧠 Planner Agent	Member 1	Interprets user intent (via Gemini), creates project plan in Supabase (projects table).
📦 Dataset Agent	Member 2	Authenticates Kaggle, downloads dataset, uploads to GCP, updates datasets table.
⚙️ Training Agent	Member 3	Downloads dataset from GCP, trains PyTorch model locally, uploads model to GCP, updates models.
📊 Evaluation Agent	Member 4	Evaluates trained model using test data, logs accuracy and metrics, marks project as completed.
________________________________________
🧱 Database Schema (Supabase)
Core Tables
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

create table if not exists datasets (
  id uuid primary key default gen_random_uuid(),
  project_id uuid references projects(id) on delete cascade,
  name text,
  gcs_url text,
  size text,
  source text default 'kaggle',
  created_at timestamptz default now()
);

create table if not exists models (
  id uuid primary key default gen_random_uuid(),
  project_id uuid references projects(id) on delete cascade,
  name text,
  framework text default 'pytorch',
  gcs_url text,
  accuracy numeric,
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz default now()
);

create table if not exists agent_logs (
  id uuid primary key default gen_random_uuid(),
  project_id uuid references projects(id) on delete cascade,
  agent_name text,
  message text,
  log_level text default 'info',
  created_at timestamptz default now()
);
Existing Chat Tables (already in your MCP)
users, messages, embeddings
________________________________________
☁️ GCP Bucket Structure
gs://automl-datasets/
 ├── raw/
 │    ├── plantvillage.zip
 │    ├── chestxray.zip
 ├── models/
 │    ├── plantvillage_model.pth
 └── temp/
      ├── intermediate/
Naming convention:
•	Dataset files: raw/{dataset_name}.zip
•	Models: models/{project_name}_model.pth
________________________________________
⚡ Workflow Summary
Step	Agent	Input	Output	Supabase Status
1️⃣	Planner Agent	User message	JSON project plan	pending_dataset
2️⃣	Dataset Agent	Project ID	GCS dataset URL	pending_training
3️⃣	Training Agent	Dataset URL	GCS model file	pending_evaluation
4️⃣	Evaluation Agent	Model + dataset	Accuracy + metrics	completed
All coordination happens through projects.status.
________________________________________
🧩 MCP Server Integration
Folder Structure
AutoML-MCP-Agents/
 ├── mcp_server/
 │    └── main.py
 ├── agents/
 │    ├── planner/
 │    │    ├── main.py
 │    │    └── architecture.md
 │    ├── dataset/
 │    │    ├── main.py
 │    │    └── architecture.md
 │    ├── training/
 │    │    ├── main.py
 │    │    └── architecture.md
 │    └── evaluation/
 │         ├── main.py
 │         └── architecture.md
 ├── README.md  ← (this file)
 ├── requirements.txt
 └── .env
________________________________________
🧠 MCP Configuration (Example)
In mcp.yaml or config.json:
tools:
  - name: planner
    path: ./agents/planner/main.py
  - name: dataset
    path: ./agents/dataset/main.py
  - name: training
    path: ./agents/training/main.py
  - name: evaluation
    path: ./agents/evaluation/main.py
Each tool registers itself when the MCP Server starts.
________________________________________
🔑 Environment Variables
Create a .env file at root:
SUPABASE_URL=
SUPABASE_KEY=
GCP_BUCKET_NAME=
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service_account.json
GEMINI_API_KEY=
MCP_API_KEY=
LOG_LEVEL=INFO
Each agent reads the same env file (shared configs).
________________________________________
🧰 Local Setup Instructions
1️⃣ Clone the repo
git clone https://github.com/<your-team>/AutoML-MCP-Agents.git
cd AutoML-MCP-Agents
2️⃣ Create a Python environment
python -m venv venv
source venv/bin/activate   # (Linux/Mac)
venv\Scripts\activate      # (Windows)
3️⃣ Install dependencies
pip install -r requirements.txt
4️⃣ Run the MCP server
cd mcp_server
uvicorn main:app --reload
5️⃣ Run an agent (example)
cd ../agents/training
python main.py
Each agent can be run locally or inside a lightweight Docker container.
________________________________________
🧩 How Agents Communicate
All agents are stateless and interact through Supabase:
•	Planner inserts → projects
•	Dataset reads → inserts → updates status
•	Training reads → inserts model → updates status
•	Evaluation reads → updates metrics → finalizes project
________________________________________
🧾 Testing End-to-End
Stage	Input	Expected Outcome
🧠 Planner	“Train a PyTorch model for tomato leaves”	Project appears in Supabase with pending_dataset.
📦 Dataset	Kaggle key uploaded	Dataset uploaded to GCP; status → pending_training.
⚙️ Training	Trigger by MCP	Model trained locally, uploaded to GCP; status → pending_evaluation.
📊 Evaluation	Auto-trigger	Metrics computed, status → completed.
✅ Output		Chatbot shows: “Model accuracy 93.8%. Project complete!”
________________________________________
🧩 Team Member Division
Member	Agent	Key Skills Used
1️⃣	Planner Agent	LLM integration, Supabase schema design
2️⃣	Dataset Agent	Kaggle API, GCP uploads, data management
3️⃣	Training Agent	PyTorch model training, file upload
4️⃣	Evaluation Agent	Model evaluation, metric computation
________________________________________
🔐 Security Guidelines
•	Never store user kaggle.json beyond the session.
•	Restrict Supabase service keys (write-only for agents).
•	Use least-privilege service accounts for GCP uploads.
•	Validate all Supabase input before insert/update.
•	Ensure model training runs locally in isolated environment (no untrusted code).
________________________________________
🧭 Future Enhancements
•	Add Auto Hyperparameter Tuner Agent.
•	Introduce Model Comparison Dashboard (Supabase + Streamlit).
•	Add Docker Compose file for one-click setup.
•	Add RAG Agent later (to remember past model results).
•	Enable optional GPU cloud training via RunPod or Vertex AI.
________________________________________
✅ End-to-End Summary
Layer	Description
Frontend	MCP Chatbot for user interaction
Middleware	MCP Server routes requests to correct agent
Backend	4 independent AI Agents (Planner, Dataset, Training, Evaluation)
Database	Supabase stores metadata, messages, logs
Storage	GCP bucket stores large datasets & trained models
Execution	Local PyTorch for training & evaluation
Output	Metrics + accuracy summary displayed in chat
________________________________________
📸 Example Final Flow
User: "Train a PyTorch model for plant disease detection"
 ↓
Planner Agent → Creates project plan
 ↓
Dataset Agent → Fetches dataset from Kaggle → Uploads to GCP
 ↓
Training Agent → Downloads dataset → Trains model → Uploads .pth to GCP
 ↓
Evaluation Agent → Evaluates model → Updates Supabase
 ↓
Chatbot → "✅ Training complete. Accuracy: 93.8%."

