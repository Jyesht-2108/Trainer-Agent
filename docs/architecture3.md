⚙️ Training Agent — Architecture Document
(Team Member 3 Ownership)
________________________________________
🧭 Overview
The Training Agent is responsible for:
1.	Downloading datasets from GCP buckets (uploaded by the Dataset Agent).
2.	Training a deep learning model locally using PyTorch.
3.	Saving the trained weights (.pth).
4.	Uploading the final model back to GCP bucket.
5.	Updating the model metadata in Supabase and setting project status → pending_evaluation.
This agent runs locally but is part of the MCP ecosystem — it reads and writes everything through Supabase.
________________________________________
⚙️ Responsibilities
Task	Description
Dataset Retrieval	Read dataset info from Supabase → download from GCP bucket.
Training	Load data, apply augmentations, train CNN (e.g., ResNet18).
Model Upload	Save .pth file locally → upload to GCP bucket.
Metadata Update	Insert row into Supabase models table with metrics.
Status Update	Change projects.status → pending_evaluation.
Logging	Record each step in Supabase agent_logs.
________________________________________
🧱 Technology Stack
•	Language: Python 3.10+
•	Framework: PyTorch + Torchvision
•	Database: Supabase (supabase-py)
•	Storage: Google Cloud Storage (google-cloud-storage)
•	Orchestration: MCP Server
•	Data Handling: ImageFolder / DataLoader
________________________________________
🗃️ Supabase Tables Used
Table	Action	Purpose
projects	read/update	Get task details; mark project progress.
datasets	read	Get dataset URL and info.
models	insert	Store model info, accuracy, and path.
agent_logs	insert	Training progress and errors.
________________________________________
🧩 Workflow
1️⃣ Trigger
•	Triggered automatically when projects.status = 'pending_training'.
•	MCP calls:
•	POST /agents/training/start
•	{
•	  "project_id": "<uuid>"
•	}
________________________________________
2️⃣ Fetch Project & Dataset Metadata
project = supabase.table("projects").select("*").eq("id", project_id).execute().data[0]
dataset = supabase.table("datasets").select("*").eq("project_id", project_id).execute().data[0]
gcs_url = dataset["gcs_url"]
________________________________________
3️⃣ Download Dataset from GCP
from google.cloud import storage

def download_dataset(gcs_url, dest_path="data.zip"):
    client = storage.Client()
    bucket_name, blob_name = parse_gcs_url(gcs_url)
    blob = client.bucket(bucket_name).blob(blob_name)
    blob.download_to_filename(dest_path)
Then unzip and prepare folder:
data/
 ├── train/
 ├── val/
 └── test/
________________________________________
4️⃣ Train Model (PyTorch)
Example training skeleton:
import torch
from torchvision import datasets, transforms, models
from torch import nn, optim

def train_model(data_dir, num_classes, epochs=10):
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor()
    ])
    train_ds = datasets.ImageFolder(root=f"{data_dir}/train", transform=transform)
    train_loader = torch.utils.data.DataLoader(train_ds, batch_size=32, shuffle=True)

    model = models.resnet18(weights="IMAGENET1K_V1")
    model.fc = nn.Linear(model.fc.in_features, num_classes)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    for epoch in range(epochs):
        model.train()
        total_loss = 0
        for imgs, labels in train_loader:
            optimizer.zero_grad()
            outputs = model(imgs)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        print(f"Epoch {epoch+1} | Loss: {total_loss:.3f}")

    torch.save(model.state_dict(), "model.pth")
    return model
________________________________________
5️⃣ Upload Trained Model to GCP
def upload_model_to_gcp(local_file, project_name):
    client = storage.Client()
    bucket = client.bucket(os.getenv("GCP_BUCKET_NAME"))
    dest = f"models/{project_name}_model.pth"
    blob = bucket.blob(dest)
    blob.upload_from_filename(local_file)
    return f"gs://{bucket.name}/{dest}"
________________________________________
6️⃣ Update Supabase
gcs_model_url = upload_model_to_gcp("model.pth", project["name"])

supabase.table("models").insert({
    "project_id": project_id,
    "name": f"{project['name']}_model",
    "framework": "pytorch",
    "gcs_url": gcs_model_url,
    "metadata": {"epochs": 10}
}).execute()

supabase.table("projects").update({
    "status": "pending_evaluation"
}).eq("id", project_id).execute()
________________________________________
7️⃣ Notify User
Send message to chatbot:
“✅ Training complete. Model uploaded to GCP. Evaluation Agent can now begin.”
________________________________________
🧮 Environment Variables
SUPABASE_URL=
SUPABASE_KEY=
GCP_BUCKET_NAME=
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service_account.json
MCP_API_KEY=
LOG_LEVEL=INFO
________________________________________
🧠 API Endpoints (Agent)
Method	Path	Description
POST	/agents/training/start	Start model training for given project_id.
GET	/agents/training/status/{project_id}	View training progress.
GET	/health	Health check.
________________________________________
🧰 Code Skeleton
from fastapi import FastAPI
from supabase import create_client
from google.cloud import storage
import torch, os

app = FastAPI()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

@app.post("/agents/training/start")
def start_training(payload: dict):
    project_id = payload["project_id"]
    project = supabase.table("projects").select("*").eq("id", project_id).execute().data[0]
    dataset = supabase.table("datasets").select("*").eq("project_id", project_id).execute().data[0]

    # 1. Download dataset
    gcs_url = dataset["gcs_url"]
    download_dataset(gcs_url)

    # 2. Train model locally
    model = train_model("data", num_classes=5, epochs=10)

    # 3. Upload model
    gcs_model_url = upload_model_to_gcp("model.pth", project["name"])

    # 4. Update Supabase
    supabase.table("models").insert({
        "project_id": project_id,
        "name": f"{project['name']}_model",
        "framework": "pytorch",
        "gcs_url": gcs_model_url
    }).execute()

    supabase.table("projects").update({"status": "pending_evaluation"}).eq("id", project_id).execute()

    return {"success": True, "model_url": gcs_model_url}
________________________________________
🧩 Integration with MCP Server
1.	Register Training Agent in mcp.yaml:
2.	tools:
3.	  - name: training
4.	    path: ./agents/training/main.py
5.	MCP monitors Supabase:
When projects.status = 'pending_training' → triggers this agent.
6.	Training Agent updates Supabase once done → Evaluation Agent picks up.
________________________________________
🧾 Testing Checklist
Test	Expected Result
Dataset URL valid	Dataset downloaded correctly
Local GPU available	Model trains successfully
Upload successful	Model file appears in GCP bucket
Supabase updated	models entry created, status changed
Invalid project id	Returns 404 error
Storage permission denied	Error logged to agent_logs
________________________________________
✅ Deliverables for Member 3
•	 PyTorch training service with configurable epochs
•	 GCP dataset download + model upload
•	 Supabase metadata updates
•	 Log training info in agent_logs
•	 Demo: project transitions pending_training → pending_evaluation

