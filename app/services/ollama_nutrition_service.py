import json
import logging
import os
import re
import time
from typing import Any

from google import genai
import requests

from app.core.config import settings


logger = logging.getLogger(__name__)


GEMINI_DAILY_QUOTA_MARKERS = (
    "GenerateRequestsPerDay",
    "PerDay",
    "daily quota",
)
GEMINI_RETRYABLE_MARKERS = (
    "429",
    "503",
    "RESOURCE_EXHAUSTED",
    "UNAVAILABLE",
    "Too Many Requests",
    "high demand",
)
GEMINI_RETRY_DELAY_PATTERN = re.compile(r"['\"]?retryDelay['\"]?\s*:\s*['\"](?P<seconds>\d+(?:\.\d+)?)s['\"]")


class OllamaNutritionService:
    """LLM Service for nutrition that supports switching between Ollama and Gemini
    via LLM_BACKEND in .env (ollama or gemini)
    """
    def __init__(self):
        self.backend = getattr(settings, "LLM_BACKEND", "ollama").lower()
        self.timeout_seconds = settings.OLLAMA_REQUEST_TIMEOUT_SECONDS
        self.model = settings.OLLAMA_MODEL
        self.gemini_max_retries = max(0, settings.GEMINI_MAX_RETRIES)
        self.gemini_retry_base_seconds = max(0.0, settings.GEMINI_RETRY_BASE_SECONDS)
        self.gemini_retry_max_seconds = max(0.0, settings.GEMINI_RETRY_MAX_SECONDS)
        self.gemini_quota_cooldown_seconds = max(0, settings.GEMINI_QUOTA_COOLDOWN_SECONDS)
        self._gemini_unavailable_until = 0.0

        if self.backend == "ollama":
            self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
            self.model = settings.OLLAMA_MODEL
            logger.info(f"🔧 [Nutrition LLM] Using Ollama: {self.model}")
        elif self.backend in ("gemini", "google"):
            self.model = settings.GEMINI_MODEL
            api_key = getattr(settings, "GOOGLE_API_KEY", "") or os.getenv("GOOGLE_API_KEY")
            if api_key:
                self.client = genai.Client(api_key=api_key)
                logger.info(f"🔧 [Nutrition LLM] Using Gemini: {self.model}")
            else:
                logger.warning("⚠️ No GOOGLE_API_KEY found for Gemini backend")
                self.backend = "ollama"  # fallback
                self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
                self.model = settings.OLLAMA_MODEL
        else:
            logger.warning(f"⚠️ Unknown LLM_BACKEND={self.backend}, falling back to ollama")
            self.backend = "ollama"
            self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
            self.model = settings.OLLAMA_MODEL

    def generate_text(self, prompt: str, *, temperature: float = 0.2) -> str:
        """Generate text using either Ollama or Gemini based on backend."""
        started_at = time.perf_counter()

        if self.backend == "ollama":
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": temperature,
                    "num_ctx": 8192,
                },
            }
            endpoint = f"{self.base_url}/api/generate"
            logger.info(
                "Ollama request started | model=%s | timeout=%ss | prompt_chars=%s",
                self.model,
                self.timeout_seconds,
                len(prompt),
            )
            try:
                response = requests.post(
                    endpoint,
                    json=payload,
                    timeout=self.timeout_seconds,
                )
                elapsed = round(time.perf_counter() - started_at, 2)
                logger.info(
                    "Ollama response received | model=%s | status=%s | elapsed=%.2fs",
                    self.model,
                    response.status_code,
                    elapsed,
                )
                response.raise_for_status()
            except requests.Timeout as exc:
                elapsed = round(time.perf_counter() - started_at, 2)
                logger.error(
                    "Ollama request timed out | model=%s | timeout=%ss | elapsed=%.2fs | endpoint=%s",
                    self.model,
                    self.timeout_seconds,
                    elapsed,
                    endpoint,
                )
                raise RuntimeError(
                    f"Ollama request timed out after {self.timeout_seconds}s for model '{self.model}'."
                ) from exc
            except requests.HTTPError as exc:
                elapsed = round(time.perf_counter() - started_at, 2)
                body_excerpt = exc.response.text[:500] if exc.response is not None else ""
                logger.error(
                    "Ollama HTTP error | model=%s | endpoint=%s | elapsed=%.2fs | status=%s | body=%s",
                    self.model,
                    endpoint,
                    elapsed,
                    exc.response.status_code if exc.response is not None else "unknown",
                    body_excerpt,
                )
                raise RuntimeError(
                    f"Ollama HTTP error {exc.response.status_code if exc.response is not None else 'unknown'} "
                    f"for endpoint {endpoint}: {body_excerpt}"
                ) from exc
            except requests.RequestException as exc:
                elapsed = round(time.perf_counter() - started_at, 2)
                logger.error(
                    "Ollama request failed | model=%s | endpoint=%s | elapsed=%.2fs | error=%s",
                    self.model,
                    endpoint,
                    elapsed,
                    exc,
                )
                raise RuntimeError(f"Ollama request failed: {exc}") from exc

            data = response.json()
            raw_response = data.get("response", "").strip()
            logger.info(
                "Ollama request completed | model=%s | elapsed=%.2fs | response_chars=%s",
                self.model,
                round(time.perf_counter() - started_at, 2),
                len(raw_response),
            )
            return raw_response

        elif self.backend in ("gemini", "google"):
            return self._generate_text_with_gemini(prompt, temperature=temperature, started_at=started_at)

        else:
            raise RuntimeError(f"Unsupported backend: {self.backend}")

    def _generate_text_with_gemini(
        self,
        prompt: str,
        *,
        temperature: float,
        started_at: float,
    ) -> str:
        self._raise_if_gemini_in_cooldown()
        last_error: Exception | None = None
        max_attempts = self.gemini_max_retries + 1

        for attempt in range(max_attempts):
            logger.info(
                "Gemini request started | model=%s | temperature=%.2f | prompt_chars=%s | attempt=%s/%s",
                self.model,
                temperature,
                len(prompt),
                attempt + 1,
                max_attempts,
            )
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config={
                        "temperature": temperature,
                        "response_mime_type": "application/json",
                        "max_output_tokens": 8192,
                    },
                )
                elapsed = round(time.perf_counter() - started_at, 2)
                logger.info(
                    "Gemini response received | model=%s | elapsed=%.2fs | attempt=%s/%s",
                    self.model,
                    elapsed,
                    attempt + 1,
                    max_attempts,
                )
                if not response.text:
                    raise ValueError("Gemini returned empty response")
                return response.text.strip()
            except Exception as exc:
                last_error = exc
                error_text = str(exc)
                elapsed = round(time.perf_counter() - started_at, 2)
                retry_delay = self._gemini_retry_delay_seconds(error_text, attempt)
                should_retry = (
                    self._is_gemini_retryable_error(error_text)
                    and attempt < self.gemini_max_retries
                    and retry_delay <= self.gemini_retry_max_seconds
                    and not self._is_gemini_daily_quota_exhausted(error_text)
                )
                if should_retry:
                    logger.warning(
                        "Gemini request retrying | model=%s | elapsed=%.2fs | attempt=%s/%s | retry_in=%.2fs | error=%s",
                        self.model,
                        elapsed,
                        attempt + 1,
                        max_attempts,
                        retry_delay,
                        error_text,
                    )
                    if retry_delay > 0:
                        time.sleep(retry_delay)
                    continue

                if self._is_gemini_daily_quota_exhausted(error_text) or retry_delay > self.gemini_retry_max_seconds:
                    self._start_gemini_cooldown(error_text)
                logger.error(
                    "Gemini request failed | model=%s | elapsed=%.2fs | attempts=%s | error=%s",
                    self.model,
                    elapsed,
                    attempt + 1,
                    error_text,
                )
                raise RuntimeError(f"Gemini request failed: {exc}") from exc

        raise RuntimeError(f"Gemini request failed: {last_error}") from last_error

    def _raise_if_gemini_in_cooldown(self) -> None:
        remaining_seconds = self._gemini_unavailable_until - time.monotonic()
        if remaining_seconds > 0:
            raise RuntimeError(
                f"Gemini temporarily disabled after quota/rate-limit failure; "
                f"retry after {remaining_seconds:.0f}s."
            )

    def _start_gemini_cooldown(self, error_text: str) -> None:
        if self.gemini_quota_cooldown_seconds <= 0:
            return
        self._gemini_unavailable_until = time.monotonic() + self.gemini_quota_cooldown_seconds
        logger.warning(
            "Gemini cooldown enabled | model=%s | cooldown_seconds=%s | reason=%s",
            self.model,
            self.gemini_quota_cooldown_seconds,
            error_text[:300],
        )

    def _gemini_retry_delay_seconds(self, error_text: str, attempt: int) -> float:
        retry_delay_match = GEMINI_RETRY_DELAY_PATTERN.search(error_text)
        if retry_delay_match:
            return float(retry_delay_match.group("seconds"))
        exponential_delay = self.gemini_retry_base_seconds * (2**attempt)
        return min(self.gemini_retry_max_seconds, exponential_delay)

    @staticmethod
    def _is_gemini_retryable_error(error_text: str) -> bool:
        return any(marker in error_text for marker in GEMINI_RETRYABLE_MARKERS)

    @staticmethod
    def _is_gemini_daily_quota_exhausted(error_text: str) -> bool:
        normalized = error_text.lower()
        return any(marker.lower() in normalized for marker in GEMINI_DAILY_QUOTA_MARKERS)

    def parse_json(self, raw_text: str) -> dict[str, Any]:
        text = raw_text.strip()
        if text.startswith("```"):
            lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
            text = "\n".join(lines).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise ValueError(f"{self.backend.upper()} did not return a JSON object.") from None
            snippet = text[start : end + 1]
            try:
                return json.loads(snippet)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON returned by {self.backend.upper()}: {exc}") from exc


ollama_nutrition_service = OllamaNutritionService()
