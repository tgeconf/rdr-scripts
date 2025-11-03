# -*- coding: utf-8 -*-
"""arXiv Paper Fetcher using arXiv API.

This script fetches papers from arXiv using their official API and stores them
in a local JSON database. The module is designed to be production-ready with
robust error handling, rate limiting, and compatibility with existing RDR pipeline.
"""

from __future__ import annotations

import json
import os
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("arxiv_fetcher.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# arXiv API configuration
ARXIV_API_BASE = "http://export.arxiv.org/api/query?"

# arXiv API Supported Categories (as of 2024)
# Full list: https://arxiv.org/category_taxonomy
#
# Computer Science (cs)
# cs.AI    - Artificial Intelligence
# cs.AR    - Hardware Architecture
# cs.CC    - Computational Complexity
# cs.CE    - Computational Engineering, Finance, and Science
# cs.CG    - Computational Geometry
# cs.CL    - Computation and Language
# cs.CR    - Cryptography and Security
# cs.CV    - Computer Vision and Pattern Recognition
# cs.CY    - Computers and Society
# cs.DB    - Databases
# cs.DC    - Distributed, Parallel, and Cluster Computing
# cs.DL    - Digital Libraries
# cs.DM    - Discrete Mathematics
# cs.DS    - Data Structures and Algorithms
# cs.ET    - Emerging Technologies
# cs.FL    - Formal Languages and Automata Theory
# cs.GL    - General Literature
# cs.GR    - Graphics
# cs.GT    - Computer Science and Game Theory
# cs.HC    - Human-Computer Interaction
# cs.IR    - Information Retrieval
# cs.IT    - Information Theory
# cs.LG    - Machine Learning
# cs.LO    - Logic in Computer Science
# cs.MA    - Multiagent Systems
# cs.MM    - Multimedia
# cs.MS    - Mathematical Software
# cs.NA    - Numerical Analysis
# cs.NE    - Neural and Evolutionary Computing
# cs.NI    - Networking and Internet Architecture
# cs.OH    - Other Computer Science
# cs.OS    - Operating Systems
# cs.PF    - Performance
# cs.PL    - Programming Languages
# cs.RO    - Robotics
# cs.SC    - Symbolic Computation
# cs.SD    - Sound
# cs.SE    - Software Engineering
# cs.SI    - Social and Information Networks
# cs.SY    - Systems and Control
#
# Economics (econ)
# econ.EM  - Econometrics
# econ.GN  - General Economics
# econ.TH  - Theoretical Economics
#
# Electrical Engineering and Systems Science (eess)
# eess.AS  - Audio and Speech Processing
# eess.IV  - Image and Video Processing
# eess.SP  - Signal Processing
# eess.SY  - Systems and Control
#
# Mathematics (math)
# math.AC  - Commutative Algebra
# math.AG  - Algebraic Geometry
# math.AP  - Analysis of PDEs
# math.AT  - Algebraic Topology
# math.CA  - Classical Analysis and ODEs
# math.CO  - Combinatorics
# math.CT  - Category Theory
# math.CV  - Complex Variables
# math.DG  - Differential Geometry
# math.DS  - Dynamical Systems
# math.FA  - Functional Analysis
# math.GM  - General Mathematics
# math.GN  - General Topology
# math.GR  - Group Theory
# math.GT  - Geometric Topology
# math.HO  - History and Overview
# math.IT  - Information Theory
# math.KT  - K-Theory and Homology
# math.LO  - Logic
# math.MG  - Metric Geometry
# math.MP  - Mathematical Physics
# math.NA  - Numerical Analysis
# math.NT  - Number Theory
# math.OA  - Operator Algebras
# math.OC  - Optimization and Control
# math.PR  - Probability
# math.QA  - Quantum Algebra
# math.RA  - Rings and Algebras
# math.RT  - Representation Theory
# math.SG  - Symplectic Geometry
# math.SP  - Spectral Theory
# math.ST  - Statistics Theory
#
# Astrophysics (astro-ph)
# astro-ph.CO - Cosmology and Nongalactic Astrophysics
# astro-ph.EP - Earth and Planetary Astrophysics
# astro-ph.GA - Astrophysics of Galaxies
# astro-ph.HE - High Energy Astrophysical Phenomena
# astro-ph.IM - Instrumentation and Methods for Astrophysics
# astro-ph.SR - Solar and Stellar Astrophysics
#
# Condensed Matter (cond-mat)
# cond-mat.dis-nn - Disordered Systems and Neural Networks
# cond-mat.mes-hall - Mesoscale and Nanoscale Physics
# cond-mat.mtrl-sci - Materials Science
# cond-mat.other - Other Condensed Matter
# cond-mat.quant-gas - Quantum Gases
# cond-mat.soft - Soft Condensed Matter
# cond-mat.stat-mech - Statistical Mechanics
# cond-mat.str-el - Strongly Correlated Electrons
# cond-mat.supr-con - Superconductivity
#
# General Relativity and Quantum Cosmology (gr-qc)
#
# High Energy Physics (hep)
# hep-ex   - High Energy Physics - Experiment
# hep-lat  - High Energy Physics - Lattice
# hep-ph   - High Energy Physics - Phenomenology
# hep-th   - High Energy Physics - Theory
#
# Nonlinear Sciences (nlin)
# nlin.AO  - Adaptation and Self-Organizing Systems
# nlin.CD  - Chaotic Dynamics
# nlin.CG  - Cellular Automata and Lattice Gases
# nlin.PS  - Pattern Formation and Solitons
# nlin.SI  - Exactly Solvable and Integrable Systems
#
# Physics (physics)
# physics.acc-ph  - Accelerator Physics
# physics.ao-ph  - Atmospheric and Oceanic Physics
# physics.app-ph  - Applied Physics
# physics.atm-clus - Atomic and Molecular Clusters
# physics.atom-ph  - Atomic Physics
# physics.bio-ph  - Biological Physics
# physics.chem-ph  - Chemical Physics
# physics.class-ph - Classical Physics
# physics.comp-ph  - Computational Physics
# physics.data-an  - Data Analysis, Statistics and Probability
# physics.ed-ph   - Physics Education
# physics.flu-dyn  - Fluid Dynamics
# physics.gen-ph  - General Physics
# physics.geo-ph  - Geophysics
# physics.hist-ph - History and Philosophy of Physics
# physics.ins-det - Instrumentation and Detectors
# physics.med-ph  - Medical Physics
# physics.optics  - Optics
# physics.plasm-ph - Plasma Physics
# physics.pop-ph  - Popular Physics
# physics.soc-ph  - Physics and Society
# physics.space-ph - Space Physics
#
# Quantitative Biology (q-bio)
# q-bio.BM  - Biomolecules
# q-bio.CB  - Cell Behavior
# q-bio.GN  - Genomics
# q-bio.MN  - Molecular Networks
# q-bio.NC  - Neurons and Cognition
# q-bio.OT  - Other Quantitative Biology
# q-bio.PE  - Populations and Evolution
# q-bio.QM  - Quantitative Methods
# q-bio.SC  - Subcellular Processes
# q-bio.TO  - Tissues and Organs
#
# Quantitative Finance (q-fin)
# q-fin.CP  - Computational Finance
# q-fin.EC  - Economics
# q-fin.GN  - General Finance
# q-fin.MF  - Mathematical Finance
# q-fin.PM  - Portfolio Management
# q-fin.PR  - Pricing of Securities
# q-fin.RM  - Risk Management
# q-fin.ST  - Statistical Finance
# q-fin.TR  - Trading and Market Microstructure
#
# Statistics (stat)
# stat.AP   - Applications
# stat.CO   - Computation
# stat.ME   - Methodology
# stat.ML   - Machine Learning
# stat.OT   - Other Statistics
# stat.TH   - Statistics Theory

DEFAULT_CATEGORIES = [
    "cs.LG",  # Machine Learning
    "cs.AI",  # Artificial Intelligence
    "cs.CL",  # Computation and Language
    "stat.ML",  # Machine Learning (Statistics)
    "cs.MA",
    "q-fin.TR",
    "q-fin.CP",
    "q-fin.PM",
    "q-fin.PR",
    "q-fin.RM"
]

MIN_BATCH_SIZE = 10


class Paper:
    """Paper class matching the existing project structure."""

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

    def to_dict(self) -> dict:
        """Convert paper to dictionary matching existing JSON structure."""
        return {
            "paper_id": self.paper_id,
            "authors": self.authors,
            "title": self.title,
            "paper_url": self.paper_url,
            "pdf_link": self.pdf_link,
            "abstract": self.abstract,
            "updated_time": self.updated_time,
            "published_time": self.published_time,
            "primary_category": self.primary_category,
            "categories": self.categories,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Paper":
        """Create Paper instance from dictionary."""
        paper = cls(data["paper_id"], data["authors"], data["title"])
        paper.paper_url = data.get("paper_url")
        paper.pdf_link = data.get("pdf_link")
        paper.abstract = data.get("abstract")
        paper.updated_time = data.get("updated_time")
        paper.published_time = data.get("published_time")
        paper.primary_category = data.get("primary_category")
        paper.categories = data.get("categories")
        return paper


class PaperDatabase:
    """Database class for managing papers, matching existing structure."""

    def __init__(self, output_dir: str = "dataset", filename: str = "arxiv.json"):
        self.output_dir = output_dir
        self.filename = os.path.join(output_dir, filename)
        self.papers: Dict[str, Paper] = {}
        self._load_existing_papers()

    def _load_existing_papers(self):
        """Load existing papers from the JSON file if it exists."""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r", encoding="utf-8") as f:
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
        with open(self.filename, "w", encoding="utf-8") as f:
            json.dump(papers_data, f, indent=2, ensure_ascii=False)

    def has_paper(self, paper_id: str) -> bool:
        """Check if a paper exists in the database."""
        return paper_id in self.papers

    def get_paper(self, paper_id: str) -> Optional[Paper]:
        """Get a paper from the database if it exists."""
        return self.papers.get(paper_id)


class ArxivFetcher:
    """Robust arXiv API fetcher with error handling and rate limiting."""

    def __init__(self, max_results: int = 50000, delay: float = 3.0):
        self.max_results = max_results
        self.delay = delay  # Delay between requests to respect rate limits

        # Configure retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def build_query(self, categories: List[str], start_date: str, end_date: str) -> str:
        """Build arXiv API query string."""
        # Combine categories with OR
        category_query = " OR ".join([f"cat:{cat}" for cat in categories])

        # Date range filter
        date_query = f"submittedDate:[{start_date} TO {end_date}]"

        # Combine all conditions
        search_query = f"({category_query}) AND {date_query}"

        return search_query
        # return category_query

    def fetch_papers(
        self, categories: List[str], start_date: str, end_date: str
    ) -> List[Paper]:
        """Fetch papers from arXiv API."""
        papers = []
        start_index = 0
        batch_size = 100  # arXiv API max per request
        original_batch_size = batch_size

        search_query = self.build_query(categories, start_date, end_date)

        logger.info(f"Fetching papers from arXiv with query: {search_query}")

        while start_index < self.max_results:
            try:
                params = {
                    "search_query": search_query,
                    "start": start_index,
                    "max_results": min(batch_size, self.max_results - start_index),
                    "sortBy": "submittedDate",
                    "sortOrder": "descending",
                }

                logger.info(
                    f"Fetching batch {start_index // original_batch_size + 1}, start_index: {start_index}, batch_size: {batch_size}..."
                )

                response = self.session.get(ARXIV_API_BASE, params=params, timeout=30)
                response.raise_for_status()

                # Parse Atom feed
                batch_papers = self.parse_atom_feed(response.text)

                # Check for empty feed with totalResults > 0 (API anomaly)
                if not batch_papers:
                    total_results = self._extract_total_results(response.text)
                    if total_results and total_results > start_index:
                        logger.warning(
                            f"Empty feed received but totalResults={total_results}, "
                            f"start_index={start_index}, batch_size={batch_size}. "
                            f"This is an API anomaly. Adjusting batch_size..."
                        )

                        # Adjust batch_size strategy
                        if batch_size > MIN_BATCH_SIZE:
                            # Reduce batch_size by half, minimum MIN_BATCH_SIZE
                            new_batch_size = max(MIN_BATCH_SIZE, batch_size // 2)
                            logger.info(
                                f"Reducing batch_size from {batch_size} to {new_batch_size}"
                            )
                            batch_size = new_batch_size
                            # Don't increment start_index, retry with smaller batch
                            continue
                        else:
                            # Already at minimum batch_size, skip this problematic range
                            logger.warning(
                                f"Already at minimum batch_size ({batch_size}). "
                                f"Skipping problematic range starting at index {start_index}."
                            )
                            # Skip this problematic range by moving to next batch
                            start_index += original_batch_size
                            # Reset batch_size to original for next batch
                            batch_size = original_batch_size
                            continue
                    else:
                        logger.info("No more papers found in this batch")
                        break

                papers.extend(batch_papers)
                logger.info(f"Fetched {len(batch_papers)} papers in this batch")

                # Check if we've reached the end
                if len(batch_papers) < batch_size:
                    logger.info("Reached end of available papers")
                    break

                start_index += batch_size

                # Successfully got papers, reset batch_size to original if it was reduced
                if batch_size != original_batch_size:
                    logger.info(
                        f"Success with reduced batch_size. Resetting to original: {original_batch_size}"
                    )
                    batch_size = original_batch_size

                # Respect rate limits
                time.sleep(self.delay)

            except requests.RequestException as e:
                logger.error(f"Request failed: {e}")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                break

        logger.info(f"Total papers fetched: {len(papers)}")
        return papers

    def _extract_total_results(self, feed_content: str) -> Optional[int]:
        """Extract totalResults from Atom feed."""
        import xml.etree.ElementTree as ET

        try:
            root = ET.fromstring(feed_content)

            # Define namespaces
            ns = {
                "atom": "http://www.w3.org/2005/Atom",
                "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
            }

            # Find totalResults element
            total_results_elem = root.find("opensearch:totalResults", ns)
            if total_results_elem is not None and total_results_elem.text:
                return int(total_results_elem.text)

        except (ET.ParseError, ValueError) as e:
            logger.warning(f"Failed to extract totalResults: {e}")

        return None

    def parse_atom_feed(self, feed_content: str) -> List[Paper]:
        """Parse arXiv Atom feed and extract paper information."""
        import xml.etree.ElementTree as ET

        papers = []

        try:
            root = ET.fromstring(feed_content)

            # Define namespaces
            ns = {
                "atom": "http://www.w3.org/2005/Atom",
                "arxiv": "http://arxiv.org/schemas/atom",
            }

            for entry in root.findall("atom:entry", ns):
                try:
                    # Extract paper ID (arXiv ID)
                    paper_id_elem = entry.find("atom:id", ns)
                    if paper_id_elem is None:
                        continue

                    paper_id = paper_id_elem.text.split("/")[-1]  # Extract arXiv ID

                    # Extract title
                    title_elem = entry.find("atom:title", ns)
                    title = title_elem.text.strip() if title_elem is not None else ""

                    # extract updated time
                    updated_time_elem = entry.find("atom:updated", ns)
                    updated_time = (
                        updated_time_elem.text.strip()
                        if updated_time_elem is not None
                        else ""
                    )

                    # extract published time
                    published_time_elem = entry.find("atom:published", ns)
                    published_time = (
                        published_time_elem.text.strip()
                        if published_time_elem is not None
                        else ""
                    )

                    # Extract authors
                    author_elems = entry.findall("atom:author/atom:name", ns)
                    authors = ", ".join(
                        [author.text for author in author_elems if author.text]
                    )

                    # extract primary category
                    primary_category_elem = entry.find(
                        "arxiv:primary_category", ns
                    )
                    primary_category = (
                        primary_category_elem.get("term")
                        if primary_category_elem is not None
                        else ""
                    )

                    # extract categories
                    categories_elem = entry.findall("atom:category", ns)
                    categories = (
                        ", ".join(
                            [
                                category.get("term")
                                for category in categories_elem
                                if category.get("term")
                            ]
                        )
                        if categories_elem is not None
                        else ""
                    )

                    # Extract abstract
                    summary_elem = entry.find("atom:summary", ns)
                    abstract = (
                        summary_elem.text.strip() if summary_elem is not None else ""
                    )

                    # Extract links
                    paper_url = None
                    pdf_link = None

                    for link in entry.findall("atom:link", ns):
                        rel = link.get("rel")
                        href = link.get("href")

                        if rel == "alternate":
                            paper_url = href
                        elif rel == "related" and link.get("title") == "pdf":
                            pdf_link = href

                    # Create Paper object
                    paper = Paper(paper_id, authors, title)
                    paper.paper_url = paper_url
                    paper.pdf_link = pdf_link
                    paper.abstract = abstract
                    paper.updated_time = updated_time
                    paper.published_time = published_time
                    paper.primary_category = primary_category
                    paper.categories = categories

                    papers.append(paper)

                except Exception as e:
                    logger.warning(f"Failed to parse entry: {e}")
                    continue

        except ET.ParseError as e:
            logger.error(f"Failed to parse Atom feed: {e}")

        return papers


def fetch_arxiv_papers(
    categories: List[str] = None,
    start_date: str = None,
    end_date: str = None,
    max_results: int = 50000,
    output_filename: str = "arxiv.json",
) -> int:
    """
    Main function to fetch arXiv papers and save to database.

    Args:
        categories: List of arXiv categories to search
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        max_results: Maximum number of papers to fetch
        output_filename: Output JSON filename

    Returns:
        Number of new papers added
    """
    if categories is None:
        categories = DEFAULT_CATEGORIES

    if start_date is None:
        # Default to last 30 days
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")

    if end_date is None:
        end_date = datetime.now().strftime("%Y%m%d")

    # Initialize database
    db = PaperDatabase(filename=output_filename)

    # Initialize fetcher
    fetcher = ArxivFetcher(max_results=max_results)

    # Fetch papers
    logger.info(f"Starting arXiv paper fetch from {start_date} to {end_date}")
    logger.info(f"Categories: {', '.join(categories)}")

    papers = fetcher.fetch_papers(categories, start_date, end_date)

    # Save new papers to database
    new_papers = 0
    for paper in papers:
        if not db.has_paper(paper.paper_id):
            db.save_paper(paper)
            new_papers += 1

    logger.info(f"Added {new_papers} new papers to database")
    return new_papers


def main():
    """Command-line interface for arXiv fetcher."""
    import argparse

    parser = argparse.ArgumentParser(description="Fetch papers from arXiv")
    parser.add_argument(
        "--categories",
        nargs="+",
        default=DEFAULT_CATEGORIES,
        help="arXiv categories to search",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=(datetime.now() - timedelta(days=30)).strftime("%Y%m%d"),
        help="Start date (YYYYMMDD)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=datetime.now().strftime("%Y%m%d"),
        help="End date (YYYYMMDD)",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=50000,
        help="Maximum number of papers to fetch",
    )
    parser.add_argument(
        "--output", type=str, default="arxiv.json", help="Output filename"
    )

    args = parser.parse_args()

    try:
        new_papers = fetch_arxiv_papers(
            categories=args.categories,
            start_date=args.start_date,
            end_date=args.end_date,
            max_results=args.max_results,
            output_filename=args.output,
        )

        print(f"\n[DONE] Added {new_papers} new papers to {args.output}")

    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise


if __name__ == "__main__":
    main()
