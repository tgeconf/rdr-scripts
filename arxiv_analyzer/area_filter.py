import argparse
import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from utils.llm import call_llm_model
from tqdm import tqdm

LOGGER = logging.getLogger(__name__)


DEFAULT_MODEL_NAME = os.environ.get("AREA_FILTER_MODEL", "deepseek-chat")
DEFAULT_MAX_WORKERS = os.environ.get("DEFAULT_MAX_WORKERS", 20)
DEFAULT_MAX_REFLECTION_ROUNDS = os.environ.get("DEFAULT_MAX_REFLECTION_ROUNDS", 3)

CATEGORY_DEFINITIONS: List[Dict[str, str]] = [
    {
        "name": "Foundation Models",
        "definition": (
            "Research on large-scale deep learning models-especially Transformer-based-trained on massive corpora to "
            "capture domain-general knowledge and serve as adaptable backbones for diverse downstream tasks across "
            "modalities and domains."
        ),
        "indicators": (
            "Large Language Models (LLM), Large Multimodal Models (LMM), pretraining-finetuning/instruction-tuning, "
            "scaling laws, alignment and safety for general-purpose use."
        ),
    },
    {
        "name": "Agent Architecture & Tool-Use Orchestration",
        "definition": (
            "Design and runtime control of single agents that plan, call tools/APIs, browse, execute code, and interface "
            "with external environments. Emphasis on planner-controller loops, schema/specs for tools, execution "
            "monitoring, error recovery, and reliability under partial observability."
        ),
        "indicators": (
            "Planning/execution loops, tool schemas and function calling, program-aided reasoning, self-verification/"
            "critique, guardrails & observability, latency/cost control in agent runtime."
        ),
    },
    {
        "name": "Agent Memory & Knowledge Systems",
        "definition": (
            "Models and systems enabling agents to form, store, retrieve, and evolve knowledge over time, supporting "
            "long-horizon tasks. Includes memory architectures (episodic/semantic/procedural), retrieval-augmented "
            "generation, knowledge evolution, credit assignment, and forgetting/updating policies."
        ),
        "indicators": (
            "RAG pipelines, hierarchical/long-term memory, memory consolidation & decay, entity/graph stores, "
            "evidence-grounded reasoning, experience replay for agents."
        ),
    },
    {
        "name": "Multi-Agent Systems & Collective Intelligence",
        "definition": (
            "Interaction, coordination, and competition among multiple agents, including mechanism design, communication "
            "protocols, team formation, consensus, and emergent behaviors in markets or simulations. Bridges game theory, "
            "RL, and distributed optimization."
        ),
        "indicators": (
            "Coordination/negotiation, auction/market mechanisms, self-play, social choice, role specialization, "
            "communication protocols, robustness to non-stationarity."
        ),
    },
    {
        "name": "Quantitative Trading Systems",
        "definition": (
            "End-to-end design and evaluation of systematic trading pipelines, covering alpha research, signal "
            "processing, execution, and post-trade analytics. Focus on automation, robustness, and production "
            "constraints."
        ),
        "indicators": (
            "Alpha generation & feature engineering, execution algorithms & slippage control, backtesting/simulation "
            "fidelity, production monitoring & risk gates."
        ),
    },
    {
        "name": "Risk Management & Pricing",
        "definition": (
            "Modeling, measuring, and controlling financial risks and valuing instruments (especially derivatives). "
            "Encompasses market/credit/liquidity risk, stochastic modeling, and stress testing under realistic market "
            "microstructure."
        ),
        "indicators": (
            "VaR/ES, scenario and stress testing, stochastic volatility & jump models, XVA, backtesting of risk models, "
            "model risk governance."
        ),
    },
    {
        "name": "Portfolio Management",
        "definition": (
            "Construction and lifecycle management of portfolios under explicit objectives and constraints, including "
            "allocation, rebalancing, and transaction cost modeling; integrates ML/RL with classical optimization."
        ),
        "indicators": (
            "Mean-variance & robust optimization, multi-factor models, hierarchical risk parity, RL for allocation/"
            "rebalancing, risk-adjusted performance (Sharpe/Sortino/Calmar)."
        ),
    },
    {
        "name": "others",
        "definition": (
            "Topics that do not materially align with the categories above. Use only when none of the definitions fit."
        ),
        "indicators": "No strong alignment with the defined categories.",
    },
]

CATEGORY_NAMES = {category["name"] for category in CATEGORY_DEFINITIONS}

PROMPT_CATEGORY_BLOCK = "\n".join(
    [
        f"{idx + 1}) {category['name']}\nDefinition: {category['definition']}\nKey Indicators: {category['indicators']}"
        for idx, category in enumerate(CATEGORY_DEFINITIONS)
    ]
)

PROMPT_TEMPLATE = """You are an experienced research analyst who classifies academic papers into strategic focus areas for review committees.
Use the category taxonomy below to assign one or more categories that reflect the paper's core contributions. If no category is a reasonable match, return only "others".

Category definitions:
{category_definitions}

Classification rules:
- Read the abstract and other metadata carefully.
- Choose at least one category name from the list and do not invent new labels.
- You may assign up to three categories; list them in descending order of relevance. If only one category applies, return a single-element list.
- Prefer categories focused on methodology or system design rather than application domain.
- Provide a brief justification that references specific evidence from the paper summary.
- Estimate confidence on a 0.0 to 1.0 scale.

Paper metadata:
Paper ID: {paper_id}
Title: {title}
Abstract: {abstract}
Primary Category: {primary_category}
All Categories: {categories}

{reviewer_feedback}
Respond with a compact JSON object using this schema:
{{
  "paper_id": "<paper_id>",
  "categories": ["<one or more of the predefined categories>"],
  "confidence": <float between 0 and 1>,
  "rationale": "<one or two sentences explaining the choice>"
}}

Return only the JSON object, without additional narration or code fences.
"""

REFLECTION_PROMPT_TEMPLATE = """You are a meticulous reviewer validating a paper classification against the provided taxonomy.

Category definitions:
{category_definitions}

Paper metadata:
Paper ID: {paper_id}
Title: {title}
Abstract: {abstract}
Primary Category: {primary_category}
All Categories: {categories}

Proposed classification (attempt {attempt_number}):
{classification_json}

Assess whether the proposed category set is well-justified. If the categories cover the paper's main contributions without adding unrelated areas, respond with verdict \"accept\". If the selection is incorrect, incomplete, or could be improved, respond with verdict \"revise\" and provide concise feedback highlighting what should change.

Return only a compact JSON object using this schema:
{{
  "verdict": "<accept|revise>",
  "feedback": "<short explanation or corrective guidance>"
}}

Do not add extra narration or code fences.
"""


@dataclass
class ClassificationResult:
    paper_id: str
    categories: List[str]
    confidence: float
    rationale: str
    raw_response: str = field(repr=False, default="")

    @property
    def primary_category(self) -> str:
        return self.categories[0] if self.categories else "others"

    @property
    def category(self) -> str:
        # Backwards-compatible alias for code that still expects a single category.
        return self.primary_category


class AreaFilter:
    """Classify arXiv papers into predefined research areas using an LLM."""

    def __init__(
        self,
        dataset_path: str,
        output_path: str,
        model_name: str = DEFAULT_MODEL_NAME,
        temperature: float = 0.1,
        request_interval: float = 1.0,
        resume: bool = True,
        max_workers: int = DEFAULT_MAX_WORKERS,
    ) -> None:
        self.dataset_path = dataset_path
        self.output_path = output_path
        self.model_name = model_name
        self.temperature = temperature
        self.request_interval = request_interval
        self.resume = resume
        self.max_workers = max(1, max_workers)
        self.max_reflection_rounds = max(1, DEFAULT_MAX_REFLECTION_ROUNDS)
        self._existing_results: Dict[str, ClassificationResult] = {}
        self._load_existing_results()

    def _load_existing_results(self) -> None:
        if not self.resume or not os.path.exists(self.output_path):
            return
        try:
            with open(self.output_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            for entry in data:
                if not isinstance(entry, dict):
                    continue
                raw_categories = entry.get("categories")
                if not raw_categories:
                    raw_categories = entry.get("category")
                categories = self._normalise_categories(raw_categories)
                confidence_raw = entry.get("confidence", 0.0)
                try:
                    confidence = float(confidence_raw)
                except (TypeError, ValueError):
                    confidence = 0.0
                result = ClassificationResult(
                    paper_id=entry.get("paper_id", ""),
                    categories=categories,
                    confidence=confidence,
                    rationale=entry.get("rationale", ""),
                )
                self._existing_results[result.paper_id] = result
            LOGGER.info("Loaded %d existing classification records", len(self._existing_results))
        except Exception as exc:
            LOGGER.warning("Failed to load existing results from %s: %s", self.output_path, exc)

    @staticmethod
    def _normalise_categories(candidate: Any) -> List[str]:
        if isinstance(candidate, str):
            stripped = candidate.strip()
            parsed_list: Any = None
            if stripped.startswith("[") and stripped.endswith("]"):
                try:
                    parsed_list = json.loads(stripped)
                except json.JSONDecodeError:
                    parsed_list = None
            if isinstance(parsed_list, list):
                raw_values = parsed_list
            elif "," in stripped:
                raw_values = [part.strip() for part in stripped.split(",")]
            else:
                raw_values = [candidate]
        elif isinstance(candidate, (list, tuple, set)):
            raw_values = list(candidate)
        else:
            raw_values = []

        seen = set()
        normalised: List[str] = []
        for item in raw_values:
            if item is None:
                continue
            name = str(item).strip()
            if not name:
                continue
            if name not in CATEGORY_NAMES:
                continue
            if name in seen:
                continue
            seen.add(name)
            normalised.append(name)

        if not normalised:
            normalised = ["others"]
        return normalised

    def _save_results(self, results: Dict[str, ClassificationResult]) -> None:
        serialisable = [
            {
                "paper_id": item.paper_id,
                "category": item.primary_category,
                "categories": item.categories,
                "confidence": item.confidence,
                "rationale": item.rationale,
            }
            for item in results.values()
        ]
        tmp_path = f"{self.output_path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(serialisable, handle, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self.output_path)
        LOGGER.debug("Persisted %d classification results to %s", len(serialisable), self.output_path)

    @staticmethod
    def _build_prompt(
        paper: Dict[str, Any],
        history: Optional[List[Tuple["ClassificationResult", str]]] = None,
    ) -> str:
        abstract = paper.get("abstract") or "Abstract not available."
        title = paper.get("title") or "Untitled"
        primary_category = paper.get("primary_category") or "Unknown"
        category_list = paper.get("categories") or "Unknown"

        feedback_section = ""
        if history:
            lines: List[str] = ["Reviewer feedback to address from earlier attempts:"]
            for idx, (prev_result, feedback) in enumerate(history, start=1):
                formatted_categories = ", ".join(f"'{name}'" for name in prev_result.categories)
                lines.append(
                    f"- Attempt {idx}: suggested categories [{formatted_categories}] "
                    f"(confidence {prev_result.confidence:.2f})."
                )
                lines.append(f"  Reviewer feedback: {feedback}")
            feedback_section = "\n".join(lines)

        return PROMPT_TEMPLATE.format(
            category_definitions=PROMPT_CATEGORY_BLOCK,
            paper_id=paper.get("paper_id", "N/A"),
            title=title.strip(),
            abstract=abstract.strip(),
            primary_category=str(primary_category),
            categories=str(category_list),
            reviewer_feedback=feedback_section,
        )

    @staticmethod
    def _strip_code_fences(response: str) -> str:
        fenced_match = re.search(r"```(?:json)?\s*(.*?)```", response, flags=re.DOTALL)
        if fenced_match:
            return fenced_match.group(1).strip()
        return response.strip()

    @staticmethod
    def _extract_json_blob(response: str) -> Optional[str]:
        match = re.search(r"\{.*\}", response, flags=re.DOTALL)
        if match:
            return match.group(0)
        return None

    def _throttle(self) -> None:
        if self.request_interval > 0:
            time.sleep(self.request_interval)

    @staticmethod
    def _format_classification_for_prompt(result: "ClassificationResult") -> str:
        payload = {
            "paper_id": result.paper_id,
            "categories": result.categories,
            "confidence": result.confidence,
            "rationale": result.rationale,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _parse_reflection_response(self, paper_id: str, response: str) -> Tuple[bool, str]:
        if not response:
            LOGGER.warning("Empty reflection response for paper %s", paper_id)
            return True, ""
        cleaned = self._strip_code_fences(response)
        json_blob = self._extract_json_blob(cleaned)
        if not json_blob:
            LOGGER.warning("No JSON object found in reflection response for paper %s: %s", paper_id, response)
            return True, ""
        try:
            payload = json.loads(json_blob)
        except json.JSONDecodeError as exc:
            LOGGER.warning("Failed to decode reflection JSON for paper %s: %s", paper_id, exc)
            return True, ""

        verdict_raw = (payload.get("verdict") or "").strip().lower()
        feedback = (payload.get("feedback") or "").strip()

        accepted_values = {"accept", "approved", "approve", "yes", "correct"}
        revise_values = {"revise", "reject", "no", "incorrect", "adjust"}

        if verdict_raw in accepted_values:
            return True, feedback
        if verdict_raw in revise_values:
            return False, feedback

        LOGGER.info(
            "Unexpected verdict '%s' in reflection for paper %s; treating as acceptance.",
            verdict_raw,
            paper_id,
        )
        return True, feedback

    def _reflect_classification(
        self,
        paper: Dict[str, Any],
        result: "ClassificationResult",
        attempt_number: int,
    ) -> Tuple[bool, str]:
        prompt = REFLECTION_PROMPT_TEMPLATE.format(
            category_definitions=PROMPT_CATEGORY_BLOCK,
            paper_id=paper.get("paper_id", "N/A"),
            title=(paper.get("title") or "Untitled").strip(),
            abstract=(paper.get("abstract") or "Abstract not available.").strip(),
            primary_category=str(paper.get("primary_category") or "Unknown"),
            categories=str(paper.get("categories") or "Unknown"),
            classification_json=self._format_classification_for_prompt(result),
            attempt_number=attempt_number,
        )
        LOGGER.debug(
            "Requesting reflection feedback for paper %s (attempt %d)",
            result.paper_id,
            attempt_number,
        )
        response = call_llm_model(self.model_name, prompt, temperature=self.temperature)
        self._throttle()
        accepted, feedback = self._parse_reflection_response(result.paper_id, response or "")
        if accepted:
            LOGGER.debug("Reflection accepted classification for paper %s", result.paper_id)
        else:
            LOGGER.debug("Reflection suggested revision for paper %s: %s", result.paper_id, feedback)
        return accepted, feedback

    def _parse_response(self, paper_id: str, response: str) -> Optional[ClassificationResult]:
        if not response:
            LOGGER.warning("Empty response for paper %s", paper_id)
            return None
        cleaned = self._strip_code_fences(response)
        json_blob = self._extract_json_blob(cleaned)
        if not json_blob:
            LOGGER.warning("No JSON object found in response for paper %s: %s", paper_id, response)
            return None
        try:
            payload = json.loads(json_blob)
        except json.JSONDecodeError as exc:
            LOGGER.warning("Failed to decode JSON for paper %s: %s", paper_id, exc)
            return None
        raw_categories = payload.get("categories")
        if not raw_categories:
            raw_categories = payload.get("category")
        categories = self._normalise_categories(raw_categories)
        if categories == ["others"] and raw_categories:
            if isinstance(raw_categories, (list, tuple, set)):
                raw_iterable = raw_categories
            else:
                raw_iterable = [raw_categories]
            invalid = [
                str(item).strip()
                for item in raw_iterable
                if str(item).strip() and str(item).strip() not in CATEGORY_NAMES
            ]
            if invalid:
                LOGGER.info(
                    "Model returned unknown categories %s for paper %s; defaulting to 'others'",
                    invalid,
                    paper_id,
                )
        confidence_raw = payload.get("confidence", 0.0)
        try:
            confidence = float(confidence_raw)
        except (TypeError, ValueError):
            LOGGER.debug("Using default confidence for paper %s due to invalid value %r", paper_id, confidence_raw)
            confidence = 0.0
        rationale = (payload.get("rationale") or "").strip()
        return ClassificationResult(
            paper_id=paper_id,
            categories=categories,
            confidence=confidence,
            rationale=rationale,
            raw_response=response,
        )

    def _classify_single_paper(self, paper: Dict[str, Any]) -> Optional[ClassificationResult]:
        paper_id = paper.get("paper_id")
        if not paper_id:
            LOGGER.warning("Skipping paper with missing paper_id: %s", paper)
            return None
        if paper_id in self._existing_results:
            LOGGER.debug("Skipping paper %s; already classified", paper_id)
            return self._existing_results[paper_id]

        attempt_history: List[Tuple["ClassificationResult", str]] = []
        last_result: Optional["ClassificationResult"] = None

        for attempt in range(1, self.max_reflection_rounds + 1):
            prompt = self._build_prompt(paper, attempt_history)
            LOGGER.debug("Submitting classification request for paper %s (attempt %d)", paper_id, attempt)
            response = call_llm_model(self.model_name, prompt, temperature=self.temperature)
            self._throttle()
            result = self._parse_response(paper_id, response or "")
            if not result:
                LOGGER.warning("Failed to classify paper %s on attempt %d", paper_id, attempt)
                continue

            last_result = result
            LOGGER.info(
                "Paper %s classified as %s (confidence %.2f) on attempt %d",
                paper_id,
                ", ".join(result.categories),
                result.confidence,
                attempt,
            )

            accepted, feedback = self._reflect_classification(paper, result, attempt)
            if accepted:
                LOGGER.info("Classification accepted for paper %s on attempt %d", paper_id, attempt)
                return result

            feedback_text = feedback or "Reviewer requested adjustment but did not provide detailed feedback."
            LOGGER.info(
                "Reflection requested revision for paper %s on attempt %d: %s",
                paper_id,
                attempt,
                feedback_text,
            )
            attempt_history.append((result, feedback_text))

        if last_result:
            fallback_feedback = attempt_history[-1][1] if attempt_history else "No reviewer feedback captured."
            LOGGER.warning(
                "Defaulting paper %s to 'others' after %d unsuccessful reflection rounds",
                paper_id,
                self.max_reflection_rounds,
            )
            return ClassificationResult(
                paper_id=paper_id,
                categories=["others"],
                confidence=0.0,
                rationale=(
                    "Fallback classification after repeated reviewer disagreement. "
                    f"Latest reviewer feedback: {fallback_feedback}"
                ),
                raw_response=last_result.raw_response,
            )

        LOGGER.warning(
            "Unable to obtain a valid classification for paper %s after %d attempts",
            paper_id,
            self.max_reflection_rounds,
        )
        return None

    def classify(self) -> Dict[str, ClassificationResult]:
        with open(self.dataset_path, "r", encoding="utf-8") as handle:
            papers: List[Dict[str, Any]] = json.load(handle)
        LOGGER.info("Loaded %d papers from %s", len(papers), self.dataset_path)

        results = dict(self._existing_results)
        pending: List[Dict[str, Any]] = [
            paper for paper in papers if paper.get("paper_id") not in results
        ]

        if not pending:
            LOGGER.info("No new papers to classify; %d records already available", len(results))
            return results

        LOGGER.info(
            "Classifying %d new papers using %d worker(s)",
            len(pending),
            self.max_workers,
        )

        if self.max_workers == 1:
            for paper in pending:
                result = self._classify_single_paper(paper)
                if result:
                    results[result.paper_id] = result
                    self._existing_results[result.paper_id] = result
                    self._save_results(results)
            LOGGER.info("Completed classification for %d papers", len(results))
            return results

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_map = {executor.submit(self._classify_single_paper, paper): paper for paper in pending}
            
            progress_bar = tqdm(total=len(future_map), desc="Classifying papers", unit="paper")
            
            for future in as_completed(future_map):
                paper = future_map[future]
                paper_id = paper.get("paper_id", "N/A")
                try:
                    result = future.result()
                except Exception as exc:  # pragma: no cover - defensive logging
                    LOGGER.error("Unhandled error while classifying paper %s: %s", paper_id, exc)
                    progress_bar.update(1)
                    continue
                if not result:
                    progress_bar.update(1)
                    continue
                results[result.paper_id] = result
                self._existing_results[result.paper_id] = result
                self._save_results(results)
                
                progress_bar.update(1)
            
            progress_bar.close()

        LOGGER.info("Completed classification for %d papers", len(results))
        return results


def _configure_logging(verbosity: int) -> None:
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Classify arXiv papers into strategic areas using an LLM.",
    )
    parser.add_argument(
        "--dataset",
        default=os.path.join("dataset", "arxiv_web.json"),
        help="Path to the arXiv dataset JSON file.",
    )
    parser.add_argument(
        "--output",
        default=os.path.join("dataset", "arxiv_area_classification.json"),
        help="Path to the output classification JSON file.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL_NAME,
        help="LLM model identifier passed to call_llm_model.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.1,
        help="Sampling temperature for the LLM.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Delay (in seconds) between consecutive LLM requests.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_MAX_WORKERS,
        help="Maximum number of concurrent classification workers.",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Ignore existing output file and classify all papers from scratch.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase log verbosity (can be used twice).",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    _configure_logging(args.verbose)
    workers = max(1, args.workers)

    filter_engine = AreaFilter(
        dataset_path=args.dataset,
        output_path=args.output,
        model_name=args.model,
        temperature=args.temperature,
        request_interval=args.interval,
        resume=not args.no_resume,
        max_workers=workers,
    )
    filter_engine.classify()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
