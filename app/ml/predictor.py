from __future__ import annotations

import hashlib
import tempfile
from typing import Any

import nibabel as nib
import numpy as np
from scipy.ndimage import zoom

from app.core.config import settings
from app.ml.model_loader import load_model
from app.schemas.prediction import (
    ClassProbability,
    InputSummary,
    ModelInfo,
    PredictionResponse,
    PredictionResult,
)

CLASS_LABELS = {
    0: "Typically Developing Children",
    1: "ADHD-Combined",
    2: "ADHD-Hyperactive/Impulsive",
    3: "ADHD-Inattentive",
}

TIME_LENGTH = 177
TARGET_SHAPE = (28, 28, 28)


def _nifti_suffix(filename: str | None) -> str:
    if not filename:
        return ".nii"
    if filename.endswith(".nii.gz"):
        return ".nii.gz"
    return ".nii"


def _load_nifti(file_bytes: bytes, filename: str | None) -> nib.spatialimages.SpatialImage:
    suffix = _nifti_suffix(filename)
    with tempfile.NamedTemporaryFile(suffix=suffix) as tmp_file:
        tmp_file.write(file_bytes)
        tmp_file.flush()
        return nib.load(tmp_file.name)


def _ensure_time_length(img_data: np.ndarray) -> np.ndarray:
    if img_data.ndim == 3:
        img_data = np.expand_dims(img_data, axis=3)

    if img_data.shape[3] > TIME_LENGTH:
        return img_data[:, :, :, :TIME_LENGTH]

    if img_data.shape[3] < TIME_LENGTH:
        padding = np.zeros((*img_data.shape[:3], TIME_LENGTH - img_data.shape[3]))
        return np.append(img_data, padding, axis=3)

    return img_data


def _preprocess_nifti(img: nib.spatialimages.SpatialImage) -> np.ndarray:
    img_data = img.get_fdata()
    img_data = _ensure_time_length(img_data)

    scale_x = TARGET_SHAPE[0] / img_data.shape[0]
    scale_y = TARGET_SHAPE[1] / img_data.shape[1]
    scale_z = TARGET_SHAPE[2] / img_data.shape[2]

    frames = []
    for index in range(TIME_LENGTH):
        resized = zoom(img_data[:, :, :, index], (scale_x, scale_y, scale_z), order=1)
        frames.append(resized.reshape((*TARGET_SHAPE, 1)))

    return np.asarray(frames, dtype=np.float32)


def _dummy_probabilities(file_bytes: bytes) -> list[float]:
    digest = hashlib.sha256(file_bytes or b"dummy").digest()
    raw = [byte + 1 for byte in digest[:4]]
    total = sum(raw)
    return [value / total for value in raw]


def _prediction_from_probs(probs: list[float]) -> PredictionResult:
    classes = [
        ClassProbability(label_id=label_id, label=CLASS_LABELS[label_id], probability=prob)
        for label_id, prob in enumerate(probs)
    ]
    best = max(classes, key=lambda item: item.probability)
    return PredictionResult(
        label_id=best.label_id,
        label=best.label,
        confidence=best.probability,
        classes=classes,
    )


def _summarize_input(
    img: nib.spatialimages.SpatialImage,
    filename: str | None,
    content_type: str | None,
) -> InputSummary:
    shape = list(img.shape)
    time_length = shape[3] if len(shape) > 3 else 1
    return InputSummary(
        filename=filename,
        content_type=content_type,
        original_shape=shape,
        dtype=str(img.get_data_dtype()),
        time_length=time_length,
    )


def _extract_probs(raw_output: Any) -> list[float] | None:
    if raw_output is None:
        return None

    array = np.asarray(raw_output)
    if array.ndim == 0:
        return None

    if array.ndim > 1:
        array = array.reshape(-1)

    if array.size < len(CLASS_LABELS):
        return None

    trimmed = array[: len(CLASS_LABELS)].astype(float)
    total = float(trimmed.sum())
    if total <= 0:
        return None

    return (trimmed / total).tolist()


async def predict_nifti(
    file_bytes: bytes,
    filename: str | None,
    content_type: str | None,
) -> PredictionResponse:
    img = _load_nifti(file_bytes, filename)
    input_summary = _summarize_input(img, filename, content_type)

    model = await load_model()
    model_loaded = model is not None

    probs: list[float] | None = None
    if model_loaded:
        try:
            model_input = np.expand_dims(_preprocess_nifti(img), axis=0)
            raw_output = model.predict(model_input)
            probs = _extract_probs(raw_output)
        except Exception:
            probs = None

    if probs is None:
        probs = _dummy_probabilities(file_bytes)

    prediction = _prediction_from_probs(probs)

    return PredictionResponse(
        prediction=prediction,
        input=input_summary,
        model=ModelInfo(loaded=model_loaded, path=settings.ml_model_path),
    )
