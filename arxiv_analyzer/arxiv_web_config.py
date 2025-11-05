# -*- coding: utf-8 -*-
"""Configuration module for arXiv web crawler.

This module provides configuration management for the arXiv web crawler,
including category settings, crawling parameters, and data storage options.
"""

from typing import List, Dict, Any
from dataclasses import dataclass
import os


@dataclass
class CrawlerConfig:
    """Configuration for arXiv web crawler."""

    # arXiv categories to crawl
    categories: List[str] = None

    # Crawling parameters
    max_workers: int = 10  # Maximum concurrent workers for detail page crawling
    request_timeout: int = 30  # Request timeout in seconds
    retry_attempts: int = 3  # Number of retry attempts for failed requests
    retry_delay: float = 2.0  # Delay between retries in seconds
    rate_limit_delay: float = 1.0  # Delay between requests to respect rate limits

    # Data filtering
    days_back: int = 1  # Only crawl papers from the last N days
    max_papers_per_category: int = 10000  # Maximum papers to crawl per category

    # Data storage
    output_dir: str = "dataset"
    output_filename: str = "arxiv_web.json"

    # Logging
    log_level: str = "INFO"
    log_file: str = "arxiv_web_crawler.log"

    def __post_init__(self):
        """Initialize default values."""
        if self.categories is None:
            self.categories = DEFAULT_CATEGORIES


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


# Default arXiv categories for crawling
DEFAULT_CATEGORIES = [
    "cs.AI",  # Artificial Intelligence
    "cs.LG",  # Machine Learning
    "cs.CL",  # Computation and Language
    "stat.ML",  # Machine Learning (Statistics)
    "cs.MA",  # Multiagent Systems
    "q-fin.TR",
    "q-fin.CP",
    "q-fin.PM",
    "q-fin.PR",
    "q-fin.RM",
]

# arXiv category display names for URL construction
CATEGORY_URLS = {
    "cs.AI": "https://arxiv.org/list/cs.AI/recent",
    "cs.LG": "https://arxiv.org/list/cs.LG/recent",
    "cs.CL": "https://arxiv.org/list/cs.CL/recent",
    "stat.ML": "https://arxiv.org/list/stat.ML/recent",
    "cs.MA": "https://arxiv.org/list/cs.MA/recent",
    "q-fin.TR": "https://arxiv.org/list/q-fin.TR/recent",
    "q-fin.CP": "https://arxiv.org/list/q-fin.CP/recent",
    "q-fin.PM": "https://arxiv.org/list/q-fin.PM/recent",
    "q-fin.PR": "https://arxiv.org/list/q-fin.PR/recent",
    "q-fin.RM": "https://arxiv.org/list/q-fin.RM/recent",
    # Add more categories as needed
}

# HTML parsing selectors for arXiv pages
HTML_SELECTORS = {
    # List page selectors
    "list_page": {
        "articles_container": "dl#articles",
        "article_items": "dt, dd",
        "paper_id": "a[href^='/abs/']",
        "title": "div.list-title",
        "authors": "div.list-authors",
        "comments": "div.list-comments",
        "subjects": "div.list-subjects",
        "primary_subject": "span.primary-subject",
        "date_header": "h3",
    },
    # Detail page selectors
    "detail_page": {
        "title": "h1.title",
        "authors": "div.authors",
        "abstract": "blockquote.abstract",
        "comments": "td.comments",
        "subjects": "td.subjects",
        "primary_subject": "span.primary-subject",
        "journal_ref": "td.journal-ref",
        "doi": "td.doi",
        "report_no": "td.report-no",
        "acm_class": "td.acm-class",
        "msc_class": "td.msc-class",
        "pdf_link": "a[href$='.pdf']",
        "html_link": "a[href*='/html/']",
    },
}


def load_config_from_env() -> CrawlerConfig:
    """Load configuration from environment variables."""
    import os

    categories_str = os.getenv("ARXIV_CATEGORIES")
    categories = categories_str.split(",") if categories_str else None

    return CrawlerConfig(
        categories=categories,
        max_workers=int(os.getenv("ARXIV_MAX_WORKERS", "10")),
        request_timeout=int(os.getenv("ARXIV_TIMEOUT", "30")),
        retry_attempts=int(os.getenv("ARXIV_RETRY_ATTEMPTS", "3")),
        retry_delay=float(os.getenv("ARXIV_RETRY_DELAY", "2.0")),
        rate_limit_delay=float(os.getenv("ARXIV_RATE_LIMIT_DELAY", "1.0")),
        days_back=int(os.getenv("ARXIV_DAYS_BACK", "1")),
        max_papers_per_category=int(os.getenv("ARXIV_MAX_PAPERS", "1000")),
        output_dir=os.getenv("ARXIV_OUTPUT_DIR", "dataset"),
        output_filename=os.getenv("ARXIV_OUTPUT_FILE", "arxiv_web.json"),
        log_level=os.getenv("ARXIV_LOG_LEVEL", "INFO"),
        log_file=os.getenv("ARXIV_LOG_FILE", "arxiv_web_crawler.log"),
    )


def get_category_url(category: str) -> str:
    """Get the URL for a specific arXiv category."""
    if category in CATEGORY_URLS:
        return CATEGORY_URLS[category]
    else:
        # Construct URL for unknown categories
        return f"https://arxiv.org/list/{category}/recent"


def validate_config(config: CrawlerConfig) -> bool:
    """Validate crawler configuration."""
    if not config.categories:
        raise ValueError("At least one category must be specified")

    if config.max_workers <= 0:
        raise ValueError("max_workers must be positive")

    if config.request_timeout <= 0:
        raise ValueError("request_timeout must be positive")

    if config.retry_attempts < 0:
        raise ValueError("retry_attempts must be non-negative")

    if config.days_back <= 0:
        raise ValueError("days_back must be positive")

    return True
