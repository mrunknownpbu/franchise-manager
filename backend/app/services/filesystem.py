import os
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
import re
from app.config import get_settings

logger = logging.getLogger(__name__)


class FilesystemAnalyzer:
    """Analyze movie filesystem for existing files."""

    # Regex patterns for extracting IDs from filenames
    TMDB_PATTERN = r"\{tmdb-([0-9]+)\}"
    IMDB_PATTERN = r"\{imdb-(tt[0-9]+)\}"

    def __init__(self):
        self.settings = get_settings()
        self.movie_library_path = Path(self.settings.movie_library_path)

    def scan_library(self) -> List[Dict[str, Any]]:
        """Scan the movie library and return list of found movies."""
        logger.info(f"Scanning movie library: {self.movie_library_path}")
        
        if not self.movie_library_path.exists():
            logger.error(f"Movie library path does not exist: {self.movie_library_path}")
            raise ValueError(f"Movie library path not found: {self.movie_library_path}")

        if not self.movie_library_path.is_dir():
            logger.error(f"Movie library path is not a directory: {self.movie_library_path}")
            raise ValueError(f"Movie library path is not a directory: {self.movie_library_path}")

        movies = []
        try:
            for item in self.movie_library_path.iterdir():
                if not item.is_dir():
                    continue

                movie_info = self._parse_movie_folder(item)
                if movie_info:
                    movies.append(movie_info)

            logger.info(f"Found {len(movies)} movies in library")
            return movies
        except PermissionError:
            logger.error(f"Permission denied accessing {self.movie_library_path}")
            raise ValueError(f"Permission denied accessing movie library")
        except Exception as e:
            logger.error(f"Error scanning library: {e}")
            raise

    def _parse_movie_folder(self, folder_path: Path) -> Optional[Dict[str, Any]]:
        """Parse a movie folder and extract metadata."""
        folder_name = folder_path.name
        
        try:
            # Extract TMDb ID if present
            tmdb_match = re.search(self.TMDB_PATTERN, folder_name)
            tmdb_id = int(tmdb_match.group(1)) if tmdb_match else None

            # Extract IMDb ID if present
            imdb_match = re.search(self.IMDB_PATTERN, folder_name)
            imdb_id = imdb_match.group(1) if imdb_match else None

            # Extract title and year
            title, year = self._extract_title_and_year(folder_name)

            if not title:
                logger.debug(f"Could not parse folder: {folder_name}")
                return None

            return {
                "path": str(folder_path),
                "folder_name": folder_name,
                "title": title,
                "year": year,
                "tmdb_id": tmdb_id,
                "imdb_id": imdb_id,
            }
        except Exception as e:
            logger.debug(f"Error parsing folder {folder_name}: {e}")
            return None

    def _extract_title_and_year(self, folder_name: str) -> tuple[Optional[str], Optional[int]]:
        """Extract title and year from folder name.
        
        Supports formats like:
        - Movie Title (2020)
        - Movie.Title.2020
        - Movie_Title_2020
        """
        # Remove ID patterns first
        cleaned = re.sub(self.TMDB_PATTERN, "", folder_name)
        cleaned = re.sub(self.IMDB_PATTERN, "", cleaned).strip()

        # Pattern: Title (YYYY)
        match = re.match(r"^(.+?)\s*\((\d{4})\)$", cleaned)
        if match:
            return match.group(1).strip(), int(match.group(2))

        # Pattern: Title YYYY (at end)
        match = re.search(r"^(.+?)\s+(\d{4})$", cleaned)
        if match:
            return match.group(1).strip(), int(match.group(2))

        # Pattern with separators: Title.2020 or Title_2020
        match = re.match(r"^(.+)[._\-](\d{4})$", cleaned)
        if match:
            title = match.group(1).replace(".", " ").replace("_", " ").strip()
            return title, int(match.group(2))

        # No year found, just return cleaned title
        title = cleaned.replace(".", " ").replace("_", " ").strip()
        return title if title else None, None

    def file_exists_at_path(self, path: str) -> bool:
        """Check if a file exists at the given path."""
        try:
            return Path(path).exists()
        except Exception as e:
            logger.error(f"Error checking path {path}: {e}")
            return False
