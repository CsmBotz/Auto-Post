"""
TMDb Fetcher — Movies & TV Shows
Auto-enriches with IMDb data when keys are available.
"""
import aiohttp
import logging
from typing import Optional, List, Dict
import config as cfg

logger = logging.getLogger(__name__)


class TMDbFetcher:
    def __init__(self):
        self._imdb = None

    def _imdb_fetcher(self):
        if self._imdb is None:
            from fetchers.imdb import IMDbFetcher
            self._imdb = IMDbFetcher()
        return self._imdb

    async def _get(self, endpoint: str, params: Dict = {}) -> Optional[Dict]:
        p = {"api_key": cfg.TMDB_API_KEY, "language": "en-US", **params}
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(
                    f"{cfg.TMDB_BASE_URL}{endpoint}", params=p,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as r:
                    if r.status == 200:
                        return await r.json()
                    logger.warning(f"TMDb {r.status}: {endpoint}")
        except Exception as e:
            logger.error(f"TMDb error: {e}")
        return None

    # ── Movies ────────────────────────────────────────────────────────────────

    async def search_movies(self, query: str) -> List[Dict]:
        data = await self._get("/search/movie", {"query": query})
        if not data:
            return []
        return [self._slim_movie(r) for r in data.get("results", [])[:cfg.MAX_SEARCH_RESULTS]]

    async def get_movie(self, movie_id: int) -> Optional[Dict]:
        data = await self._get(
            f"/movie/{movie_id}",
            {"append_to_response": "external_ids"},
        )
        if not data:
            return None
        meta = self._full_movie(data)
        imdb_id = data.get("imdb_id") or data.get("external_ids", {}).get("imdb_id", "")
        if imdb_id:
            meta["imdb_id"] = imdb_id
        try:
            meta = await self._imdb_fetcher().enrich(meta)
        except Exception as e:
            logger.warning(f"IMDb enrich failed (non-fatal): {e}")
        return meta

    def _slim_movie(self, r: Dict) -> Dict:
        return {
            "id":     r.get("id"),
            "title":  r.get("title", "Unknown"),
            "year":   (r.get("release_date") or "")[:4],
            "poster": f"{cfg.TMDB_IMAGE_URL}{r['poster_path']}" if r.get("poster_path") else None,
            "rating": round(r.get("vote_average", 0), 1),
        }

    def _full_movie(self, r: Dict) -> Dict:
        genres  = ", ".join(g["name"] for g in r.get("genres", []))
        rt      = r.get("runtime", 0)
        imdb_id = r.get("imdb_id", "")
        return {
            "id":             r.get("id"),
            "title":          r.get("title", "Unknown"),
            "year":           (r.get("release_date") or "")[:4],
            "release_date":   r.get("release_date", "N/A"),
            "poster":         f"{cfg.TMDB_IMAGE_URL}{r['poster_path']}" if r.get("poster_path") else None,
            "backdrop":       f"https://image.tmdb.org/t/p/w1280{r['backdrop_path']}" if r.get("backdrop_path") else None,
            "rating":         round(r.get("vote_average", 0), 1),
            "genres":         genres or "N/A",
            "overview":       r.get("overview", "No synopsis available."),
            "runtime":        f"{rt // 60}h {rt % 60}m" if rt else "N/A",
            "status":         r.get("status", "N/A"),
            "tagline":        r.get("tagline", ""),
            "language":       r.get("original_language", "en").upper(),
            "imdb_id":        imdb_id,
            "imdb_url":       f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else "",
            "imdb_rating":    "N/A",
            "imdb_votes":     "N/A",
            "content_rating": "N/A",
            "box_office":     "N/A",
            "awards":         "N/A",
            "metacritic":     "N/A",
            "category":       "movie",
        }

    # ── TV Shows ──────────────────────────────────────────────────────────────

    async def search_tv(self, query: str) -> List[Dict]:
        data = await self._get("/search/tv", {"query": query})
        if not data:
            return []
        return [self._slim_tv(r) for r in data.get("results", [])[:cfg.MAX_SEARCH_RESULTS]]

    async def get_tv(self, tv_id: int) -> Optional[Dict]:
        data = await self._get(
            f"/tv/{tv_id}",
            {"append_to_response": "external_ids"},
        )
        if not data:
            return None
        meta    = self._full_tv(data)
        imdb_id = data.get("external_ids", {}).get("imdb_id", "")
        if not imdb_id:
            try:
                imdb_id = await self._imdb_fetcher().get_imdb_id_for_tmdb(tv_id, "tv") or ""
            except Exception:
                pass
        if imdb_id:
            meta["imdb_id"] = imdb_id
        try:
            meta = await self._imdb_fetcher().enrich(meta)
        except Exception as e:
            logger.warning(f"IMDb enrich failed (non-fatal): {e}")
        return meta

    def _slim_tv(self, r: Dict) -> Dict:
        return {
            "id":     r.get("id"),
            "title":  r.get("name", "Unknown"),
            "year":   (r.get("first_air_date") or "")[:4],
            "poster": f"{cfg.TMDB_IMAGE_URL}{r['poster_path']}" if r.get("poster_path") else None,
            "rating": round(r.get("vote_average", 0), 1),
        }

    def _full_tv(self, r: Dict) -> Dict:
        genres = ", ".join(g["name"] for g in r.get("genres", []))
        return {
            "id":             r.get("id"),
            "title":          r.get("name", "Unknown"),
            "year":           (r.get("first_air_date") or "")[:4],
            "release_date":   r.get("first_air_date", "N/A"),
            "poster":         f"{cfg.TMDB_IMAGE_URL}{r['poster_path']}" if r.get("poster_path") else None,
            "backdrop":       f"https://image.tmdb.org/t/p/w1280{r['backdrop_path']}" if r.get("backdrop_path") else None,
            "rating":         round(r.get("vote_average", 0), 1),
            "genres":         genres or "N/A",
            "overview":       r.get("overview", "No synopsis available."),
            "status":         r.get("status", "N/A"),
            "seasons":        r.get("number_of_seasons", 0),
            "episodes":       r.get("number_of_episodes", 0),
            "language":       r.get("original_language", "en").upper(),
            "network":        ", ".join(n["name"] for n in r.get("networks", [])) or "N/A",
            "imdb_id":        "",
            "imdb_url":       "",
            "imdb_rating":    "N/A",
            "imdb_votes":     "N/A",
            "content_rating": "N/A",
            "box_office":     "N/A",
            "awards":         "N/A",
            "metacritic":     "N/A",
            "category":       "tvshow",
        }
