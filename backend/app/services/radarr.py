import httpx
import logging
from typing import Optional, List, Dict, Any
import asyncio
from app.config import get_settings

logger = logging.getLogger(__name__)


class RadarrClient:
    """Radarr API client for movie management."""

    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.radarr_url.rstrip("/")
        self.api_key = self.settings.radarr_api_key
        self.timeout = self.settings.radarr_request_timeout
        self.max_retries = self.settings.radarr_max_retries

    async def get_system_status(self) -> Dict[str, Any]:
        """Get Radarr system status."""
        logger.info("Fetching Radarr system status")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/v3/system/status",
                    headers={"X-Api-Key": self.api_key},
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("Radarr authentication failed - invalid API key")
                raise ValueError("Invalid Radarr API key")
            else:
                logger.error(f"Radarr status check failed: {e}")
                raise
        except Exception as e:
            logger.error(f"Radarr connection error: {e}")
            raise

    async def get_quality_profiles(self) -> List[Dict[str, Any]]:
        """Get available quality profiles."""
        logger.info("Fetching Radarr quality profiles")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/v3/qualityprofile",
                    headers={"X-Api-Key": self.api_key},
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch quality profiles: {e}")
            raise

    async def get_root_folders(self) -> List[Dict[str, Any]]:
        """Get available root folders."""
        logger.info("Fetching Radarr root folders")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/v3/rootfolder",
                    headers={"X-Api-Key": self.api_key},
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch root folders: {e}")
            raise

    async def get_movies(self, skip: int = 0, take: int = 1000) -> List[Dict[str, Any]]:
        """Get all movies from Radarr."""
        logger.info(f"Fetching Radarr movies (skip={skip}, take={take})")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/v3/movie",
                    params={"sort_by": "sortTitle", "page": skip // take + 1, "pageSize": take},
                    headers={"X-Api-Key": self.api_key},
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch movies from Radarr: {e}")
            raise

    async def get_movie(self, movie_id: int) -> Dict[str, Any]:
        """Get a specific movie from Radarr by Radarr ID."""
        logger.info(f"Fetching Radarr movie {movie_id}")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/v3/movie/{movie_id}",
                    headers={"X-Api-Key": self.api_key},
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.debug(f"Movie {movie_id} not found in Radarr")
                return None
            raise
        except Exception as e:
            logger.error(f"Failed to fetch movie {movie_id}: {e}")
            raise

    async def add_movie(self, movie_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a movie to Radarr."""
        tmdb_id = movie_data.get("tmdbId")
        title = movie_data.get("title")
        logger.info(f"Adding movie to Radarr: {title} (TMDb ID: {tmdb_id})")
        
        retry_count = 0
        while retry_count < self.max_retries:
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/api/v3/movie",
                        json=movie_data,
                        headers={"X-Api-Key": self.api_key},
                    )
                    response.raise_for_status()
                    result = response.json()
                    logger.info(f"Successfully added movie to Radarr: {title}")
                    return result
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 400:
                    # Check if it's a duplicate error
                    error_text = e.response.text
                    if "already exists" in error_text or "duplicate" in error_text.lower():
                        logger.warning(f"Movie {title} already exists in Radarr")
                        return {"error": "duplicate", "message": error_text}
                    else:
                        logger.error(f"Radarr validation error: {error_text}")
                        raise
                elif e.response.status_code == 401:
                    logger.error("Radarr authentication failed")
                    raise ValueError("Invalid Radarr API key")
                else:
                    logger.error(f"Radarr add movie error: {e}")
                    raise
            except Exception as e:
                logger.error(f"Failed to add movie {title}: {e}")
                if retry_count < self.max_retries - 1:
                    await asyncio.sleep(2 ** retry_count)
                    retry_count += 1
                else:
                    raise

    async def search_movies(self, query: str) -> List[Dict[str, Any]]:
        """Search for movies in Radarr by title."""
        logger.info(f"Searching Radarr for: {query}")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/v3/movie/lookup",
                    params={"term": query},
                    headers={"X-Api-Key": self.api_key},
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Radarr search failed: {e}")
            raise

    async def test_connection(self) -> bool:
        """Test the Radarr API connection."""
        try:
            await self.get_system_status()
            return True
        except Exception as e:
            logger.error(f"Radarr connection test failed: {e}")
            return False
