import httpx
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import asyncio
from app.config import get_settings

logger = logging.getLogger(__name__)


class TMDbClient:
    """TMDb API client for collection and movie searches."""

    BASE_URL = "https://api.themoviedb.org/3"
    CACHE_TTL = timedelta(hours=24)

    def __init__(self):
        self.settings = get_settings()
        self.api_key = self.settings.tmdb_api_key
        self.timeout = self.settings.tmdb_request_timeout
        self.max_retries = self.settings.tmdb_max_retries
        self._cache: Dict[str, tuple[Any, datetime]] = {}

    async def search_collections(self, query: str) -> List[Dict[str, Any]]:
        """Search for collections by name."""
        logger.info(f"Searching TMDb collections for: {query}")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.BASE_URL}/search/collection",
                    params={
                        "api_key": self.api_key,
                        "query": query,
                    },
                )
                response.raise_for_status()
                data = response.json()
                return data.get("results", [])
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("TMDb authentication failed - invalid API key")
                raise ValueError("Invalid TMDb API key")
            elif e.response.status_code == 429:
                logger.error("TMDb rate limit exceeded")
                raise RuntimeError("TMDb rate limit exceeded")
            else:
                logger.error(f"TMDb search failed: {e}")
                raise
        except Exception as e:
            logger.error(f"TMDb search error: {e}")
            raise

    async def get_collection(self, collection_id: int) -> Dict[str, Any]:
        """Get collection details and all movies in it."""
        cache_key = f"collection_{collection_id}"
        
        # Check cache
        if cache_key in self._cache:
            cached_data, cached_time = self._cache[cache_key]
            if datetime.utcnow() - cached_time < self.CACHE_TTL:
                logger.debug(f"Returning cached collection {collection_id}")
                return cached_data

        logger.info(f"Fetching TMDb collection {collection_id}")
        
        retry_count = 0
        while retry_count < self.max_retries:
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(
                        f"{self.BASE_URL}/collection/{collection_id}",
                        params={"api_key": self.api_key},
                    )
                    response.raise_for_status()
                    data = response.json()
                    
                    # Cache the result
                    self._cache[cache_key] = (data, datetime.utcnow())
                    return data
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    logger.error("TMDb authentication failed")
                    raise ValueError("Invalid TMDb API key")
                elif e.response.status_code == 404:
                    logger.error(f"Collection {collection_id} not found")
                    raise ValueError(f"Collection {collection_id} not found")
                elif e.response.status_code == 429:
                    logger.warning(f"TMDb rate limit, retrying in {2 ** retry_count}s")
                    await asyncio.sleep(2 ** retry_count)
                    retry_count += 1
                else:
                    logger.error(f"TMDb error: {e}")
                    raise
            except Exception as e:
                logger.error(f"TMDb request error: {e}")
                if retry_count < self.max_retries - 1:
                    await asyncio.sleep(2 ** retry_count)
                    retry_count += 1
                else:
                    raise

        raise RuntimeError(f"Failed to fetch collection after {self.max_retries} retries")

    async def get_movie(self, movie_id: int) -> Dict[str, Any]:
        """Get movie details from TMDb."""
        cache_key = f"movie_{movie_id}"
        
        if cache_key in self._cache:
            cached_data, cached_time = self._cache[cache_key]
            if datetime.utcnow() - cached_time < self.CACHE_TTL:
                return cached_data

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.BASE_URL}/movie/{movie_id}",
                    params={"api_key": self.api_key},
                )
                response.raise_for_status()
                data = response.json()
                self._cache[cache_key] = (data, datetime.utcnow())
                return data
        except Exception as e:
            logger.error(f"Failed to get movie {movie_id}: {e}")
            raise

    def clear_cache(self):
        """Clear the cache."""
        self._cache.clear()
        logger.info("TMDb cache cleared")

    async def test_connection(self) -> bool:
        """Test the TMDb API connection."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.BASE_URL}/collection/1",  # Star Wars collection
                    params={"api_key": self.api_key},
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"TMDb connection test failed: {e}")
            return False
