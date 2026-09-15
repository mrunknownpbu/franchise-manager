import logging
from typing import Optional, Tuple, List
from difflib import SequenceMatcher
import unicodedata
import re
from app.config import get_settings

logger = logging.getLogger(__name__)


class MovieMatcher:
    """Intelligent movie matching engine using multiple identifiers."""

    def __init__(self):
        self.settings = get_settings()
        self.confidence_threshold = self.settings.match_confidence_threshold

    def match_tmdb_to_radarr(self, tmdb_movie: dict, radarr_movies: List[dict]) -> Optional[Tuple[dict, float]]:
        """Find the best match for a TMDb movie in Radarr results.
        
        Returns: (radarr_movie, confidence_score) or None
        """
        if not radarr_movies:
            return None

        best_match = None
        best_score = 0

        tmdb_id = tmdb_movie.get("id")
        tmdb_title = tmdb_movie.get("title", "")
        tmdb_year = self._extract_year(tmdb_movie.get("release_date", ""))
        tmdb_imdb = tmdb_movie.get("imdb_id")

        for radarr_movie in radarr_movies:
            score = self._score_match(tmdb_movie, radarr_movie)
            
            if score > best_score:
                best_score = score
                best_match = radarr_movie

            # Very high confidence matches can return immediately
            if score >= 95:
                return best_match, score

        if best_match and best_score >= self.confidence_threshold:
            return best_match, best_score

        return None

    def match_tmdb_to_filesystem(self, tmdb_movie: dict, filesystem_movies: List[dict]) -> Optional[Tuple[dict, float]]:
        """Find the best match for a TMDb movie in filesystem."""
        if not filesystem_movies:
            return None

        best_match = None
        best_score = 0

        for fs_movie in filesystem_movies:
            score = self._score_filesystem_match(tmdb_movie, fs_movie)
            
            if score > best_score:
                best_score = score
                best_match = fs_movie

            if score >= 95:
                return best_match, score

        if best_match and best_score >= self.confidence_threshold:
            return best_match, best_score

        return None

    def _score_match(self, tmdb_movie: dict, radarr_movie: dict) -> float:
        """Score how well a TMDb movie matches a Radarr movie (0-100)."""
        score = 0

        # TMDb ID exact match (very high confidence)
        if tmdb_movie.get("id") == radarr_movie.get("tmdbId"):
            return 100

        # IMDb ID exact match (very high confidence)
        tmdb_imdb = tmdb_movie.get("imdb_id")
        radarr_imdb = radarr_movie.get("imdbId")
        if tmdb_imdb and radarr_imdb and tmdb_imdb == radarr_imdb:
            return 100

        # Title + year exact match (normalized)
        tmdb_title = self._normalize_string(tmdb_movie.get("title", ""))
        radarr_title = self._normalize_string(radarr_movie.get("title", ""))
        tmdb_year = self._extract_year(tmdb_movie.get("release_date", ""))
        radarr_year = radarr_movie.get("year")

        if tmdb_title and radarr_title:
            if tmdb_title == radarr_title and tmdb_year and radarr_year and tmdb_year == radarr_year:
                return 90

            # Fuzzy title match
            title_similarity = self._string_similarity(tmdb_title, radarr_title)
            
            # Boost score if years match
            year_match_boost = 0
            if tmdb_year and radarr_year and tmdb_year == radarr_year:
                year_match_boost = 15

            score = (title_similarity * 0.8) + year_match_boost

        return score

    def _score_filesystem_match(self, tmdb_movie: dict, fs_movie: dict) -> float:
        """Score how well a TMDb movie matches a filesystem movie."""
        score = 0

        # TMDb ID in filename (very high confidence)
        if fs_movie.get("tmdb_id") and fs_movie.get("tmdb_id") == tmdb_movie.get("id"):
            return 100

        # IMDb ID in filename (very high confidence)
        tmdb_imdb = tmdb_movie.get("imdb_id")
        fs_imdb = fs_movie.get("imdb_id")
        if tmdb_imdb and fs_imdb and tmdb_imdb == fs_imdb:
            return 100

        # Title + year match
        tmdb_title = self._normalize_string(tmdb_movie.get("title", ""))
        fs_title = self._normalize_string(fs_movie.get("title", ""))
        tmdb_year = self._extract_year(tmdb_movie.get("release_date", ""))
        fs_year = fs_movie.get("year")

        if tmdb_title and fs_title:
            if tmdb_title == fs_title and tmdb_year and fs_year and tmdb_year == fs_year:
                return 90

            title_similarity = self._string_similarity(tmdb_title, fs_title)
            
            year_match_boost = 0
            if tmdb_year and fs_year and tmdb_year == fs_year:
                year_match_boost = 15

            score = (title_similarity * 0.8) + year_match_boost

        return score

    def _normalize_string(self, s: str) -> str:
        """Normalize a string for comparison."""
        if not s:
            return ""
        
        # Convert to lowercase
        s = s.lower()
        
        # Remove accents
        s = ''.join(
            c for c in unicodedata.normalize('NFD', s)
            if unicodedata.category(c) != 'Mn'
        )
        
        # Remove special characters but keep spaces
        s = re.sub(r"[^a-z0-9\s]", "", s)
        
        # Replace multiple spaces with single space
        s = re.sub(r"\s+", " ", s)
        
        return s.strip()

    def _string_similarity(self, a: str, b: str) -> float:
        """Calculate similarity between two strings (0-100)."""
        if not a or not b:
            return 0
        
        ratio = SequenceMatcher(None, a, b).ratio()
        return ratio * 100

    def _extract_year(self, date_string: str) -> Optional[int]:
        """Extract year from date string (YYYY-MM-DD format)."""
        if not date_string:
            return None
        
        try:
            return int(date_string.split("-")[0])
        except (ValueError, IndexError):
            return None
