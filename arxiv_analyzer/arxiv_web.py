# -*- coding: utf-8 -*-
"""arXiv Web Crawler for fetching latest papers directly from arXiv website.

This module provides a production-ready web crawler that fetches arXiv papers
directly from the website, bypassing API delays to get the most recent papers.
"""

from __future__ import annotations

import json
import os
import time
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any, Tuple
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from .arxiv_web_config import (
        CrawlerConfig, 
        DEFAULT_CATEGORIES, 
        HTML_SELECTORS,
        get_category_url,
        validate_config
    )
except ImportError:
    # Fallback for direct execution
    from arxiv_web_config import (
        CrawlerConfig, 
        DEFAULT_CATEGORIES, 
        HTML_SELECTORS,
        get_category_url,
        validate_config
    )


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('arxiv_web_crawler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class Paper:
    """Paper class matching the existing project structure with extended fields."""
    
    def __init__(self, paper_id: str, authors: str, title: str):
        self.paper_id = paper_id
        self.authors = authors
        self.title = title
        self.paper_url = None
        self.pdf_link = None
        self.abstract = None
        self.updated_time = None
        self.published_time = None
        self.primary_category = None
        self.categories = None
        self.comments = None
        self.journal_ref = None
        self.doi = None
        self.report_no = None
        self.acm_class = None
        self.msc_class = None
        self.html_link = None
    
    def to_dict(self) -> dict:
        """Convert paper to dictionary matching existing JSON structure."""
        return {
            'paper_id': self.paper_id,
            'authors': self.authors,
            'title': self.title,
            'paper_url': self.paper_url,
            'pdf_link': self.pdf_link,
            'abstract': self.abstract,
            'updated_time': self.updated_time,
            'published_time': self.published_time,
            'primary_category': self.primary_category,
            'categories': self.categories,
            'comments': self.comments,
            'journal_ref': self.journal_ref,
            'doi': self.doi,
            'report_no': self.report_no,
            'acm_class': self.acm_class,
            'msc_class': self.msc_class,
            'html_link': self.html_link,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Paper':
        """Create Paper instance from dictionary."""
        paper = cls(data['paper_id'], data['authors'], data['title'])
        paper.paper_url = data.get('paper_url')
        paper.pdf_link = data.get('pdf_link')
        paper.abstract = data.get('abstract')
        paper.updated_time = data.get('updated_time')
        paper.published_time = data.get('published_time')
        paper.primary_category = data.get('primary_category')
        paper.categories = data.get('categories')
        paper.comments = data.get('comments')
        paper.journal_ref = data.get('journal_ref')
        paper.doi = data.get('doi')
        paper.report_no = data.get('report_no')
        paper.acm_class = data.get('acm_class')
        paper.msc_class = data.get('msc_class')
        paper.html_link = data.get('html_link')
        return paper


class PaperDatabase:
    """Database class for managing papers, matching existing structure."""
    
    def __init__(self, output_dir: str = "dataset", filename: str = "arxiv_web.json"):
        if os.path.isabs(filename):
            self.output_dir = os.path.dirname(filename)
            self.filename = filename
        else:
            self.output_dir = output_dir
            self.filename = os.path.join(output_dir, filename)
        self.papers: Dict[str, Paper] = {}
        self._load_existing_papers()

    def _load_existing_papers(self):
        """Load existing papers from the JSON file if it exists."""
        target_dir = os.path.dirname(self.filename) or self.output_dir
        if target_dir and not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
        
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for paper_dict in data:
                        paper = Paper.from_dict(paper_dict)
                        self.papers[paper.paper_id] = paper
                logger.info(f"Loaded {len(self.papers)} existing papers from database")
            except Exception as e:
                logger.error(f"Failed to load existing papers: {e}")
                # Create a backup of the potentially corrupted file
                if os.path.exists(self.filename):
                    backup_name = f"{self.filename}.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    os.rename(self.filename, backup_name)
                    logger.info(f"Created backup of existing database: {backup_name}")

    def save_paper(self, paper: Paper):
        """Save or update a single paper in the database."""
        self.papers[paper.paper_id] = paper
        self._save_to_file()

    def _save_to_file(self):
        """Save all papers to the JSON file."""
        papers_data = [paper.to_dict() for paper in self.papers.values()]
        target_dir = os.path.dirname(self.filename)
        if target_dir and not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(papers_data, f, indent=2, ensure_ascii=False)

    def has_paper(self, paper_id: str) -> bool:
        """Check if a paper exists in the database."""
        return paper_id in self.papers

    def get_paper(self, paper_id: str) -> Optional[Paper]:
        """Get a paper from the database if it exists."""
        return self.papers.get(paper_id)


class ArxivWebCrawler:
    """Robust arXiv web crawler with error handling and rate limiting."""
    
    def __init__(self, config: CrawlerConfig = None):
        self.config = config or CrawlerConfig()
        validate_config(self.config)
        
        # Configure HTTP session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=self.config.retry_attempts,
            backoff_factor=self.config.retry_delay,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set user agent to identify as a legitimate crawler
        self.session.headers.update({
            'User-Agent': 'arXiv-Web-Crawler/1.0 (https://github.com/your-repo; your-email@example.com)'
        })
    
    def crawl_category_list(self, category: str) -> List[Paper]:
        """Crawl the list page for a specific category and extract basic paper info."""
        papers = []
        url = get_category_url(category)
        
        logger.info(f"Crawling category {category} from {url}")
        
        try:
            response = self.session.get(url, timeout=self.config.request_timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find the articles container
            articles_container = soup.select_one(HTML_SELECTORS["list_page"]["articles_container"])
            if not articles_container:
                logger.warning(f"No articles container found for category {category}")
                return papers
            
            # Extract date from the page to filter recent papers
            current_date = self._extract_current_date(soup)
            if not current_date:
                logger.warning(f"Could not extract date from page for category {category}")
                return papers
            
            # Parse article items
            article_items = articles_container.select(HTML_SELECTORS["list_page"]["article_items"])
            
            current_dt = None
            current_dd = None
            
            for item in article_items:
                if item.name == 'dt':
                    current_dt = item
                elif item.name == 'dd' and current_dt:
                    paper = self._parse_list_item(current_dt, item, category, current_date)
                    if paper:
                        papers.append(paper)
                    current_dt = None
            
            logger.info(f"Found {len(papers)} papers in category {category}")
            
        except requests.RequestException as e:
            logger.error(f"Failed to crawl category {category}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error crawling category {category}: {e}")
        
        return papers
    
    def _extract_current_date(self, soup: BeautifulSoup) -> Optional[datetime]:
        """Extract the current date from the page header."""
        try:
            date_header = soup.select_one(HTML_SELECTORS["list_page"]["date_header"])
            if date_header:
                # Extract date from header like "Mon, 3 Nov 2025 (showing first 50 of 141 entries)"
                date_text = date_header.get_text()
                date_match = re.search(r'(\w+, \d+ \w+ \d{4})', date_text)
                if date_match:
                    date_str = date_match.group(1)
                    return datetime.strptime(date_str, "%a, %d %b %Y")
        except Exception as e:
            logger.warning(f"Failed to extract date from header: {e}")
        
        return None
    
    def _parse_list_item(self, dt: BeautifulSoup, dd: BeautifulSoup, category: str, current_date: datetime) -> Optional[Paper]:
        """Parse a single paper item from the list page."""
        try:
            # Extract paper ID
            paper_link = dt.select_one(HTML_SELECTORS["list_page"]["paper_id"])
            if not paper_link:
                return None
            
            paper_id = paper_link.get('href', '').replace('/abs/', '')
            if not paper_id:
                return None
            
            # Extract title
            title_elem = dd.select_one(HTML_SELECTORS["list_page"]["title"])
            title = self._clean_text(title_elem.get_text()) if title_elem else ""
            
            # Extract authors
            authors_elem = dd.select_one(HTML_SELECTORS["list_page"]["authors"])
            authors = self._extract_authors(authors_elem) if authors_elem else ""
            
            # Extract comments
            comments_elem = dd.select_one(HTML_SELECTORS["list_page"]["comments"])
            comments = self._clean_text(comments_elem.get_text()) if comments_elem else ""
            
            # Extract subjects
            subjects_elem = dd.select_one(HTML_SELECTORS["list_page"]["subjects"])
            primary_subject_elem = dd.select_one(HTML_SELECTORS["list_page"]["primary_subject"])
            
            primary_category = self._clean_text(primary_subject_elem.get_text()) if primary_subject_elem else category
            categories = self._extract_categories(subjects_elem) if subjects_elem else primary_category
            
            # Create paper object with basic info
            paper = Paper(paper_id, authors, title)
            paper.paper_url = f"https://arxiv.org/abs/{paper_id}"
            paper.pdf_link = f"https://arxiv.org/pdf/{paper_id}.pdf"
            paper.comments = comments
            paper.primary_category = primary_category
            paper.categories = categories
            paper.published_time = current_date.isoformat()
            
            return paper
            
        except Exception as e:
            logger.warning(f"Failed to parse list item: {e}")
            return None
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        if not text:
            return ""
        
        # Remove descriptor prefixes like "Title:", "Authors:", etc.
        text = re.sub(r'^[A-Za-z]+:\s*', '', text.strip())
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def _extract_authors(self, authors_elem: BeautifulSoup) -> str:
        """Extract author names from the authors element."""
        try:
            author_links = authors_elem.find_all('a')
            authors = [link.get_text().strip() for link in author_links]
            return ", ".join(authors)
        except Exception as e:
            logger.warning(f"Failed to extract authors: {e}")
            return ""
    
    def _extract_categories(self, subjects_elem: BeautifulSoup) -> str:
        """Extract categories from the subjects element."""
        try:
            # Remove the primary subject span and get the remaining text
            primary_span = subjects_elem.find('span', class_='primary-subject')
            if primary_span:
                primary_span.extract()
            
            # Get remaining categories
            categories_text = subjects_elem.get_text().strip()
            
            # Clean up separators
            categories_text = re.sub(r'^;\s*', '', categories_text)
            categories_text = re.sub(r'\s*;\s*', '; ', categories_text)
            
            return categories_text
        except Exception as e:
            logger.warning(f"Failed to extract categories: {e}")
            return ""

    def crawl_paper_details(self, papers: List[Paper]) -> List[Paper]:
        """Crawl detail pages for papers in parallel to get complete metadata."""
        if not papers:
            return []
        
        logger.info(f"Starting parallel crawl of {len(papers)} paper details")
        
        # Use ThreadPoolExecutor for parallel crawling
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            # Submit all crawl tasks
            future_to_paper = {
                executor.submit(self._crawl_single_paper_detail, paper): paper 
                for paper in papers
            }
            
            # Collect results as they complete
            completed_papers = []
            for future in as_completed(future_to_paper):
                paper = future_to_paper[future]
                try:
                    updated_paper = future.result()
                    if updated_paper:
                        completed_papers.append(updated_paper)
                    else:
                        logger.warning(f"Failed to crawl details for paper {paper.paper_id}")
                        # Keep the original paper with basic info
                        completed_papers.append(paper)
                except Exception as e:
                    logger.error(f"Error crawling paper {paper.paper_id}: {e}")
                    # Keep the original paper with basic info
                    completed_papers.append(paper)
        
        logger.info(f"Successfully crawled details for {len(completed_papers)} papers")
        return completed_papers
    
    def _crawl_single_paper_detail(self, paper: Paper) -> Optional[Paper]:
        """Crawl detail page for a single paper and update its metadata."""
        try:
            response = self.session.get(paper.paper_url, timeout=self.config.request_timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Update paper with detailed information
            self._update_paper_from_detail(paper, soup)
            
            return paper
            
        except requests.RequestException as e:
            logger.warning(f"Failed to crawl detail page for {paper.paper_id}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected error crawling {paper.paper_id}: {e}")
            return None
    
    def _update_paper_from_detail(self, paper: Paper, soup: BeautifulSoup):
        """Update paper object with detailed information from the detail page."""
        try:
            # Extract abstract
            abstract_elem = soup.select_one(HTML_SELECTORS["detail_page"]["abstract"])
            if abstract_elem:
                paper.abstract = self._clean_text(abstract_elem.get_text())
            
            # Extract detailed authors (in case list page had truncated info)
            authors_elem = soup.select_one(HTML_SELECTORS["detail_page"]["authors"])
            if authors_elem:
                detailed_authors = self._extract_detailed_authors(authors_elem)
                if detailed_authors:
                    paper.authors = detailed_authors
            
            # Extract detailed subjects and categories
            subjects_elem = soup.select_one(HTML_SELECTORS["detail_page"]["subjects"])
            primary_subject_elem = soup.select_one(HTML_SELECTORS["detail_page"]["primary_subject"])
            
            if primary_subject_elem:
                paper.primary_category = self._clean_text(primary_subject_elem.get_text())
            
            if subjects_elem:
                paper.categories = self._extract_detailed_categories(subjects_elem)
            
            # Extract additional metadata from the table
            self._extract_metadata_table(paper, soup)
            
            # Extract HTML link if available
            html_link_elem = soup.select_one(HTML_SELECTORS["detail_page"]["html_link"])
            if html_link_elem:
                paper.html_link = html_link_elem.get('href', '')
            
            logger.debug(f"Updated detailed metadata for paper {paper.paper_id}")
            
        except Exception as e:
            logger.warning(f"Failed to update paper {paper.paper_id} from detail page: {e}")
    
    def _extract_detailed_authors(self, authors_elem: BeautifulSoup) -> str:
        """Extract detailed author information."""
        try:
            author_links = authors_elem.find_all('a')
            authors = []
            for link in author_links:
                author_name = link.get_text().strip()
                if author_name:
                    authors.append(author_name)
            return ", ".join(authors)
        except Exception as e:
            logger.warning(f"Failed to extract detailed authors: {e}")
            return ""
    
    def _extract_detailed_categories(self, subjects_elem: BeautifulSoup) -> str:
        """Extract detailed category information."""
        try:
            # Get all category spans
            category_spans = subjects_elem.find_all('span', class_='primary-subject')
            categories = []
            
            for span in category_spans:
                category_text = self._clean_text(span.get_text())
                if category_text:
                    categories.append(category_text)
            
            # Also get any additional categories from the text
            remaining_text = subjects_elem.get_text().strip()
            if remaining_text:
                # Remove primary categories from the text
                for category in categories:
                    remaining_text = remaining_text.replace(category, '')
                
                # Clean up the remaining text
                remaining_text = re.sub(r'^;\s*', '', remaining_text)
                remaining_text = re.sub(r'\s*;\s*', '; ', remaining_text)
                remaining_text = remaining_text.strip()
                
                if remaining_text:
                    categories.append(remaining_text)
            
            return "; ".join(categories)
            
        except Exception as e:
            logger.warning(f"Failed to extract detailed categories: {e}")
            return ""
    
    def _extract_metadata_table(self, paper: Paper, soup: BeautifulSoup):
        """Extract metadata from the detail page table."""
        try:
            # Find the metadata table
            meta_table = soup.find('table', summary='Additional metadata')
            if not meta_table:
                return
            
            # Extract various metadata fields
            rows = meta_table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    label = cells[0].get_text().strip().lower()
                    value = cells[1].get_text().strip()
                    
                    if 'comments' in label and not paper.comments:
                        paper.comments = self._clean_text(value)
                    elif 'journal' in label and 'ref' in label:
                        paper.journal_ref = self._clean_text(value)
                    elif 'doi' in label:
                        paper.doi = self._clean_text(value)
                    elif 'report' in label:
                        paper.report_no = self._clean_text(value)
                    elif 'acm' in label:
                        paper.acm_class = self._clean_text(value)
                    elif 'msc' in label:
                        paper.msc_class = self._clean_text(value)
                        
        except Exception as e:
            logger.warning(f"Failed to extract metadata table for paper {paper.paper_id}: {e}")


def crawl_arxiv_web(
    categories: List[str] = None,
    config: CrawlerConfig = None,
    include_details: bool = True
) -> List[Paper]:
    """
    Main function to crawl arXiv papers from the website.
    
    Args:
        categories: List of arXiv categories to crawl
        config: Crawler configuration
        include_details: Whether to crawl detail pages for complete metadata
    
    Returns:
        List of crawled papers
    """
    if config is None:
        config = CrawlerConfig()
    
    if categories:
        config.categories = categories
    
    validate_config(config)
    
    crawler = ArxivWebCrawler(config)
    all_papers = []
    
    logger.info(f"Starting arXiv web crawl for categories: {', '.join(config.categories)}")
    
    # Step 1: Crawl list pages for basic paper information
    for category in config.categories:
        papers = crawler.crawl_category_list(category)
        all_papers.extend(papers)
        
        # Respect rate limits
        time.sleep(config.rate_limit_delay)
    
    logger.info(f"Total papers crawled from list pages: {len(all_papers)}")
    
    # Step 2: Crawl detail pages for complete metadata (if requested)
    if include_details and all_papers:
        logger.info("Starting parallel crawl of paper details...")
        all_papers = crawler.crawl_paper_details(all_papers)
        logger.info(f"Completed detail crawl for {len(all_papers)} papers")
    
    return all_papers


def crawl_and_save_arxiv_web(
    categories: List[str] = None,
    config: CrawlerConfig = None,
    include_details: bool = True,
    output_filename: str = None
) -> int:
    """
    Crawl arXiv papers and save to database.
    
    Args:
        categories: List of arXiv categories to crawl
        config: Crawler configuration
        include_details: Whether to crawl detail pages
        output_filename: Output filename
    
    Returns:
        Number of new papers added
    """
    if config is None:
        config = CrawlerConfig()
    
    if output_filename:
        config.output_filename = output_filename
    
    # Crawl papers
    papers = crawl_arxiv_web(categories=categories, config=config, include_details=include_details)
    
    # Save to database
    db = PaperDatabase(filename=config.output_filename)
    
    new_papers = 0
    for paper in papers:
        if not db.has_paper(paper.paper_id):
            db.save_paper(paper)
            new_papers += 1
    
    logger.info(f"Added {new_papers} new papers to database")
    return new_papers


def main():
    """Command-line interface for arXiv web crawler."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Crawl arXiv papers directly from the website')
    parser.add_argument('--categories', nargs='+', default=DEFAULT_CATEGORIES,
                       help='arXiv categories to crawl')
    parser.add_argument('--max-workers', type=int, default=10,
                       help='Maximum concurrent workers for detail page crawling')
    parser.add_argument('--timeout', type=int, default=30,
                       help='Request timeout in seconds')
    parser.add_argument('--retry-attempts', type=int, default=3,
                       help='Number of retry attempts for failed requests')
    parser.add_argument('--rate-limit-delay', type=float, default=1.0,
                       help='Delay between requests to respect rate limits')
    parser.add_argument('--days-back', type=int, default=1,
                       help='Only crawl papers from the last N days')
    parser.add_argument('--max-papers', type=int, default=10000,
                       help='Maximum papers to crawl per category')
    parser.add_argument('--output', type=str, default='arxiv_web.json',
                       help='Output filename')
    parser.add_argument('--no-details', action='store_true',
                       help='Skip detail page crawling (only get basic info)')
    parser.add_argument('--log-level', type=str, default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level')
    
    args = parser.parse_args()
    
    # Configure logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    try:
        config = CrawlerConfig(
            categories=args.categories,
            max_workers=args.max_workers,
            request_timeout=args.timeout,
            retry_attempts=args.retry_attempts,
            rate_limit_delay=args.rate_limit_delay,
            days_back=args.days_back,
            max_papers_per_category=args.max_papers,
            output_filename=args.output,
            log_level=args.log_level
        )
        
        logger.info(f"Starting arXiv web crawler with configuration:")
        logger.info(f"  Categories: {', '.join(config.categories)}")
        logger.info(f"  Max workers: {config.max_workers}")
        logger.info(f"  Include details: {not args.no_details}")
        logger.info(f"  Output file: {config.output_filename}")
        
        new_papers = crawl_and_save_arxiv_web(
            config=config,
            include_details=not args.no_details,
            output_filename=args.output
        )
        
        print(f"\n[DONE] Successfully added {new_papers} new papers to {args.output}")
        
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        print("\n[CANCELLED] Crawling interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"\n[ERROR] Fatal error occurred: {e}")
        raise


if __name__ == "__main__":
    main()
