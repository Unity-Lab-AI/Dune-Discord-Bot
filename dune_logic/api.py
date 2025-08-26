import os, random, re, asyncio
from typing import Any, Dict, List, Optional, Sequence
import aiohttp
from cachetools import TTLCache
from .common import PROXY_URL

class ApiClient:
    def __init__(self, *, ttl_seconds: int = 900):
        self._cache: TTLCache[str, Any] = TTLCache(maxsize=2048, ttl=ttl_seconds)
        self._session: Optional[aiohttp.ClientSession] = None
        self._secret = os.getenv("SECRET_TOKEN","").strip()

    async def _ensure(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        return self._session

    def _format(self, path: str) -> str:
        return f"{PROXY_URL}/{path}.json.gz?random={random.random()}"

    async def _fetch(self, path: str) -> Optional[Any]:
        if path in self._cache:
            return self._cache[path]
        url = self._format(path)
        headers = {"X-Secret-Token": self._secret} if self._secret else {}
        s = await self._ensure()
        try:
            async with s.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                self._cache[path] = data
                return data
        except Exception:
            return None

    async def search(self, locale: str, query: Optional[str] = None, types: Optional[Sequence[str]] = None) -> List[Dict[str,Any]]:
        data = await self._fetch(f"{locale}/search") or []
        if types:
            data = [e for e in data if (e.get("path","").split("/",1)[0] in types)]
        if not query:
            return data
        try:
            rx = re.compile(re.escape(query), re.I)
        except Exception:
            return data
        return [e for e in data if e.get("name") and rx.search(e["name"])]

    async def get(self, path: str, locale: str):
        return await self._fetch(f"{locale}/{path}")

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

api = ApiClient()
