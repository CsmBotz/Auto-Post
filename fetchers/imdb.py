"""
IMDb Enrichment Fetcher
Tries RapidAPI IMDb first, then OMDb as fallback.
Both are optional — if no keys set, TMDb data is used as-is.
"""
import aiohttp
import logging
from typing import Optional, Dict
import config as cfg

logger = logging.getLogger(__name__)

_RAPIDAPI_HOST = "imdb8.p.rapidapi.com"
_OMDB_BASE     = "https://www.omdbapi.com"


class IMDbFetcher:
    def __init__(self):
        self._cache: Dict[str, Dict] = {}

    async def enrich(self, meta: Dict) -> Dict:
        """Enrich TMDb metadata with IMDb data. Never raises."""
        imdb_id = meta.get("imdb_id", "")
        title   = meta.get("title", "")
        year    = meta.get("year", "")

        data = None
        if imdb_id:
            data = await self._by_id(imdb_id)
        if not data and title:
            data = await self._by_title(title, year)
        if not data:
            return meta

        return self._merge(meta, data)

    async def get_imdb_id_for_tmdb(self, tmdb_id: int, media_type: str = "movie") -> Optional[str]:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(
                    f"{cfg.TMDB_BASE_URL}/{media_type}/{tmdb_id}/external_ids",
                    params={"api_key": cfg.TMDB_API_KEY},
                    timeout=aiohttp.ClientTimeout(total=8),
                ) as r:
                    if r.status == 200:
                        return (await r.json()).get("imdb_id")
        except Exception as e:
            logger.debug(f"TMDb external_ids: {e}")
        return None

    # ── RapidAPI ──────────────────────────────────────────────────────────────

    async def _rapidapi(self, endpoint: str, params: Dict) -> Optional[Dict]:
        if not cfg.IMDB_API_KEY:
            return None
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(
                    f"https://{_RAPIDAPI_HOST}{endpoint}",
                    headers={"X-RapidAPI-Key": cfg.IMDB_API_KEY, "X-RapidAPI-Host": _RAPIDAPI_HOST},
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as r:
                    if r.status == 200:
                        return await r.json()
        except Exception as e:
            logger.debug(f"RapidAPI: {e}")
        return None

    async def _rapidapi_by_id(self, imdb_id: str) -> Optional[Dict]:
        data = await self._rapidapi(
            "/title/get-overview-details",
            {"tconst": imdb_id, "currentCountry": "US"},
        )
        if not data:
            return None
        rt  = data.get("ratings", {})
        box = data.get("boxOffice", {})
        return {
            "imdb_id":        imdb_id,
            "imdb_rating":    rt.get("rating"),
            "imdb_votes":     _fmt_votes(rt.get("ratingCount")),
            "imdb_url":       f"https://www.imdb.com/title/{imdb_id}/",
            "content_rating": data.get("certificate", {}).get("certificate", "N/A"),
            "box_office":     _fmt_money(
                box.get("openingWeekendGross", {}).get("amount")
                or box.get("cumulativeWorldwideGross", {}).get("amount")
            ),
            "awards":    _fmt_awards(data.get("awards", {})),
            "metacritic": "N/A",
        }

    async def _rapidapi_search(self, title: str, year: str) -> Optional[Dict]:
        data = await self._rapidapi("/auto-complete", {"q": f"{title} {year}".strip()})
        if not data:
            return None
        for s in data.get("d", [])[:3]:
            if s.get("qid") in ("movie", "tvSeries", "tvMiniSeries"):
                if s.get("id"):
                    return await self._rapidapi_by_id(s["id"])
        return None

    # ── OMDb ──────────────────────────────────────────────────────────────────

    async def _omdb(self, params: Dict) -> Optional[Dict]:
        if not cfg.OMDB_API_KEY:
            return None
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(
                    _OMDB_BASE,
                    params={"apikey": cfg.OMDB_API_KEY, **params},
                    timeout=aiohttp.ClientTimeout(total=8),
                ) as r:
                    if r.status == 200:
                        d = await r.json()
                        if d.get("Response") == "True":
                            return d
        except Exception as e:
            logger.debug(f"OMDb: {e}")
        return None

    def _parse_omdb(self, data: Dict) -> Dict:
        imdb_id = data.get("imdbID", "")
        rating  = data.get("imdbRating")
        meta    = next(
            (r.get("Value", "").replace("/100", "")
             for r in data.get("Ratings", []) if "Metacritic" in r.get("Source", "")),
            "N/A",
        )
        box = data.get("BoxOffice", "")
        return {
            "imdb_id":        imdb_id,
            "imdb_rating":    float(rating) if rating and rating != "N/A" else None,
            "imdb_votes":     data.get("imdbVotes", "N/A").replace(",", ""),
            "imdb_url":       f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else "",
            "content_rating": data.get("Rated", "N/A"),
            "box_office":     _fmt_money(box) if box and box != "N/A" else "N/A",
            "awards":         data.get("Awards", "N/A"),
            "metacritic":     meta,
        }

    # ── Unified ───────────────────────────────────────────────────────────────

    async def _by_id(self, imdb_id: str) -> Optional[Dict]:
        if imdb_id in self._cache:
            return self._cache[imdb_id]
        result = await self._rapidapi_by_id(imdb_id)
        if not result:
            data = await self._omdb({"i": imdb_id, "plot": "short"})
            result = self._parse_omdb(data) if data else None
        if result:
            self._cache[imdb_id] = result
        return result

    async def _by_title(self, title: str, year: str) -> Optional[Dict]:
        result = await self._rapidapi_search(title, year)
        if not result:
            params = {"t": title, "plot": "short"}
            if year:
                params["y"] = year
            data = await self._omdb(params)
            result = self._parse_omdb(data) if data else None
        return result

    def _merge(self, meta: Dict, imdb: Dict) -> Dict:
        m = dict(meta)
        ir = imdb.get("imdb_rating")
        if ir:
            m["rating"]     = ir
            m["rating_src"] = "IMDb"
        else:
            m.setdefault("rating_src", "TMDb")
        m["imdb_id"]        = imdb.get("imdb_id") or meta.get("imdb_id", "")
        m["imdb_rating"]    = str(ir) if ir else str(meta.get("rating", "N/A"))
        m["imdb_votes"]     = imdb.get("imdb_votes", "N/A")
        m["imdb_url"]       = imdb.get("imdb_url", "")
        m["content_rating"] = imdb.get("content_rating", "N/A")
        m["box_office"]     = imdb.get("box_office", "N/A")
        m["awards"]         = imdb.get("awards", "N/A")
        m["metacritic"]     = imdb.get("metacritic", "N/A")
        return m


def _fmt_votes(n) -> str:
    try:
        n = int(n)
        if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
        if n >= 1_000:     return f"{n/1_000:.0f}K"
        return str(n)
    except Exception:
        return "N/A"

def _fmt_money(v) -> str:
    if not v: return "N/A"
    try:
        n = int(str(v).replace(",","").replace("$",""))
        if n >= 1_000_000_000: return f"${n/1_000_000_000:.2f}B"
        if n >= 1_000_000:     return f"${n/1_000_000:.1f}M"
        return f"${n:,}"
    except Exception:
        return str(v)

def _fmt_awards(d: Dict) -> str:
    if not isinstance(d, dict): return "N/A"
    hl = d.get("highlight", {}).get("text", "")
    if hl: return hl
    w, n = d.get("wins", 0), d.get("nominations", 0)
    return f"{w} wins, {n} nominations" if (w or n) else "N/A"
