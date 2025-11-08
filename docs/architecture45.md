🧱 What the Evaluation Agent will do after evaluation
1.	Download trained model (.pth) from GCP
2.	Load dataset labels from Supabase metadata or from the validation set
3.	Compute evaluation metrics (accuracy, f1, etc.)
4.	Generate downloadable user bundle (new step)
5.	Upload bundle → GCP (/exports/ folder)
6.	Update Supabase with bundle URL
7.	Return link to MCP chatbot → “Your ready-to-use model is available!”
________________________________________
🧩 Structure of the packaged output
When the Evaluation Agent runs packaging, it creates:
/tmp/export_<project_id>/
├── model.pth
├── labels.json
├── predict.py
└── README.txt
and zips it:
export_<project_id>.zip
Then uploads it to:
gs://automl-datasets-vivek/exports/<project_name>_bundle.zip
________________________________________
⚙️ Example packaging code (to add inside Evaluation Agent)
After evaluation completes successfully:
import json, os, zipfile, shutil
from google.cloud import storage

def create_user_bundle(project_id, project_name, model_path, class_labels):
    export_dir = f"/tmp/export_{project_id}"
    os.makedirs(export_dir, exist_ok=True)

    # 1️⃣ Save labels.json
    labels_path = os.path.join(export_dir, "labels.json")
    with open(labels_path, "w") as f:
        json.dump({i: label for i, label in enumerate(class_labels)}, f, indent=2)

    # 2️⃣ Copy model
    shutil.copy(model_path, os.path.join(export_dir, "model.pth"))

    # 3️⃣ Create predict.py
    predict_code = f"""\
import torch, json, sys
from torchvision import models, transforms
from PIL import Image

with open('labels.json') as f:
    labels = json.load(f)

model = models.efficientnet_b0()
model.classifier[1] = torch.nn.Linear(model.classifier[1].in_features, len(labels))
model.load_state_dict(torch.load('model.pth', map_location='cpu'))
model.eval()

def predict(image_path):
    img = Image.open(image_path)
    tfms = transforms.Compose([transforms.Resize((224,224)), transforms.ToTensor()])
    x = tfms(img).unsqueeze(0)
    with torch.no_grad():
        pred = model(x).argmax(1).item()
    print(f"Prediction: {{labels[str(pred)]}}")

if __name__ == "__main__":
    predict(sys.argv[1])
"""
    with open(os.path.join(export_dir, "predict.py"), "w") as f:
        f.write(predict_code)

    # 4️⃣ Simple README
    readme = """\
Usage:
  python predict.py your_image.jpg
Dependencies:
  pip install torch torchvision pillow
"""
    with open(os.path.join(export_dir, "README.txt"), "w") as f:
        f.write(readme)

    # 5️⃣ Zip it
    zip_path = f"/tmp/{project_name}_bundle.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(export_dir):
            for file in files:
                full = os.path.join(root, file)
                zf.write(full, os.path.relpath(full, export_dir))

    # 6️⃣ Upload to GCP
    storage_client = storage.Client()
    bucket = storage_client.bucket("automl-datasets-vivek")
    blob = bucket.blob(f"exports/{project_name}_bundle.zip")
    blob.upload_from_filename(zip_path)
    return f"gs://automl-datasets-vivek/exports/{project_name}_bundle.zip"
Then call:
bundle_url = create_user_bundle(project_id, project_name, model_path, class_labels)
supabase.table("projects").update({
    "status": "export_ready",
    "metadata": {"bundle_url": bundle_url}
}).eq("id", project_id).execute()
________________________________________
🚀 User-visible flow (end-to-end)
Stage	User sees	Behind the scenes
1. “Train my skin cancer classifier”		Dataset Agent + Training Agent do their jobs
2. “Evaluation completed ✅ Accuracy: 89.3%”		Evaluation Agent runs inference on validation set
3. “📦 Download ready: Model Bundle.zip”
	Evaluation Agent builds & uploads the zip
4. User downloads → python predict.py image.jpg		Fully offline inference

