from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from app.core.config import settings

_model: Any | None = None
_model_lock = asyncio.Lock()


async def load_model() -> Any:
    global _model
    if _model is not None:
        return _model

    async with _model_lock:
        if _model is not None:
            return _model

        model_path = settings.ml_model_path
        if not model_path:
            return None

        if not Path(model_path).exists():
            return None

        try:
            from tensorflow import keras
        except Exception:
            return None

        _model = keras.models.load_model(model_path)
        return _model
