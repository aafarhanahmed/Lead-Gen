from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests

from .config import PLACES_CACHE_DIR
from .utils import clean_value, slugify, stable_hash

PLACES_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

FIELD_MASKS = {
    # Cheap discovery mode. Useful for counting/building place ID pools.
    "ids-only": ",".join(["places.id", "places.name", "nextPageToken"]),
    # Sales mode. Needed for no-website detection and outreach qualification.
    "enriched": ",".join(
        [
            "places.id",
            "places.displayName",
            "places.formattedAddress",
            "places.websiteUri",
            "places.nationalPhoneNumber",
            "places.internationalPhoneNumber",
            "places.rating",
            "places.userRatingCount",
            "places.googleMapsUri",
            "places.businessStatus",
            "places.primaryType",
            "places.types",
            "nextPageToken",
        ]
    ),
}


class PlacesClient:
    def __init__(
        self,
        api_key: str,
        *,
        cache_dir: str | Path = PLACES_CACHE_DIR,
        use_cache: bool = True,
        force_refresh: bool = False,
        sleep_seconds: float = 1.0,
    ) -> None:
        self.api_key = api_key
        self.cache_dir = Path(cache_dir)
        self.use_cache = use_cache
        self.force_refresh = force_refresh
        self.sleep_seconds = sleep_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def text_search(self, query: str, *, max_results: int, mode: str = "enriched") -> list[dict[str, Any]]:
        if mode not in FIELD_MASKS:
            raise ValueError(f"Unknown Places mode '{mode}'. Use one of: {', '.join(FIELD_MASKS)}")
        query = clean_value(query)
        if not query:
            return []
        max_results = max(1, int(max_results))
        cache_path = self._cache_path(query, max_results, mode)
        if self.use_cache and not self.force_refresh and cache_path.exists():
            with cache_path.open("r", encoding="utf-8") as handle:
                return json.load(handle).get("places", [])

        places: list[dict[str, Any]] = []
        page_token = ""
        while len(places) < max_results:
            remaining = max_results - len(places)
            payload: dict[str, Any] = {
                "textQuery": query,
                "maxResultCount": min(20, max(1, remaining)),
            }
            if page_token:
                payload["pageToken"] = page_token

            response = requests.post(
                PLACES_TEXT_SEARCH_URL,
                headers={
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": self.api_key,
                    "X-Goog-FieldMask": FIELD_MASKS[mode],
                },
                json=payload,
                timeout=25,
            )
            if response.status_code >= 400:
                raise RuntimeError(f"Places API error {response.status_code}: {response.text[:800]}")

            data = response.json()
            batch = data.get("places") or []
            places.extend(batch[:remaining])
            page_token = clean_value(data.get("nextPageToken"))
            if not page_token or not batch:
                break
            time.sleep(max(2.0, self.sleep_seconds))

        if self.use_cache:
            with cache_path.open("w", encoding="utf-8") as handle:
                json.dump({"query": query, "mode": mode, "places": places}, handle, indent=2)
        return places

    def _cache_path(self, query: str, max_results: int, mode: str) -> Path:
        name = f"{slugify(query)}-{mode}-{max_results}-{stable_hash(query + mode + str(max_results))}.json"
        return self.cache_dir / name
