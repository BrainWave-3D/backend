from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.ml.predictor import predict_nifti
from app.schemas.prediction import PredictionResponse

router = APIRouter(prefix="/ml", tags=["ml"])


@router.post("/predict", response_model=PredictionResponse)
async def predict(file: UploadFile = File(...)) -> PredictionResponse:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing filename")

    if not (file.filename.endswith(".nii") or file.filename.endswith(".nii.gz")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expected a .nii or .nii.gz file",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")

    try:
        return await predict_nifti(file_bytes, file.filename, file.content_type)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid NIfTI file",
        ) from exc
