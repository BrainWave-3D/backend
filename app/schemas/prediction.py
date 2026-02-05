from pydantic import BaseModel


class InputSummary(BaseModel):
    filename: str | None = None
    content_type: str | None = None
    original_shape: list[int] | None = None
    dtype: str | None = None
    time_length: int | None = None


class ModelInfo(BaseModel):
    loaded: bool
    path: str | None = None


class ClassProbability(BaseModel):
    label_id: int
    label: str
    probability: float


class PredictionResult(BaseModel):
    label_id: int
    label: str
    confidence: float
    classes: list[ClassProbability]


class PredictionResponse(BaseModel):
    prediction: PredictionResult
    input: InputSummary
    model: ModelInfo
