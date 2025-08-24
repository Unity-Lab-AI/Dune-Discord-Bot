import aiohttp
import random
import asyncio
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class APIClient:
    def __init__(self, config):
        self.config = config
        self.session: aiohttp.ClientSession | None = None
        self.retry_attempts = 6
        self.retry_delay = 2

    async def initialize(self) -> None:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def close(self) -> None:
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

    async def _request_json(self, method: str, url: str, **kwargs) -> Dict[str, Any] | str:
        if self.session is None or self.session.closed:
            await self.initialize()
        for attempt in range(self.retry_attempts):
            try:
                async with self.session.request(method, url, **kwargs) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    if resp.status in {429, 500, 502, 503, 504}:
                        delay = self.retry_delay * (2 ** attempt) + random.uniform(0, 0.1)
                        logger.warning(f"Retry {attempt + 1}/{self.retry_attempts} status {resp.status} wait {delay:.2f}s")
                        await asyncio.sleep(delay)
                        continue
                    try:
                        error_text = await resp.text()
                    except Exception:
                        error_text = ""
                    return f"Error: API returned status {resp.status} {error_text}"
            except (aiohttp.ClientConnectionError, asyncio.TimeoutError) as e:
                delay = self.retry_delay * (2 ** attempt) + random.uniform(0, 0.1)
                logger.warning(f"Retry {attempt + 1}/{self.retry_attempts} due to {e} wait {delay:.2f}s")
                await asyncio.sleep(delay)
                continue
            except Exception as e:
                logger.error(f"Unexpected exception {e}")
                return f"Error: Unexpected exception {e}"
        logger.error("API unreachable after retries")
        return "Error: Upstream API unreachable after retries"

    async def fetch_models(self) -> List[Dict[str, str]]:
        result = await self._request_json("GET", self.config.models_url, timeout=15)
        if isinstance(result, list):
            if all(isinstance(m, str) for m in result):
                return [{"name": m.strip()} for m in result]
            if all(isinstance(m, dict) and "name" in m for m in result):
                return [{"name": m["name"].strip(), "description": m.get("description", "")} for m in result]
        # Fallback to the gpt-5-nano model if the models endpoint is unavailable
        return [{"name": "gpt-5-nano", "description": "Default gpt-5 nano model"}]

    async def send_message(self, messages: list, model: str | None):
        if self.session is None or self.session.closed:
            await self.initialize()
        if not model or not isinstance(model, str) or model.strip() == "":
            model = self.config.default_model
        logger.info(f"Using model: {model}")
        payload = {
            "messages": messages,
            "model": model,
            "max_tokens": 1024,
            "stream": False
        }
        # The gpt-5-nano model only supports the default temperature of 0.
        # Including a non-zero temperature value results in an API error.
        # To maintain compatibility with other models that might support
        # temperature tuning, only add the temperature field when the
        # selected model is not gpt-5-nano.
        if model.lower() != "gpt-5-nano":
            payload["temperature"] = 0.7
        try:
            result = await self._request_json("POST", self.config.api_url, json=payload, timeout=aiohttp.ClientTimeout(total=30))
        except asyncio.TimeoutError:
            return "Error: Request timed out"
        if isinstance(result, str):
            return result
        try:
            return result["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            return f"Error: Invalid response format {e}"
