"""
Genuine Reverse-Image Search Module.
Integrates with Google Cloud Vision API (webDetection) and Bing Visual Search API,
filtering candidate matches strictly to public social media domains (X, Instagram, LinkedIn, Facebook).
Treats search results strictly as candidate leads, NEVER as verified identity matches.
"""

import os
import base64
import json
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple, Union
from urllib.parse import urlparse
import requests

ROOT_DIR = Path(__file__).resolve().parent.parent

# Social platforms domain whitelist and CDN mapping
SOCIAL_DOMAIN_MAP = {
    "x.com": "x.com",
    "twitter.com": "x.com",
    "twimg.com": "x.com",
    "instagram.com": "instagram.com",
    "cdninstagram.com": "instagram.com",
    "linkedin.com": "linkedin.com",
    "licdn.com": "linkedin.com",
    "facebook.com": "facebook.com",
    "fbcdn.net": "facebook.com"
}


@dataclass
class SearchCandidate:
    source_platform: str    # e.g., "x.com", "linkedin.com"
    page_url: str           # Web page URL (post or profile)
    image_url: str          # Candidate image URL
    page_title: str         # Page title / entity description
    match_type: str         # "full_match", "partial_match", "page_match", "visually_similar"


class ReverseImageSearch:
    """
    Reverse image search client supporting Google Cloud Vision and Bing Visual Search.
    Filters results to public social media domains.
    """

    def __init__(
        self,
        google_api_key: Optional[str] = None,
        google_creds_path: Optional[str] = None,
        bing_api_key: Optional[str] = None,
        allowed_domains: Optional[Dict[str, str]] = None
    ):
        self.google_api_key = google_api_key or os.getenv("GOOGLE_VISION_API_KEY")
        self.google_creds_path = google_creds_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        self.bing_api_key = bing_api_key or os.getenv("BING_VISUAL_SEARCH_API_KEY")
        self.domain_map = allowed_domains or SOCIAL_DOMAIN_MAP

    def _resolve_creds_file(self) -> Optional[str]:
        if not self.google_creds_path:
            return None
        clean_path = self.google_creds_path.strip('"\'')
        p = Path(clean_path)
        if p.exists():
            return str(p.resolve())
        if (ROOT_DIR / clean_path).exists():
            return str((ROOT_DIR / clean_path).resolve())
        return None

    def has_credentials(self) -> bool:
        """Check if any valid search API credentials are present."""
        return bool(self.google_api_key or self._resolve_creds_file() or self.bing_api_key)

    def _get_domain(self, url: str) -> str:
        """Extract root domain from URL (e.g., 'twitter.com', 'x.com')."""
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            if netloc.startswith("www."):
                netloc = netloc[4:]
            return netloc
        except Exception:
            return ""

    def _is_social_domain(self, url: str) -> Tuple[bool, str]:
        """Check if domain or CDN matches social platforms whitelist."""
        domain = self._get_domain(url)
        for key, platform in self.domain_map.items():
            if domain == key or domain.endswith("." + key):
                return True, platform
        return False, domain

    def search_google_vision(self, image_path: Union[str, Path]) -> List[SearchCandidate]:
        """
        Execute genuine reverse image search using Google Cloud Vision webDetection API.
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found at {image_path}")

        # Read image and convert to base64
        with open(image_path, "rb") as f:
            content = base64.b64encode(f.read()).decode("utf-8")

        endpoint = "https://vision.googleapis.com/v1/images:annotate"
        params = {}
        headers = {"Content-Type": "application/json"}

        creds_file = self._resolve_creds_file()
        if self.google_api_key:
            params["key"] = self.google_api_key
        elif creds_file:
            try:
                from google.oauth2 import service_account
                import google.auth.transport.requests
                creds = service_account.Credentials.from_service_account_file(
                    creds_file,
                    scopes=["https://www.googleapis.com/auth/cloud-platform"]
                )
                auth_req = google.auth.transport.requests.Request()
                creds.refresh(auth_req)
                headers["Authorization"] = f"Bearer {creds.token}"
            except Exception as e:
                print(f"[Warning] Failed to generate OAuth token from service account: {e}")

        payload = {
            "requests": [
                {
                    "image": {"content": content},
                    "features": [{"type": "WEB_DETECTION", "maxResults": 50}]
                }
            ]
        }

        resp = requests.post(endpoint, params=params, headers=headers, json=payload, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"Google Cloud Vision API error ({resp.status_code}): {resp.text}")

        data = resp.json()
        responses = data.get("responses", [])
        if not responses:
            return []

        web_detection = responses[0].get("webDetection", {})
        candidates: List[SearchCandidate] = []
        seen_urls = set()

        # 1. Inspect pages with matching images
        for page in web_detection.get("pagesWithMatchingImages", []):
            page_url = page.get("url", "")
            page_title = page.get("pageTitle", "Web Page")
            is_social, domain = self._is_social_domain(page_url)
            if is_social:
                # Find associated image URLs on this page
                img_list = page.get("fullMatchingImages", []) or page.get("partialMatchingImages", [])
                for img_obj in img_list:
                    img_url = img_obj.get("url")
                    if img_url and img_url not in seen_urls:
                        seen_urls.add(img_url)
                        candidates.append(SearchCandidate(
                            source_platform=domain,
                            page_url=page_url,
                            image_url=img_url,
                            page_title=page_title,
                            match_type="page_match"
                        ))

        # 2. Inspect full matching images
        for img_obj in web_detection.get("fullMatchingImages", []):
            img_url = img_obj.get("url", "")
            is_social, domain = self._is_social_domain(img_url)
            if is_social and img_url not in seen_urls:
                seen_urls.add(img_url)
                candidates.append(SearchCandidate(
                    source_platform=domain,
                    page_url=img_url,
                    image_url=img_url,
                    page_title="Full Visual Match",
                    match_type="full_match"
                ))

        # 3. Inspect partial matching images
        for img_obj in web_detection.get("partialMatchingImages", []):
            img_url = img_obj.get("url", "")
            is_social, domain = self._is_social_domain(img_url)
            if is_social and img_url not in seen_urls:
                seen_urls.add(img_url)
                candidates.append(SearchCandidate(
                    source_platform=domain,
                    page_url=img_url,
                    image_url=img_url,
                    page_title="Partial Visual Match",
                    match_type="partial_match"
                ))

        return candidates

    def search_bing_visual(self, image_path: Union[str, Path]) -> List[SearchCandidate]:
        """
        Execute genuine reverse image search using Bing Visual Search API.
        """
        if not self.bing_api_key:
            raise ValueError("BING_VISUAL_SEARCH_API_KEY is not configured.")

        endpoint = "https://api.bing.microsoft.com/v7.0/images/visualsearch"
        headers = {"Ocp-Apim-Subscription-Key": self.bing_api_key}

        with open(image_path, "rb") as f:
            files = {"image": f}
            resp = requests.post(endpoint, headers=headers, files=files, timeout=30)

        if resp.status_code != 200:
            raise RuntimeError(f"Bing Visual Search API error ({resp.status_code}): {resp.text}")

        data = resp.json()
        candidates: List[SearchCandidate] = []
        seen_urls = set()

        for tag in data.get("tags", []):
            for action in tag.get("actions", []):
                action_type = action.get("actionType", "")
                if action_type in ["PagesIncluding", "VisualSearch"]:
                    for item in action.get("data", {}).get("value", []):
                        page_url = item.get("hostPageUrl", "")
                        img_url = item.get("contentUrl", "") or item.get("thumbnailUrl", "")
                        page_title = item.get("name", "Social Page")

                        is_social, domain = self._is_social_domain(page_url)
                        if is_social and img_url and img_url not in seen_urls:
                            seen_urls.add(img_url)
                            candidates.append(SearchCandidate(
                                source_platform=domain,
                                page_url=page_url,
                                image_url=img_url,
                                page_title=page_title,
                                match_type="bing_" + action_type.lower()
                            ))

        return candidates

    def search(self, image_path: Union[str, Path]) -> List[SearchCandidate]:
        """
        Run genuine reverse image search using available APIs.
        Returns filtered candidate social media posts.
        """
        if self.google_api_key or self.google_creds_path:
            return self.search_google_vision(image_path)
        elif self.bing_api_key:
            return self.search_bing_visual(image_path)
        else:
            return []

