"""
AniList GraphQL Fetcher — Manhwa / Manga (no API key needed)
"""
import re
import aiohttp
import logging
from typing import Optional, List, Dict
import config as cfg

logger = logging.getLogger(__name__)

_SEARCH_GQL = """
query ($search: String, $type: MediaType, $format: MediaFormat) {
  Page(perPage: 5) {
    media(search: $search, type: $type, format: $format, sort: POPULARITY_DESC) {
      id title { romaji english native }
      coverImage { extraLarge }
      averageScore status genres chapters volumes
      startDate { year } format countryOfOrigin
    }
  }
}"""

_DETAIL_GQL = """
query ($id: Int) {
  Media(id: $id, type: MANGA) {
    id title { romaji english native }
    coverImage { extraLarge } bannerImage
    averageScore status genres chapters volumes
    startDate { year month day } endDate { year }
    description(asHtml: false) format countryOfOrigin siteUrl
  }
}"""


class AniListFetcher:
    async def _gql(self, query: str, variables: Dict) -> Optional[Dict]:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    cfg.ANILIST_URL,
                    json={"query": query, "variables": variables},
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=12),
                ) as r:
                    if r.status == 200:
                        return await r.json()
        except Exception as e:
            logger.error(f"AniList error: {e}")
        return None

    async def search_manhwa(self, query: str) -> List[Dict]:
        data = await self._gql(_SEARCH_GQL, {"search": query, "type": "MANGA", "format": "MANHWA"})
        results = (data or {}).get("data", {}).get("Page", {}).get("media", [])
        if not results:
            data = await self._gql(_SEARCH_GQL, {"search": query, "type": "MANGA"})
            results = (data or {}).get("data", {}).get("Page", {}).get("media", [])
        return [self._slim(r) for r in results[:cfg.MAX_SEARCH_RESULTS]]

    async def get_manhwa(self, anilist_id: int) -> Optional[Dict]:
        data = await self._gql(_DETAIL_GQL, {"id": anilist_id})
        media = (data or {}).get("data", {}).get("Media")
        return self._full(media) if media else None

    def _slim(self, r: Dict) -> Dict:
        t = r.get("title", {})
        return {
            "id":     r.get("id"),
            "title":  t.get("english") or t.get("romaji", "Unknown"),
            "year":   str(r.get("startDate", {}).get("year") or ""),
            "poster": (r.get("coverImage") or {}).get("extraLarge"),
            "rating": r.get("averageScore") or 0,
        }

    def _full(self, r: Dict) -> Dict:
        t   = r.get("title", {})
        sd  = r.get("startDate", {})
        ed  = r.get("endDate", {})
        pub = str(sd.get("year", "?")) if sd.get("year") else "N/A"
        if ed.get("year"):
            pub = f"{pub}–{ed['year']}"

        desc = re.sub(r"<[^>]+>", "", r.get("description", "") or "").strip()
        desc = re.sub(r"\n{3,}", "\n\n", desc) or "No synopsis available."

        country_map = {"KR": "MANHWA", "JP": "MANGA", "CN": "MANHUA"}
        media_type  = country_map.get(r.get("countryOfOrigin", "KR"), r.get("format", "MANHWA"))

        return {
            "id":           r.get("id"),
            "title":        t.get("english") or t.get("romaji", "Unknown"),
            "title_native": t.get("native", ""),
            "year":         str(sd.get("year") or ""),
            "poster":       (r.get("coverImage") or {}).get("extraLarge"),
            "backdrop":     r.get("bannerImage"),
            "rating":       r.get("averageScore") or 0,
            "genres":       ", ".join(r.get("genres", [])) or "N/A",
            "synopsis":     desc,
            "status":       (r.get("status") or "").replace("_", " ").title(),
            "chapters":     r.get("chapters") or "Ongoing",
            "volumes":      r.get("volumes") or "N/A",
            "published":    pub,
            "type":         media_type,
            "category":     "manhwa",
        }
