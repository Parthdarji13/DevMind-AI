"""
LLM Provider client and abstraction for DevMind AI.
Ref: PRD Section 7, Section 8, Section 9; Step 21, Step 24 of execution guide.
Supports Google Gemini, OpenAI, Groq, and Mock providers with timeout handling,
rate limit detection, zero secret leaks, and grounded response synthesis.
"""
from abc import ABC, abstractmethod
import logging
import os
import re
import time
from typing import Optional
import httpx

from ...core.config import get_settings

logger = logging.getLogger(__name__)


def sanitize_error_text(text: str) -> str:
    """Masks API keys and credential strings from error messages or URLs."""
    if not text:
        return ""
    # Mask Gemini query param key
    s = re.sub(r"(key=)[^&\s]+", r"\1***", text)
    # Mask Bearer token
    s = re.sub(r"(Bearer\s+)[A-Za-z0-9_\-\.]+", r"\1***", s)
    # Mask header key
    s = re.sub(r"(x-goog-api-key['\":\s]+)[A-Za-z0-9_\-\.]+", r"\1***", s)
    return s


class LLMError(Exception):
    """Base exception for LLM provider errors."""
    pass


class LLMConfigurationError(LLMError):
    """Raised when API credentials or required configurations are missing."""
    pass


class LLMTimeoutError(LLMError):
    """Raised when provider call times out."""
    pass


class LLMRateLimitError(LLMError):
    """Raised when external provider returns 429 Too Many Requests."""
    pass


class LLMAPIError(LLMError):
    """Raised when external provider returns an HTTP error or malformed payload."""
    pass


class BaseLLMProvider(ABC):
    """Abstract base class for LLM synthesis providers."""

    @abstractmethod
    def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1500,
        temperature: float = 0.2,
    ) -> str:
        """Generates completion text from system and user prompts."""
        pass

    def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1500,
        temperature: float = 0.2,
    ):
        """Generates streaming tokens. Default implementation yields words from generate_response."""
        full_text = self.generate_response(system_prompt, user_prompt, max_tokens, temperature)
        words = re.findall(r"\S+|\s+", full_text)
        for w in words:
            yield w


class GeminiLLMProvider(BaseLLMProvider):
    """Google Gemini provider (gemini-3-flash-preview / gemini-3.5-flash)."""

    def __init__(self, api_key: str, model_name: str = "gemini-3-flash-preview", timeout: float = 60.0):
        if not api_key or api_key.startswith("your_"):
            raise LLMConfigurationError("GEMINI_API_KEY is not configured or contains placeholder value.")
        self.api_key = api_key
        self.model_name = model_name
        self.timeout = timeout

    def _get_candidate_models(self) -> list[str]:
        candidates = []
        if self.model_name and self.model_name not in (
            "gemini-flash-latest",
            "gemini-flash-lite-latest",
            "gemini-1.5-flash",
            "gemini-2.0-flash",
            "gemini-2.5-flash",
        ):
            candidates.append(self.model_name)
        candidates.extend([
            "gemini-3-flash-preview",
            "gemini-3.5-flash",
            "gemini-3.5-flash-lite",
            "gemini-flash-latest",
            "gemini-flash-lite-latest",
        ])
        models = []
        for m in candidates:
            if m not in models:
                models.append(m)
        return models

    def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1500,
        temperature: float = 0.2,
    ) -> str:
        headers = {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        models_to_try = self._get_candidate_models()
        last_resp = None
        last_error = None

        with httpx.Client(timeout=self.timeout) as client:
            for model in models_to_try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                for attempt in range(2):  # Try current model with 1 retry on 503/429
                    try:
                        resp = client.post(url, headers=headers, json=payload)
                        last_resp = resp
                        if resp.status_code == 200:
                            break
                        elif resp.status_code in (503, 429):
                            # Temporary high demand or rate limit: wait briefly and retry or fallback
                            logger.warning(
                                f"Gemini model {model} returned HTTP {resp.status_code} (attempt {attempt + 1}). Retrying/falling back..."
                            )
                            time.sleep(1.2)
                            continue
                        elif resp.status_code == 404:
                            # Deprecated / unserved model name: try next candidate
                            break
                        elif resp.status_code in (401, 403):
                            raise LLMConfigurationError("Gemini API authentication failed. Verify GEMINI_API_KEY.")
                        else:
                            break
                    except httpx.TimeoutException as e:
                        last_error = e
                        break
                    except Exception as e:
                        last_error = e
                        break

                if last_resp is not None and last_resp.status_code == 200:
                    break

        if last_resp is None:
            if isinstance(last_error, httpx.TimeoutException):
                raise LLMTimeoutError(f"Gemini API request timed out after {self.timeout}s.") from last_error
            raise LLMAPIError(sanitize_error_text(f"Connection error to Gemini API: {str(last_error)}"))

        if last_resp.status_code == 429:
            settings = get_settings()
            if settings.groq_api_key and not settings.groq_api_key.startswith("your_"):
                logger.warning("Gemini API quota exhausted across all models. Seamlessly falling back to Groq provider.")
                groq_p = GroqLLMProvider(api_key=settings.groq_api_key, timeout=self.timeout)
                return groq_p.generate_response(system_prompt, user_prompt, max_tokens, temperature)
            raise LLMRateLimitError("Gemini API rate limit exceeded (HTTP 429). Please retry in a moment.")
        elif last_resp.status_code in (401, 403):
            raise LLMConfigurationError("Gemini API authentication failed. Verify GEMINI_API_KEY.")
        elif last_resp.status_code == 503:
            settings = get_settings()
            if settings.groq_api_key and not settings.groq_api_key.startswith("your_"):
                logger.warning("Gemini API experiencing high demand (HTTP 503). Seamlessly falling back to Groq provider.")
                groq_p = GroqLLMProvider(api_key=settings.groq_api_key, timeout=self.timeout)
                return groq_p.generate_response(system_prompt, user_prompt, max_tokens, temperature)
            raise LLMAPIError("Gemini API is currently experiencing temporary high demand (HTTP 503). Please retry in a few moments.")
        elif last_resp.status_code != 200:
            clean_text = sanitize_error_text(last_resp.text[:200])
            raise LLMAPIError(f"Gemini API returned HTTP {last_resp.status_code}: {clean_text}")

        try:
            data = last_resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return "The model did not return any candidates."
            parts = candidates[0].get("content", {}).get("parts", [])
            return "".join(p.get("text", "") for p in parts)
        except Exception as e:
            raise LLMAPIError(f"Failed to parse Gemini response: {str(e)}") from e

    def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1500,
        temperature: float = 0.2,
    ):
        headers = {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        models_to_try = self._get_candidate_models()
        streamed_any = False

        with httpx.Client(timeout=self.timeout) as client:
            for model in models_to_try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse"
                try:
                    with client.stream("POST", url, headers=headers, json=payload) as response:
                        if response.status_code == 200:
                            import json
                            for line in response.iter_lines():
                                line_str = line.strip()
                                if line_str.startswith("data: "):
                                    data_str = line_str[6:].strip()
                                    try:
                                        data = json.loads(data_str)
                                        candidates = data.get("candidates", [])
                                        if candidates:
                                            parts = candidates[0].get("content", {}).get("parts", [])
                                            for part in parts:
                                                text = part.get("text", "")
                                                if text:
                                                    streamed_any = True
                                                    yield text
                                    except Exception:
                                        pass
                            if streamed_any:
                                break
                        elif response.status_code in (404, 429, 503):
                            logger.warning(
                                f"Gemini streaming {model} returned HTTP {response.status_code}. Trying next candidate..."
                            )
                            continue
                        else:
                            break
                except Exception as e:
                    logger.warning(f"Live Gemini SSE streaming error on {model} ({e}). Trying next candidate...")
                    continue

        if not streamed_any:
            settings = get_settings()
            if settings.groq_api_key and not settings.groq_api_key.startswith("your_"):
                logger.warning("Gemini streaming quota exhausted. Seamlessly streaming via Groq provider.")
                groq_p = GroqLLMProvider(api_key=settings.groq_api_key, timeout=self.timeout)
                for tok in groq_p.generate_stream(system_prompt, user_prompt, max_tokens, temperature):
                    yield tok
                return

            # Fallback to standard generation across all candidate models
            full_text = self.generate_response(system_prompt, user_prompt, max_tokens, temperature)
            words = re.findall(r"\S+|\s+", full_text)
            for w in words:
                yield w



class OpenAILLMProvider(BaseLLMProvider):
    """OpenAI provider (gpt-4o-mini / gpt-4o)."""

    def __init__(self, api_key: str, model_name: str = "gpt-4o-mini", timeout: float = 60.0):
        if not api_key or api_key.startswith("your_"):
            raise LLMConfigurationError("OPENAI_API_KEY is not configured or contains placeholder value.")
        self.api_key = api_key
        self.model_name = model_name
        self.timeout = timeout

    def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1500,
        temperature: float = 0.2,
    ) -> str:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as e:
            raise LLMTimeoutError(f"OpenAI API request timed out after {self.timeout}s.") from e
        except Exception as e:
            raise LLMAPIError(sanitize_error_text(f"Connection error to OpenAI API: {str(e)}")) from e

        if resp.status_code == 429:
            raise LLMRateLimitError("OpenAI API rate limit exceeded (HTTP 429).")
        elif resp.status_code == 401 or resp.status_code == 403:
            raise LLMConfigurationError("OpenAI API authentication failed. Verify OPENAI_API_KEY.")
        elif resp.status_code != 200:
            clean_text = sanitize_error_text(resp.text[:200])
            raise LLMAPIError(f"OpenAI API returned HTTP {resp.status_code}: {clean_text}")

        try:
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            raise LLMAPIError(f"Failed to parse OpenAI response: {str(e)}") from e


class GroqLLMProvider(BaseLLMProvider):
    """Groq provider (openai/gpt-oss-120b / qwen/qwen3.8-27b)."""

    def __init__(self, api_key: str, model_name: str = "openai/gpt-oss-120b", timeout: float = 60.0):
        if not api_key or api_key.startswith("your_"):
            raise LLMConfigurationError("GROQ_API_KEY is not configured or contains placeholder value.")
        self.api_key = api_key
        # Automatically map deprecated or Google model names to active Groq models
        if not model_name or model_name in (
            "llama-3.3-70b-versatile",
            "llama-3.1-70b-versatile",
            "llama3-70b-8192",
            "llama3-8b-8192",
            "mixtral-8x7b-32768",
            "gemini-3-flash-preview",
            "gemini-3.5-flash",
            "gemini-flash-latest",
        ):
            self.model_name = "openai/gpt-oss-120b"
        else:
            self.model_name = model_name
        self.timeout = timeout

    def _get_candidate_models(self) -> list[str]:
        candidates = [self.model_name]
        for fallback in ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]:
            if fallback not in candidates:
                candidates.append(fallback)
        return candidates

    def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1500,
        temperature: float = 0.2,
    ) -> str:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        models_to_try = self._get_candidate_models()
        last_resp = None
        last_error = None

        with httpx.Client(timeout=self.timeout) as client:
            for model in models_to_try:
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                }
                try:
                    resp = client.post(url, headers=headers, json=payload)
                    last_resp = resp
                    if resp.status_code == 200:
                        break
                    elif resp.status_code in (404, 429, 503):
                        logger.warning(f"Groq model {model} returned HTTP {resp.status_code}. Trying next candidate...")
                        continue
                    else:
                        break
                except httpx.TimeoutException as e:
                    last_error = e
                    continue
                except Exception as e:
                    last_error = e
                    continue

        if last_resp is None:
            if isinstance(last_error, httpx.TimeoutException):
                raise LLMTimeoutError(f"Groq API request timed out after {self.timeout}s.") from last_error
            raise LLMAPIError(sanitize_error_text(f"Connection error to Groq API: {str(last_error)}"))

        if last_resp.status_code == 429:
            raise LLMRateLimitError("Groq API rate limit exceeded (HTTP 429).")
        elif last_resp.status_code in (401, 403):
            raise LLMConfigurationError("Groq API authentication failed. Verify GROQ_API_KEY.")
        elif last_resp.status_code != 200:
            clean_text = sanitize_error_text(last_resp.text[:200])
            raise LLMAPIError(f"Groq API returned HTTP {last_resp.status_code}: {clean_text}")

        try:
            data = last_resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            raise LLMAPIError(f"Failed to parse Groq response: {str(e)}") from e

    def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1500,
        temperature: float = 0.2,
    ):
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        models_to_try = self._get_candidate_models()
        streamed_any = False

        with httpx.Client(timeout=self.timeout) as client:
            for model in models_to_try:
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream": True,
                }
                try:
                    with client.stream("POST", url, headers=headers, json=payload) as response:
                        if response.status_code == 200:
                            import json
                            for line in response.iter_lines():
                                line_str = line.strip()
                                if line_str.startswith("data: ") and line_str != "data: [DONE]":
                                    try:
                                        data = json.loads(line_str[6:].strip())
                                        delta = data.get("choices", [{}])[0].get("delta", {})
                                        content = delta.get("content", "")
                                        if content:
                                            streamed_any = True
                                            yield content
                                    except Exception:
                                        pass
                            if streamed_any:
                                break
                        elif response.status_code in (404, 429, 503):
                            logger.warning(
                                f"Groq streaming {model} returned HTTP {response.status_code}. Trying next candidate..."
                            )
                            continue
                        else:
                            break
                except Exception as e:
                    logger.warning(f"Groq SSE streaming error on {model} ({e}). Trying next candidate...")
                    continue

        if not streamed_any:
            full_text = self.generate_response(system_prompt, user_prompt, max_tokens, temperature)
            words = re.findall(r"\S+|\s+", full_text)
            for w in words:
                yield w


class MockLLMProvider(BaseLLMProvider):
    """
    Mock LLM provider for deterministic offline tests and fallback.
    Synthesizes compliant answers referencing evidence chunks with valid citations.
    """

    def __init__(self, canned_response: Optional[str] = None):
        self.canned_response = canned_response

    def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1500,
        temperature: float = 0.2,
    ) -> str:
        if self.canned_response is not None:
            return self.canned_response

        # Check if evidence is missing or explicitly empty
        if "No relevant code chunks were retrieved" in user_prompt or "--- RETRIEVED CODEBASE EVIDENCE ---\n\n" in user_prompt:
            return "The retrieved codebase evidence does not contain sufficient information to answer this question."

        # Extract first chunk file and line info if present
        import re
        from ..retrieval.multilingual import detect_language

        match = re.search(r"File:\s*([^\n\r]+)[\r\n]+Lines:\s*(\d+)-(\d+)", user_prompt)
        if match:
            fpath = match.group(1).strip()
            start = match.group(2).strip()
            end = match.group(3).strip()
            lang = detect_language(user_prompt)

            if lang == "hindi":
                ans = f"दिए गए कोडबेस साक्ष्य के अनुसार, संबंधित घटक [File: {fpath}, Lines: {start}-{end}] में परिभाषित है।"
            elif lang == "hinglish":
                ans = f"Provided codebase evidence ke mutabik, component [File: {fpath}, Lines: {start}-{end}] me defined hai."
            else:
                ans = f"Based on the provided codebase evidence, the requested component is defined in [File: {fpath}, Lines: {start}-{end}]."

            if any(k in user_prompt.lower() for k in ("architecture", "pattern", "sanrachna", "dancha", "design")):
                ans += "\n[Inference] The architecture appears structured with modular component boundaries."
            return ans

        return "The retrieved codebase evidence does not contain information about this query."


def get_llm_provider(provider_choice: Optional[str] = None) -> BaseLLMProvider:
    """Factory creating configured LLM provider."""
    settings = get_settings()
    choice = (provider_choice or settings.llm_provider).lower()

    timeout = getattr(settings, "llm_timeout_seconds", 60.0)
    if choice == "mock":
        return MockLLMProvider()
    elif choice in ("google", "google_genai", "gemini"):
        return GeminiLLMProvider(api_key=settings.gemini_api_key, model_name=settings.llm_model, timeout=timeout)
    elif choice == "openai":
        return OpenAILLMProvider(api_key=settings.openai_api_key, model_name=settings.llm_model, timeout=timeout)
    elif choice == "groq":
        return GroqLLMProvider(api_key=settings.groq_api_key, model_name=settings.llm_model, timeout=timeout)
    else:
        raise LLMConfigurationError(
            f"Unsupported LLM provider: '{choice}'. Supported: 'mock', 'google_genai', 'openai', 'groq'."
        )
