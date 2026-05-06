from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid
import sys

# Add server directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline import process_document

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

INPUT_DIR = os.path.join(os.path.dirname(__file__), "parser", "input-files")
os.makedirs(INPUT_DIR, exist_ok=True)


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}


@app.post("/api/parse")
async def parse_file(file: UploadFile = File(...)):
    """Parse a document and extract structured data with bounding boxes.

    Accepts PDF files and returns extracted fields with confidence scores,
    document hierarchy with bounding boxes, and file metadata.

    Returns:
        FinalOutput JSON with fields, elements, metadata, and flagged_fields
    """
    file_ext = os.path.splitext(file.filename)[1]
    temp_filename = f"{uuid.uuid4()}{file_ext}"
    temp_path = os.path.join(INPUT_DIR, temp_filename)

    try:
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Process through all 4 layers of the pipeline
        result = await process_document(temp_path)

        # Return as JSON
        return result.model_dump(exclude_none=False)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)