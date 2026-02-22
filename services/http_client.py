import asyncio
import aiohttp
from typing import Optional
from mitmproxy import ctx
from config import HTTPConfig

class HTTPClient:
    _instance: Optional['HTTPClient'] = None
    _lock = asyncio.Lock()
    
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._config = HTTPConfig()
    
    @classmethod
    def get_instance(cls) -> 'HTTPClient':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    async def ensure_session(self) -> None:
        async with self._lock:
            if self._session is None:
                timeout = aiohttp.ClientTimeout(total=self._config.timeout_seconds)
                connector = aiohttp.TCPConnector(ssl=False)
                self._session = aiohttp.ClientSession(timeout=timeout, connector=connector)
    
    async def close(self) -> None:
        async with self._lock:
            if self._session:
                try:
                    await self._session.close()
                except Exception:
                    pass
                finally:
                    self._session = None
    
    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None:
            raise RuntimeError("Session not initialized. Call ensure_session() first.")
        return self._session
