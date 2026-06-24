from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from Tool.llm.config import load_config


DEFAULT_AZURE_EMBEDDING_CONFIG = "config/azure_embedding_3_small_config.json"


@dataclass(slots=True)
class AzureEmbeddingAdapter:
    endpoint: str
    deployment: str
    api_key: str
    api_version: str = "2024-02-01"
    timeout_seconds: int = 120

    @classmethod
    def from_config(cls, config_path: str = DEFAULT_AZURE_EMBEDDING_CONFIG) -> "AzureEmbeddingAdapter":
        config = load_config(config_path)
        return cls(
            endpoint=config.endpoint,
            deployment=str(config.deployment or config.model),
            api_key=config.api_key,
            api_version=str(config.api_version or "2024-02-01"),
        )

    def embed_text(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    def embed_texts(self, texts: list[str], *, batch_size: int = 32) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for start in range(0, len(texts), max(1, batch_size)):
            batch = texts[start : start + max(1, batch_size)]
            embeddings.extend(self._post_embeddings(batch))
        return embeddings

    def _post_embeddings(self, inputs: list[str]) -> list[list[float]]:
        url = f"{self.endpoint.rstrip('/')}/openai/deployments/{self.deployment}/embeddings"
        response = requests.post(
            url,
            json={"input": inputs[0] if len(inputs) == 1 else inputs},
            params={"api-version": self.api_version},
            headers={"Content-Type": "application/json", "api-key": self.api_key},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        items = data.get("data") or []
        if len(items) != len(inputs):
            raise ValueError("Azure embedding response size did not match input size")
        embeddings: list[list[float]] = []
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("Azure embedding response item is not an object")
            embedding = item.get("embedding")
            if not isinstance(embedding, list):
                raise ValueError("Azure embedding response did not include a list embedding")
            embeddings.append([float(value) for value in embedding])
        return embeddings