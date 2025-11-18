from fastapi import APIRouter, UploadFile, File

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("/csv")
async def upload_csv(file: UploadFile = File(...)):
    """Endpoint to upload a CSV file containing products."""
    # TODO: Process the uploaded CSV file
    return {"filename": file.filename}
