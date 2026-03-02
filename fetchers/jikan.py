"""
Jikan v4 Fetcher — Anime (MyAnimeList, no API key needed)
"""
import aiohttp
import asyncio
import logging
from typing import Optional, List, Dict
import config as cfg

logger = logging.getLogger(__name__)
_TIMEOUT = aiohttp.ClientTimeout(total=20)


class JikanFetcher:

    async def _get(self, endpoint: str, params: Dict = {}) -> Optional[Dict]:
        url = f"{cfg.JIKAN_BASE_URL}{endpoint}"
        for attempt in range(3):
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.get(url, params=params, timeout=_TIMEOUT) as r:
                        if r.status == 200:
                            return await r.json()
                        if r.status == 429:
                            wait = 3 * (attempt + 1)
                            logger.warning(f"Jikan rate limited, retrying in {wait}s...")
                            await asyncio.sleep(wait)
                            continue
                        if r.status == 503:
                            await asyncio.sleep(3)
                            continue
                        logger.warning(f"Jikan HTTP {r.status}: {endpoint}")
                        return None
            except asyncio.TimeoutError:
                logger.warning(f"Jikan timeout attempt {attempt+1}: {endpoint}")
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Jikan error: {e}")
                return None
        logger.error(f"Jikan failed after 3 attempts: {endpoint}")
        return None

    async def search_anime(self, query: str) -> List[Dict]:
        data = await self._get("/anime", {
            "q": query,
            "limit": cfg.MAX_SEARCH_RESULTS,
            "order_by": "popularity",
            "sort": "asc",
        })
        results = (data or {}).get("data", [])
        if not results:
            logger.info(f"Jikan primary empty, fallback for: {query}")
            data2   = await self._get("/anime", {"q": query, "limit": cfg.MAX_SEARCH_RESULTS})
            results = (data2 or {}).get("data", [])
        if not results:
            logger.warning(f"Jikan: no results for '{query}'")
        return [self._slim(r) for r in results]

    async def get_anime(self, mal_id: int) -> Optional[Dict]:
        data = await self._get(f"/anime/{mal_id}/full")
        if not data:
            return None
        return self._full(data.get("data", {}))

    def _slim(self, r: Dict) -> Dict:
        score = r.get("score") or 0
        return {
            "id":     r.get("mal_id"),
            "title":  r.get("title_english") or r.get("title", "Unknown"),
            "year":   str(r.get("year") or ""),
            "poster": (r.get("images") or {}).get("jpg", {}).get("large_image_url"),
            "rating": round(score * 10),
        }

    def _full(self, r: Dict) -> Dict:
        genres     = ", ".join(g["name"] for g in r.get("genres", []))
        themes     = ", ".join(t["name"] for t in r.get("themes", []))
        all_genres = ", ".join(filter(None, [genres, themes])) or "N/A"
        score      = r.get("score") or 0
        synopsis   = r.get("synopsis", "") or ""
        for tag in ["[Written by MAL Rewrite]", "(Source:", "[Source:"]:
            if tag in synopsis:
                synopsis = synopsis[:synopsis.index(tag)].strip()
        synopsis = synopsis or "No synopsis available."
        return {
            "id":          r.get("mal_id"),
            "title":       r.get("title_english") or r.get("title", "Unknown"),
            "title_jp":    r.get("title_japanese", ""),
            "year":        str(r.get("year") or ""),
            "poster":      (r.get("images") or {}).get("jpg", {}).get("large_image_url"),
            "backdrop":    None,
            "rating":      round(score * 10),
            "imdb_rating": f"{score}/10" if score else "N/A",
            "genres":      all_genres,
            "synopsis":    synopsis,
            "overview":    synopsis,
            "status":      r.get("status", "N/A"),
            "episodes":    r.get("episodes") or "?",
            "type":        r.get("type", "TV"),
            "aired":       (r.get("aired") or {}).get("string", "N/A"),
            "studio":      ", ".join(s["name"] for s in r.get("studios", [])) or "N/A",
            "source":      r.get("source", "N/A"),
            "season":      (r.get("season") or "").capitalize(),
            "category":    "anime",
        }
