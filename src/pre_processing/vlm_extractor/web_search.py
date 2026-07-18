"""Search, scrape, clean and store Vietnamese news content matching a query."""

import os
import re
import time
from urllib.parse import urlparse

import requests
import trafilatura
from googlesearch import search
from rank_bm25 import BM25Okapi
from urllib3.exceptions import HTTPError

from src.pre_processing.vlm_extractor.utils import VIET_NEWS_SITES, remove_diacritics
from src.utils.logger import get_logger
from src.utils.settings import get_settings

logger = get_logger()


class Search_web:
    """Searches, scrapes, cleans and stores content from trusted Vietnamese news sites for a query."""

    def __init__(
        self,
        query,
        output_dir: str | None = None,
        metadata_path: str | None = None,
        shot_index: int = 1,
    ):
        self.query = query
        self.output_dir = output_dir or get_settings().base_output_craw_path
        self.metadata_path = metadata_path
        self.shot_index = shot_index
        self.candidate_urls = []
        self.best_url = None

    def _get_year_from_metadata(self) -> str | None:
        """Read the metadata file/folder and extract a year from 'publish_date'."""
        if not self.metadata_path or not os.path.exists(self.metadata_path):
            logger.info("   [INFO] Metadata path does not exist.")
            return None

        json_file_path = None

        if os.path.isdir(self.metadata_path):
            logger.info(
                "   [INFO] Metadata path is a folder. Looking for the first .json file..."
            )
            for filename in os.listdir(self.metadata_path):
                if filename.endswith(".json"):
                    json_file_path = os.path.join(self.metadata_path, filename)
                    logger.info(f"   [INFO] Found metadata file: {json_file_path}")
                    break

        elif os.path.isfile(self.metadata_path):
            json_file_path = self.metadata_path

        if not json_file_path:
            logger.warning(
                f"   [ERROR] No valid .json file found in folder: {self.metadata_path}"
            )
            return None

        try:
            import json

            with open(json_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            publish_date = data.get("publish_date")
            if publish_date and isinstance(publish_date, str):
                year = publish_date.split("/")[-1]
                if year.isdigit() and len(year) == 4:
                    logger.info(
                        f"   [INFO] Applying time filter for year {year} from metadata."
                    )
                    return year
        except Exception as e:
            logger.warning(
                f"   [ERROR] Could not read or process '{json_file_path}': {e}"
            )

        return None

    def _find_candidate_urls(self, num_results=10, max_retries=3):
        """Search Google, filter URLs, and retry if IP-blocked."""
        logger.info("--- STEP 1: SEARCH AND FILTER URLS ---")
        year = self._get_year_from_metadata()
        search_query = f'"{self.query}"'
        if year:
            search_query += f" năm: {year}"  # Optimize the Google query

        logger.info(f"   [INFO] Running query: {search_query}")

        for attempt in range(max_retries):
            try:
                search_results = search(
                    search_query, num_results=num_results, lang="vi"
                )
                self.candidate_urls = [
                    url
                    for url in search_results
                    if any(site in urlparse(url).netloc for site in VIET_NEWS_SITES)
                ]

                if not self.candidate_urls:
                    logger.warning(
                        "   [RESULT] No matching URLs found from the specified news sites."
                    )
                    return False

                logger.info(
                    f"   [RESULT] Found {len(self.candidate_urls)} candidate URLs."
                )
                return True

            except HTTPError as e:
                if "429" in str(e):
                    logger.warning(
                        f"   [WARNING] IP blocked (429). Waiting 2s to retry... (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(2)
                else:
                    logger.error(f"   [ERROR] Unknown HTTP error during search: {e}")
                    return False
            except Exception as e:
                logger.error(f"   [ERROR] An error occurred during Google search: {e}")
                return False

        logger.error(
            f"   [ERROR] Search failed after {max_retries} attempts. Check connection or IP."
        )
        return False

    def _rank_and_select_best_url(self):
        """Use BM25 to rank and select the best URL matching the query."""
        logger.info("\n--- STEP 2: RANK AND SELECT BEST URL ---")
        if not self.candidate_urls:
            return False

        logger.info("   [DEBUG] Candidate URLs found:")
        for url in self.candidate_urls:
            logger.info(f"     - {url}")

        tokenized_corpus = [
            re.split(r"[^a-z0-9]+", remove_diacritics(url))
            for url in self.candidate_urls
        ]
        tokenized_query = re.split(r"[^a-z0-9]+", remove_diacritics(self.query))

        try:
            bm25 = BM25Okapi(tokenized_corpus)
            doc_scores = bm25.get_scores(tokenized_query)
            best_doc_index = doc_scores.argmax()
            self.best_url = self.candidate_urls[best_doc_index]

            logger.info(f"   [DEBUG] BM25 scores for URLs: {doc_scores}")
            logger.info(
                f"   [RESULT] Best URL selected (BM25 score: {doc_scores[best_doc_index]:.2f}):"
            )
            logger.info(f"   -> {self.best_url}")
            return True
        except Exception as e:
            logger.error(f"   [ERROR] An error occurred during BM25 ranking: {e}")
            return False

    def _crawl_clean_and_save(self):
        """Download, clean and save content from the selected URL."""
        logger.info("\n--- STEP 3: CRAWL, CLEAN AND SAVE CONTENT ---")
        os.makedirs(self.output_dir, exist_ok=True)

        filename = (
            f"output_{self.shot_index}.txt"
            if self.shot_index is not None
            else "output.txt"
        )
        output_file = os.path.join(self.output_dir, filename)

        logger.info(f"   [INFO] Processing URL: {self.best_url}")

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
            }
            response = requests.get(
                self.best_url, headers=headers, timeout=20, verify=False
            )
            response.raise_for_status()

            cleaned_content = trafilatura.extract(
                response.text,
                favor_recall=True,
                include_comments=False,
                include_tables=False,
            )

            if cleaned_content:
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(cleaned_content)
                logger.info(f"   [SUCCESS] Saved cleaned content to: '{output_file}'")
                return cleaned_content
            else:
                logger.warning(
                    "   [ERROR] Trafilatura could not extract the main content."
                )
                return None

        except Exception as e:
            logger.error(
                f"   [ERROR] An error occurred while crawling and saving the file: {e}"
            )
            return None

    def run(self):
        """Execute the full search -> rank -> crawl pipeline."""
        logger.info("\n================= PIPELINE START =================")

        if not self._find_candidate_urls():
            logger.error("Pipeline stopped: no candidate URLs found.")
            return None

        if not self._rank_and_select_best_url():
            logger.error("Pipeline stopped: could not rank or select a URL.")
            return None

        content = self._crawl_clean_and_save()

        logger.info("\n================= PIPELINE END =================\n")
        return content
