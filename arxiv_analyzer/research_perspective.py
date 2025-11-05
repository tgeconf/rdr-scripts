import argparse
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from utils.llm import call_llm_model

LOGGER = logging.getLogger(__name__)


DEFAULT_MODEL_NAME = os.environ.get("PERSPECTIVE_MODEL", "deepseek-reasoner")
DEFAULT_REFLECTOR_MODEL_NAME = os.environ.get(
    "PERSPECTIVE_REFLECTOR_MODEL", DEFAULT_MODEL_NAME
)
DEFAULT_TEMPERATURE = 0.0
DEFAULT_REFLECTION_TEMPERATURE = 0.0
DEFAULT_REQUEST_INTERVAL = 1.0
DEFAULT_MAX_ROUNDS = os.environ.get("DEFAULT_MAX_REFLECTION_ROUNDS", 3)
DEFAULT_MAX_WORKERS = os.environ.get("DEFAULT_MAX_WORKERS", 10)


@dataclass(frozen=True)
class PerspectiveDefinition:
    label: str
    coverage: str
    examples: str


PERSPECTIVE_TAXONOMY: Dict[str, List[PerspectiveDefinition]] = {
    "Foundation Models": [
        PerspectiveDefinition(
            label="Data & Inputs (I)",
            coverage=(
                "Coverage: Raw corpora and sensor streams; tokenization/patchification; multimodal alignment; "
                "data quality, filtering, deduplication, and augmentation."
            ),
            examples=(
                "Typical Examples: Web-scale text/image/video/audio, code, math; vision tokens/patches, spectrograms; "
                "tokenizer design (BPE/Unigram), visual tokenizers, latent tokens; synthetic data pipelines."
            ),
        ),
        PerspectiveDefinition(
            label="Architecture & Modeling (M)",
            coverage=(
                "Coverage: Backbone design and parameterization; attention variants; mixture-of-experts; multimodal "
                "fusion; sparse/structured computation; long-context methods."
            ),
            examples=(
                "Typical Examples: Decoder-only vs. encoder–decoder; MoE routing; Perceiver-style fusion; state-space "
                "models; linear attention; memory-augmented transformers."
            ),
        ),
        PerspectiveDefinition(
            label="Objectives & Learning Signals (O)",
            coverage=(
                "Coverage: Pretraining losses and auxiliary heads; instruction/objective design; preference learning; "
                "safety/harms constraints in the loss."
            ),
            examples=(
                "Typical Examples: Next-token prediction, masked objectives, contrastive learning; RLHF/DPO/ORPO; "
                "multimodal alignment losses; spec-violation penalties."
            ),
        ),
        PerspectiveDefinition(
            label="Optimization & Training Recipe (R)",
            coverage=(
                "Coverage: Optimizers, schedulers, parallelism strategies, curriculum, mixed-precision, checkpointing, "
                "stabilization techniques."
            ),
            examples=(
                "Typical Examples: AdamW/Lion; cosine decay; ZeRO/FS/TP/PP; data curriculum; gradient clipping; "
                "activation/weight scaling; QK-norm."
            ),
        ),
        PerspectiveDefinition(
            label="Inference & Systems (S)",
            coverage=(
                "Coverage: Serving stacks, batching, speculative decoding, caching, quantization, distillation, "
                "cost/latency/throughput trade-offs."
            ),
            examples=(
                "Typical Examples: KV cache management, tensor/graph compilers, 4/8-bit quantization, mixture "
                "distillation, speculative decoding pipelines."
            ),
        ),
        PerspectiveDefinition(
            label="Alignment, Safety & Governance (A)",
            coverage=(
                "Coverage: Red-teaming, safety tuning, policy enforcement, controllability, provenance, licensing."
            ),
            examples=(
                "Typical Examples: System prompt hardening, refusal training, safety classifiers/filters, watermarking, "
                "data governance."
            ),
        ),
        PerspectiveDefinition(
            label="Evaluation & Benchmarks (E)",
            coverage=(
                "Coverage: General, domain, and adversarial evaluations; multimodal and long-horizon tests; "
                "calibration and uncertainty."
            ),
            examples=(
                "Typical Examples: Reasoning/coding/multimodal suites, grounding tests, long-context recall, "
                "toxicity/hallucination audits, cost–quality frontiers."
            ),
        ),
    ],
    "Agent Architecture & Tool-Use Orchestration": [
        PerspectiveDefinition(
            label="Task & Environment Specification (T)",
            coverage=(
                "Coverage: Goal formalization, constraints, interfaces to web/OS/APIs/sandboxes."
            ),
            examples=(
                "Typical Examples: Tool schemas, OpenAPI/Function-Calling specs, sandboxed code exec, browser automation."
            ),
        ),
        PerspectiveDefinition(
            label="Planning & Control Loops (P)",
            coverage=(
                "Coverage: Decomposition, hierarchical planning, reflection/verification, interruption and replanning."
            ),
            examples=(
                "Typical Examples: ReAct/Tree-of-Thoughts, hierarchical controllers, self-critique, model-based control."
            ),
        ),
        PerspectiveDefinition(
            label="Tool Invocation & Program Synthesis (U)",
            coverage=(
                "Coverage: Tool selection, argument grounding, composition, and program generation to orchestrate tools."
            ),
            examples=(
                "Typical Examples: Multi-tool routing, code-gen for pipelines, schema-constrained decoding."
            ),
        ),
        PerspectiveDefinition(
            label="Execution Monitoring & Error Recovery (X)",
            coverage=(
                "Coverage: Runtime observability, exception handling, timeouts, retries, rollbacks, transactional semantics."
            ),
            examples=(
                "Typical Examples: Guardrails, circuit breakers, step validators, idempotent actions."
            ),
        ),
        PerspectiveDefinition(
            label="Latency/Cost/Quality Trade-offs (C)",
            coverage=(
                "Coverage: Model routing, caching, speculative plans, partial results, dynamic depth-of-thought."
            ),
            examples=(
                "Typical Examples: Multi-model routing (small↔large), response caching, adaptive reasoning depth."
            ),
        ),
        PerspectiveDefinition(
            label="Security & Compliance (F)",
            coverage=(
                "Coverage: Permissioning, data boundaries, least privilege, audit trails."
            ),
            examples=(
                "Typical Examples: OAuth scopes, PII masking, policy engines, immutable logs."
            ),
        ),
        PerspectiveDefinition(
            label="Agent Evaluation (E)",
            coverage=(
                "Coverage: Task success, robustness to tool failures, reproducibility, reliability under drift."
            ),
            examples=(
                "Typical Examples: End-to-end success rate, tool-call precision/recall, step efficiency, ablations."
            ),
        ),
    ],
    "Agent Memory & Knowledge Systems": [
        PerspectiveDefinition(
            label="Memory Typology (M)",
            coverage=(
                "Coverage: Episodic, semantic, procedural, and working memory roles and interfaces."
            ),
            examples=(
                "Typical Examples: Session logs (episodic), entity/graph stores (semantic), skills/tools (procedural)."
            ),
        ),
        PerspectiveDefinition(
            label="Indexing & Retrieval (R)",
            coverage=(
                "Coverage: Vector/graph/hybrid indices; multi-hop and query planning; grounding and citation."
            ),
            examples=(
                "Typical Examples: RAG pipelines, retrieval fusion, multi-vector stores, evidence tracking."
            ),
        ),
        PerspectiveDefinition(
            label="Writing & Consolidation (W)",
            coverage=(
                "Coverage: What/when/how to write; summarization, distillation, and compression; cross-episode consolidation."
            ),
            examples=(
                "Typical Examples: Saliency-triggered writes, nightly consolidation jobs, memory compression."
            ),
        ),
        PerspectiveDefinition(
            label="Evolution & Update Policies (E)",
            coverage=(
                "Coverage: Forgetting/decay, conflict resolution, versioning, provenance."
            ),
            examples=(
                "Typical Examples: TTLs/decay kernels, provenance graphs, counterfactual updates."
            ),
        ),
        PerspectiveDefinition(
            label="Credit Assignment & Attribution (C)",
            coverage=(
                "Coverage: Linking outcomes to memory traces; reward shaping for retrieval/write policies."
            ),
            examples=(
                "Typical Examples: Success-trace linking, write-policy RL, hindsight credit."
            ),
        ),
        PerspectiveDefinition(
            label="Privacy & Governance (G)",
            coverage=(
                "Coverage: Access control, tenant isolation, redaction, right-to-forget."
            ),
            examples=(
                "Typical Examples: Row/field-level ACLs, encryption at rest/in transit, redaction filters."
            ),
        ),
        PerspectiveDefinition(
            label="Memory Evaluation (V)",
            coverage=(
                "Coverage: Helpfulness vs. hallucination, coverage, staleness, latency."
            ),
            examples=(
                "Typical Examples: Evidence-grounded QA, update-lag metrics, end-task lift from memory."
            ),
        ),
    ],
    "Multi-Agent Systems & Collective Intelligence": [
        PerspectiveDefinition(
            label="Interaction Protocols (P)",
            coverage=(
                "Coverage: Communication languages, negotiation/coordination rules, commitments."
            ),
            examples=(
                "Typical Examples: Auction protocols, contract nets, differentiable communication."
            ),
        ),
        PerspectiveDefinition(
            label="Team Formation & Role Specialization (S)",
            coverage=(
                "Coverage: Role assignment, task allocation, dynamic coalition formation."
            ),
            examples=(
                "Typical Examples: Skill-based matching, leader–worker hierarchies, market-based allocation."
            ),
        ),
        PerspectiveDefinition(
            label="Learning Dynamics (L)",
            coverage=(
                "Coverage: Self-play, opponent modeling, equilibrium learning, non-stationarity handling."
            ),
            examples=(
                "Typical Examples: Multi-agent RL (MARL), fictitious play, population-based training."
            ),
        ),
        PerspectiveDefinition(
            label="Mechanism & Incentive Design (M)",
            coverage=(
                "Coverage: Rules that elicit truthful signals and efficient outcomes under strategic behavior."
            ),
            examples=(
                "Typical Examples: VCG mechanisms, scoring rules, budget-balanced exchanges."
            ),
        ),
        PerspectiveDefinition(
            label="Robustness & Safety (R)",
            coverage=(
                "Coverage: Adversarial agents, collusion, sybil attacks, resilience to failures."
            ),
            examples=(
                "Typical Examples: Byzantine robustness, coalition detection, anomaly agents."
            ),
        ),
        PerspectiveDefinition(
            label="Simulation & Testbeds (T)",
            coverage=(
                "Coverage: Environment realism, partial observability, market/game simulators."
            ),
            examples=(
                "Typical Examples: Gridworld/market simulators, web-scale user simulations, ops digital twins."
            ),
        ),
        PerspectiveDefinition(
            label="Collective Evaluation (E)",
            coverage=(
                "Coverage: Social welfare, fairness, resource efficiency, emergent behaviors."
            ),
            examples=(
                "Typical Examples: Welfare/regret metrics, consensus rates, diversity–performance trade-offs."
            ),
        ),
    ],
    "Quantitative Trading Systems": [
        PerspectiveDefinition(
            label="Data Engineering & Curation (D)",
            coverage=(
                "Coverage: Market/alt-data ingestion, cleaning, corporate actions, survivorship bias control."
            ),
            examples=(
                "Typical Examples: Tick/LOB normalization, point-in-time pipelines, vendor cross-checks."
            ),
        ),
        PerspectiveDefinition(
            label="Signal Research & Alpha Modeling (A)",
            coverage=(
                "Coverage: Feature discovery, stationarity tests, regime awareness, leakage control."
            ),
            examples=(
                "Typical Examples: Cross-sectional and time-series alphas, ML for return/vol forecasting, causal filters."
            ),
        ),
        PerspectiveDefinition(
            label="Strategy Construction (S)",
            coverage=(
                "Coverage: Combining signals into tradeable policies; position sizing; constraints."
            ),
            examples=(
                "Typical Examples: Meta-learners, ensemble stacking, Kelly/convex risk budgets."
            ),
        ),
        PerspectiveDefinition(
            label="Execution & Microstructure (E)",
            coverage=(
                "Coverage: Order scheduling, venue selection, slippage modeling, TCA."
            ),
            examples=(
                "Typical Examples: POV/TWAP/VWAP, smart order routing, queue position models."
            ),
        ),
        PerspectiveDefinition(
            label="Backtesting & Simulation Fidelity (B)",
            coverage=(
                "Coverage: Event-driven sims, latency/impact modeling, robustness tests."
            ),
            examples=(
                "Typical Examples: Intraday simulators, Monte Carlo pathing, randomized market frictions."
            ),
        ),
        PerspectiveDefinition(
            label="Real-time Risk & Controls (R)",
            coverage=(
                "Coverage: Pre-/in-/post-trade risk gates, kill switches, exposure/limit frameworks."
            ),
            examples=(
                "Typical Examples: Max drawdown guards, inventory caps, fat-finger checks."
            ),
        ),
        PerspectiveDefinition(
            label="Production Ops & Monitoring (O)",
            coverage=(
                "Coverage: Deployment, observability, incident response, configuration governance."
            ),
            examples=(
                "Typical Examples: Canary releases, feature flags, audit trails, disaster recovery drills."
            ),
        ),
    ],
    "Risk Management & Pricing": [
        PerspectiveDefinition(
            label="Risk Identification & Taxonomy (I)",
            coverage=(
                "Coverage: Market/credit/liquidity/operational/model risks; concentration and contagion."
            ),
            examples=(
                "Typical Examples: Factor decompositions, wrong-way risk, basis/roll risks."
            ),
        ),
        PerspectiveDefinition(
            label="Stochastic Modeling & Calibration (M)",
            coverage=(
                "Coverage: Process selection and parameter estimation for prices/vol/rates; calibration stability."
            ),
            examples=(
                "Typical Examples: Local/stochastic vol, Heston/HJM, jump-diffusions, particle filters."
            ),
        ),
        PerspectiveDefinition(
            label="Measurement & Aggregation (Q)",
            coverage=(
                "Coverage: VaR/ES and scenario metrics; horizon and confidence handling; risk aggregation."
            ),
            examples=(
                "Typical Examples: Historical/simulated VaR, ES, copulas, factor aggregation."
            ),
        ),
        PerspectiveDefinition(
            label="Stress Testing & Scenarios (S)",
            coverage=(
                "Coverage: Historical replays, hypothetical shocks, macro/market linkages."
            ),
            examples=(
                "Typical Examples: 2008/2020 replays, liquidity freezes, rate shocks, volatility spikes."
            ),
        ),
        PerspectiveDefinition(
            label="Pricing & XVA (P)",
            coverage=(
                "Coverage: Instrument valuation, counterparty/funding/capital adjustments."
            ),
            examples=(
                "Typical Examples: CVA/DVA/FVA/MVA/KVA, CSA modeling, collateral optimization."
            ),
        ),
        PerspectiveDefinition(
            label="Hedging & Risk Transfer (H)",
            coverage=(
                "Coverage: Static/dynamic hedges, basis risk, transaction costs, re-hedge policies."
            ),
            examples=(
                "Typical Examples: Delta–gamma–vega hedging, proxy hedges, transaction-cost-aware rebalancing."
            ),
        ),
        PerspectiveDefinition(
            label="Model Risk & Governance (G)",
            coverage=(
                "Coverage: Validation, challenger models, monitoring, documentation and audits."
            ),
            examples=(
                "Typical Examples: Benchmarking, backtesting drift, limitations registers, SR-11-7 style controls."
            ),
        ),
    ],
    "Portfolio Management": [
        PerspectiveDefinition(
            label="Objectives & Constraints (O)",
            coverage=(
                "Coverage: Utility specification, mandates, drawdown/turnover/ESG/regulatory constraints."
            ),
            examples=(
                "Typical Examples: Mean–variance vs. drawdown-aware utilities, leverage and shorting limits."
            ),
        ),
        PerspectiveDefinition(
            label="Forecasts & Estimation Risk (F)",
            coverage=(
                "Coverage: Return/vol/correlation forecasts; shrinkage/robust stats; parameter uncertainty."
            ),
            examples=(
                "Typical Examples: Bayesian/shrinkage estimators, regime-switching covariances, resampling."
            ),
        ),
        PerspectiveDefinition(
            label="Allocation & Construction (A)",
            coverage=(
                "Coverage: Optimization paradigms and heuristics; risk parity and factor budgeting."
            ),
            examples=(
                "Typical Examples: Mean–variance/robust/Black–Litterman, HRP, minimum-variance, factor tilts."
            ),
        ),
        PerspectiveDefinition(
            label="Rebalancing & Trading Frictions (R)",
            coverage=(
                "Coverage: Rebalance triggers, transaction-cost models, taxes, liquidity."
            ),
            examples=(
                "Typical Examples: No-trade regions, AC/TCost models, tax-aware lot selection."
            ),
        ),
        PerspectiveDefinition(
            label="Multi-Asset & Constraints Integration (M)",
            coverage=(
                "Coverage: Cross-asset modeling, derivatives overlays, liability-driven investing (LDI)."
            ),
            examples=(
                "Typical Examples: Equity/rates/credit/FX/commodities stack, options overlays, duration matching."
            ),
        ),
        PerspectiveDefinition(
            label="Performance Measurement & Attribution (P)",
            coverage=(
                "Coverage: Absolute/relative performance; factor and interaction effects; risk-adjusted metrics."
            ),
            examples=(
                "Typical Examples: Brinson attribution, multi-factor attribution, Sharpe/Sortino/Calmar."
            ),
        ),
        PerspectiveDefinition(
            label="Automation, Monitoring & Governance (G)",
            coverage=(
                "Coverage: Policy engines, breach detection, documentation, stewardship."
            ),
            examples=(
                "Typical Examples: IPS enforcement, drift/limit monitors, change management, audit trails."
            ),
        ),
    ],
}


ANALYSIS_PROMPT_TEMPLATE = """You are a senior research analyst producing detailed perspective analysis for internal reviews.
The paper has been categorized under "{area}". Use the perspective taxonomy below to structure the analysis.

Perspective taxonomy:
{perspective_block}

Paper metadata:
- Title: {title}
- Abstract: {abstract}
- Primary arXiv Category: {primary_category}
- Assigned Strategic Areas: {categories}

Can you analyze the paper contents according to the following perspectives:
{perspective_list}
After analysis, please identify each of the perspectives in the paper, and return the answer in the following format:
{{"perspective 1": plain text, "perspective 2": plain text, "perspective 3": plain text, ...}}

Strict instructions:
- Use exactly the perspective labels shown above as the JSON keys (matching capitalization and punctuation).
- Provide concise, evidence-backed explanations grounded in the abstract and metadata.
- Do not add extra keys, narrative text, or code fences.
{revision_guidance}
"""


REFLECTION_PROMPT_TEMPLATE = """You are a meticulous reviewer validating a research perspective analysis.

Perspective taxonomy for "{area}":
{perspective_block}

Paper metadata:
- Title: {title}
- Abstract: {abstract}
- Primary arXiv Category: {primary_category}
- Assigned Strategic Areas: {categories}

Proposed analysis (attempt {attempt_number}):
{analysis_json}

Assess whether each perspective explanation is relevant, faithful to the paper, and aligned with the taxonomy. If the analysis is acceptable, respond with verdict "accept". If not, respond with verdict "revise" and provide targeted guidance to improve the analysis.

Return only a compact JSON object:
{{"verdict": "<accept|revise>", "feedback": "<short explanation>"}}
"""


@dataclass
class ReflectionResult:
    verdict: str
    feedback: str
    raw_response: str = field(repr=False)


@dataclass
class AnalysisAttempt:
    attempt_number: int
    analysis: Optional[Dict[str, str]]
    analysis_raw: str
    reflection: Optional[ReflectionResult] = None
    error_feedback: Optional[str] = None


@dataclass
class PerspectiveAnalysisResult:
    paper_id: str
    area: str
    categories: List[str]
    title: str
    analysis: Optional[Dict[str, str]]
    reflection: Optional[ReflectionResult]
    attempts: List[AnalysisAttempt]


class ResearchPerspectiveAnalyzer:
    def __init__(
        self,
        classification_path: str,
        paper_dataset_path: str,
        output_path: str,
        model_name: str = DEFAULT_MODEL_NAME,
        reflector_model_name: str = DEFAULT_REFLECTOR_MODEL_NAME,
        temperature: float = DEFAULT_TEMPERATURE,
        reflection_temperature: float = DEFAULT_REFLECTION_TEMPERATURE,
        max_rounds: int = DEFAULT_MAX_ROUNDS,
        request_interval: float = DEFAULT_REQUEST_INTERVAL,
        max_workers: int = DEFAULT_MAX_WORKERS,
    ) -> None:
        self.classification_path = classification_path
        self.paper_dataset_path = paper_dataset_path
        self.output_path = output_path
        self.model_name = model_name
        self.reflector_model_name = reflector_model_name
        self.temperature = temperature
        self.reflection_temperature = reflection_temperature
        self.max_rounds = max(1, max_rounds)
        self.request_interval = max(0.0, request_interval)
        self.max_workers = max(1, max_workers)

    @staticmethod
    def _normalise_categories(candidate: Any) -> List[str]:
        if isinstance(candidate, str):
            stripped = candidate.strip()
            parsed: Any = None
            if stripped.startswith("[") and stripped.endswith("]"):
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError:
                    parsed = None
            if isinstance(parsed, list):
                raw_values = parsed
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
            if name in seen:
                continue
            seen.add(name)
            normalised.append(name)

        return normalised

    def run(self) -> List[PerspectiveAnalysisResult]:
        papers = self._prepare_papers()
        total = len(papers)
        if total == 0:
            self._write_results([])
            return []

        indexed_papers: List[Tuple[int, Dict[str, Any], str, List[str]]] = [
            (idx, paper, category, assigned_categories)
            for idx, (paper, category, assigned_categories) in enumerate(papers, start=1)
        ]

        results_with_index: List[Tuple[int, PerspectiveAnalysisResult]] = []

        if self.max_workers == 1:
            for idx, paper, category, assigned_categories in indexed_papers:
                LOGGER.info(
                    "Analyzing paper %s (%d/%d) under area '%s' (assigned areas: %s)",
                    paper.get("paper_id", "N/A"),
                    idx,
                    total,
                    category,
                    ", ".join(assigned_categories) if assigned_categories else "None",
                )
                result = self._analyze_single_paper(paper, category, assigned_categories)
                if result is not None:
                    results_with_index.append((idx, result))
                else:
                    LOGGER.warning(
                        "Failed to obtain analysis for paper %s",
                        paper.get("paper_id", "N/A"),
                    )
        else:
            LOGGER.info(
                "Analyzing %d papers using %d worker(s)",
                total,
                self.max_workers,
            )
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                progress_bar = tqdm(total=len(indexed_papers), desc="Analyzing papers", unit="paper")

                future_map = {
                    executor.submit(self._analyze_single_paper, paper, category, assigned_categories): (
                        idx,
                        paper,
                        category,
                        assigned_categories,
                    )
                    for idx, paper, category, assigned_categories in indexed_papers
                }
                for future in as_completed(future_map):
                    idx, paper, category, assigned_categories = future_map[future]
                    paper_id = paper.get("paper_id", "N/A")
                    try:
                        result = future.result()
                    except Exception as exc:  # pragma: no cover - defensive logging
                        LOGGER.error(
                            "Unhandled error while analyzing paper %s under area '%s': %s",
                            paper_id,
                            category,
                            exc,
                        )
                        progress_bar.update(1)
                        continue
                    if result is None:
                        LOGGER.warning(
                            "Failed to obtain analysis for paper %s",
                            paper_id,
                        )
                        progress_bar.update(1)
                        continue
                    results_with_index.append((idx, result))
                    progress_bar.update(1)

                progress_bar.close()

        results_with_index.sort(key=lambda item: item[0])
        results = [item[1] for item in results_with_index]
        self._write_results(results)
        return results

    def _prepare_papers(self) -> List[Tuple[Dict[str, Any], str, List[str]]]:
        with open(self.classification_path, "r", encoding="utf-8") as fp:
            classifications = json.load(fp)
        with open(self.paper_dataset_path, "r", encoding="utf-8") as fp:
            papers = json.load(fp)

        paper_map: Dict[str, Dict[str, Any]] = {
            str(item.get("paper_id")): item for item in papers if item.get("paper_id")
        }

        filtered: List[Tuple[Dict[str, Any], str, List[str]]] = []
        for entry in classifications:
            paper_id = str(entry.get("paper_id"))
            if not paper_id:
                continue
            if entry.get("category") == "others":
                continue
            raw_categories = entry.get("categories")
            if not raw_categories:
                raw_categories = entry.get("category")
            categories = self._normalise_categories(raw_categories)
            if not categories:
                continue
            assigned_categories = list(categories)
            paper_entry = paper_map.get(paper_id)
            if not paper_entry:
                LOGGER.warning(
                    "Paper metadata not found for paper_id %s, skipping perspective analysis",
                    paper_id,
                )
                continue
            for category in assigned_categories:
                if category == "others":
                    continue
                taxonomy = PERSPECTIVE_TAXONOMY.get(category)
                if not taxonomy:
                    LOGGER.warning(
                        "Skipping paper %s due to unknown category '%s'", paper_id, category
                    )
                    continue
                filtered.append((paper_entry, category, assigned_categories))

        filtered.sort(
            key=lambda item: (
                item[0].get("paper_id", ""),
                item[2].index(item[1]) if item[1] in item[2] else 0,
            )
        )

        LOGGER.info(
            "Prepared %d paper-area assignments for perspective analysis (from %d classification records)",
            len(filtered),
            len(classifications),
        )
        return filtered

    def _throttle(self) -> None:
        if self.request_interval > 0:
            time.sleep(self.request_interval)

    def _build_revision_guidance(self, history: List[AnalysisAttempt]) -> str:
        if not history:
            return ""
        lines = ["Previous reviewer feedback to address:"]
        for attempt in history:
            if attempt.reflection and attempt.reflection.feedback:
                lines.append(
                    f"- Attempt {attempt.attempt_number}: {attempt.reflection.feedback.strip()}"
                )
            elif attempt.error_feedback:
                lines.append(
                    f"- Attempt {attempt.attempt_number}: {attempt.error_feedback.strip()}"
                )
        return "\n".join(lines)

    def _format_perspective_block(self, area: str) -> str:
        definitions = PERSPECTIVE_TAXONOMY.get(area, [])
        lines: List[str] = []
        for idx, perspective in enumerate(definitions, start=1):
            lines.append(
                f"{idx}) {perspective.label}\n{perspective.coverage}\n{perspective.examples}"
            )
        return "\n".join(lines)

    def _format_perspective_list(self, area: str) -> str:
        definitions = PERSPECTIVE_TAXONOMY.get(area, [])
        lines = [f"({idx}) {perspective.label}" for idx, perspective in enumerate(definitions, start=1)]
        return "\n".join(lines)

    def _build_analysis_prompt(
        self,
        paper: Dict[str, Any],
        area: str,
        assigned_categories: List[str],
        history: List[AnalysisAttempt],
    ) -> str:
        abstract = (paper.get("abstract") or "Abstract not available.").strip()
        title = (paper.get("title") or "Untitled").strip()
        paper_id = paper.get("paper_id", "N/A")
        primary_category = paper.get("primary_category") or "Unknown"
        categories_text = ", ".join(assigned_categories) if assigned_categories else "Unknown"
        perspective_block = self._format_perspective_block(area)
        perspective_list = self._format_perspective_list(area)
        revision_guidance = self._build_revision_guidance(history)

        return ANALYSIS_PROMPT_TEMPLATE.format(
            area=area,
            perspective_block=perspective_block,
            paper_id=paper_id,
            title=title,
            abstract=abstract,
            primary_category=primary_category,
            categories=categories_text,
            perspective_list=perspective_list,
            revision_guidance=revision_guidance,
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

    def _parse_analysis_response(
        self,
        paper_id: str,
        area: str,
        response: str,
    ) -> Tuple[Optional[Dict[str, str]], Optional[str]]:
        if not response:
            return None, "The previous response was empty. Please return valid JSON."

        cleaned = self._strip_code_fences(response)
        json_blob = self._extract_json_blob(cleaned)
        if not json_blob:
            return (
                None,
                "The previous response did not contain a JSON object. Return only the JSON dictionary specified.",
            )
        try:
            payload = json.loads(json_blob)
        except json.JSONDecodeError as exc:
            LOGGER.warning("JSON decode error for paper %s: %s", paper_id, exc)
            return (
                None,
                "The previous response contained invalid JSON. Return a valid JSON object with the required keys.",
            )

        if not isinstance(payload, dict):
            return (
                None,
                "The response must be a JSON object mapping each perspective label to its analysis.",
            )

        expected_labels = {definition.label for definition in PERSPECTIVE_TAXONOMY[area]}
        actual_labels = set(payload.keys())
        missing = expected_labels - actual_labels
        extra = actual_labels - expected_labels

        if missing or extra:
            messages: List[str] = []
            if missing:
                messages.append(
                    "Missing perspectives: " + ", ".join(sorted(missing))
                )
            if extra:
                messages.append(
                    "Unexpected perspectives: " + ", ".join(sorted(extra))
                )
            messages.append("Use exactly the provided perspective labels as JSON keys.")
            return None, " ".join(messages)

        normalized: Dict[str, str] = {}
        for label in expected_labels:
            value = payload.get(label, "")
            if not isinstance(value, str):
                return (
                    None,
                    f"The value for '{label}' must be a string describing the perspective analysis.",
                )
            normalized[label] = value.strip()

        return normalized, None

    def _format_analysis_for_reflection(
        self,
        analysis: Dict[str, str],
    ) -> str:
        return json.dumps(analysis, ensure_ascii=False, indent=2)

    def _parse_reflection_response(self, response: str) -> Optional[ReflectionResult]:
        if not response:
            return ReflectionResult(verdict="accept", feedback="", raw_response=response)
        cleaned = self._strip_code_fences(response)
        json_blob = self._extract_json_blob(cleaned)
        if not json_blob:
            return ReflectionResult(verdict="accept", feedback="", raw_response=response)
        try:
            payload = json.loads(json_blob)
        except json.JSONDecodeError as exc:
            LOGGER.warning("Failed to decode reflection response: %s", exc)
            return ReflectionResult(verdict="accept", feedback="", raw_response=response)

        verdict_raw = str(payload.get("verdict", "")).strip().lower()
        feedback = str(payload.get("feedback", "")).strip()
        accepted_values = {"accept", "approved", "approve", "yes", "correct"}
        revise_values = {"revise", "reject", "no", "incorrect", "adjust"}

        if verdict_raw in accepted_values:
            verdict = "accept"
        elif verdict_raw in revise_values:
            verdict = "revise"
        else:
            verdict = "accept"
            LOGGER.info(
                "Unexpected reflection verdict '%s'; defaulting to accept", verdict_raw
            )
        return ReflectionResult(verdict=verdict, feedback=feedback, raw_response=response)

    def _reflect_analysis(
        self,
        paper: Dict[str, Any],
        area: str,
        assigned_categories: List[str],
        analysis: Dict[str, str],
        attempt_number: int,
    ) -> ReflectionResult:
        abstract = (paper.get("abstract") or "Abstract not available.").strip()
        title = (paper.get("title") or "Untitled").strip()
        paper_id = paper.get("paper_id", "N/A")
        primary_category = paper.get("primary_category") or "Unknown"
        categories_text = ", ".join(assigned_categories) if assigned_categories else "Unknown"
        perspective_block = self._format_perspective_block(area)
        prompt = REFLECTION_PROMPT_TEMPLATE.format(
            area=area,
            perspective_block=perspective_block,
            paper_id=paper_id,
            title=title,
            abstract=abstract,
            primary_category=primary_category,
            categories=categories_text,
            analysis_json=self._format_analysis_for_reflection(analysis),
            attempt_number=attempt_number,
        )
        response = call_llm_model(
            self.reflector_model_name, prompt, temperature=self.reflection_temperature
        )
        self._throttle()
        return self._parse_reflection_response(response or "")

    def _analyze_single_paper(
        self,
        paper: Dict[str, Any],
        area: str,
        assigned_categories: List[str],
    ) -> Optional[PerspectiveAnalysisResult]:
        history: List[AnalysisAttempt] = []
        final_analysis: Optional[Dict[str, str]] = None
        final_reflection: Optional[ReflectionResult] = None

        for attempt in range(1, self.max_rounds + 1):
            prompt = self._build_analysis_prompt(paper, area, assigned_categories, history)
            response = call_llm_model(self.model_name, prompt, temperature=self.temperature)
            self._throttle()

            analysis, error_feedback = self._parse_analysis_response(
                paper.get("paper_id", "N/A"),
                area,
                response or "",
            )

            attempt_record = AnalysisAttempt(
                attempt_number=attempt,
                analysis=analysis,
                analysis_raw=response or "",
                error_feedback=error_feedback,
            )

            if analysis is None:
                LOGGER.debug(
                    "Attempt %d for paper %s failed parsing: %s",
                    attempt,
                    paper.get("paper_id", "N/A"),
                    error_feedback,
                )
                history.append(attempt_record)
                continue

            reflection = self._reflect_analysis(paper, area, assigned_categories, analysis, attempt)
            attempt_record.reflection = reflection
            history.append(attempt_record)

            if reflection.verdict == "accept":
                final_analysis = analysis
                final_reflection = reflection
                break

            LOGGER.debug(
                "Reflection requested revision for paper %s (attempt %d): %s",
                paper.get("paper_id", "N/A"),
                attempt,
                reflection.feedback,
            )

        if final_analysis is None:
            # Use the last valid analysis if available even if not accepted.
            for attempt_record in reversed(history):
                if attempt_record.analysis is not None:
                    final_analysis = attempt_record.analysis
                    final_reflection = attempt_record.reflection
                    break

        return PerspectiveAnalysisResult(
            paper_id=str(paper.get("paper_id", "")),
            area=area,
            categories=list(assigned_categories),
            title=(paper.get("title") or "Untitled").strip(),
            analysis=final_analysis,
            reflection=final_reflection,
            attempts=history,
        )

    def _write_results(self, results: List[PerspectiveAnalysisResult]) -> None:
        serializable: List[Dict[str, Any]] = []
        for result in results:
            attempts_payload: List[Dict[str, Any]] = []
            for attempt in result.attempts:
                attempts_payload.append(
                    {
                        "attempt_number": attempt.attempt_number,
                        "analysis": attempt.analysis,
                        "analysis_raw": attempt.analysis_raw,
                        "reflection": {
                            "verdict": attempt.reflection.verdict if attempt.reflection else None,
                            "feedback": attempt.reflection.feedback if attempt.reflection else None,
                            "raw_response": attempt.reflection.raw_response if attempt.reflection else None,
                        }
                        if attempt.reflection
                        else None,
                        "error_feedback": attempt.error_feedback,
                    }
                )
            serializable.append(
                {
                    "paper_id": result.paper_id,
                    "area": result.area,
                    "categories": result.categories,
                    "title": result.title,
                    "analysis": result.analysis,
                    "reflection": {
                        "verdict": result.reflection.verdict if result.reflection else None,
                        "feedback": result.reflection.feedback if result.reflection else None,
                        "raw_response": result.reflection.raw_response if result.reflection else None,
                    }
                    if result.reflection
                    else None,
                    "attempts": attempts_payload,
                }
            )

        output_dir = os.path.dirname(self.output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        with open(self.output_path, "w", encoding="utf-8") as fp:
            json.dump(serializable, fp, ensure_ascii=False, indent=2)
        LOGGER.info("Wrote %d analysis results to %s", len(serializable), self.output_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate research perspective analysis for arXiv papers."
    )
    parser.add_argument(
        "--classification",
        default=os.path.join("dataset", "arxiv_area_classification.json"),
        help="Path to the classification JSON file.",
    )
    parser.add_argument(
        "--papers",
        default=os.path.join("dataset", "arxiv_web.json"),
        help="Path to the arXiv paper metadata JSON file.",
    )
    parser.add_argument(
        "--output",
        default=os.path.join("dataset", "arxiv_research_perspective.json"),
        help="Destination path for the generated perspective analysis.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL_NAME,
        help="LLM model name to use for analysis.",
    )
    parser.add_argument(
        "--reflector-model",
        default=DEFAULT_REFLECTOR_MODEL_NAME,
        help="LLM model name to use for self-reflection.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=DEFAULT_TEMPERATURE,
        help="Sampling temperature for the analysis model.",
    )
    parser.add_argument(
        "--reflection-temperature",
        type=float,
        default=DEFAULT_REFLECTION_TEMPERATURE,
        help="Sampling temperature for the reflection model.",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=DEFAULT_MAX_ROUNDS,
        help="Maximum number of reflection rounds per paper.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_REQUEST_INTERVAL,
        help="Seconds to wait between model invocations.",
    )
    parser.add_argument(
        "--max-papers",
        type=int,
        default=None,
        help="Optional limit on the number of papers to process.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_MAX_WORKERS,
        help="Number of concurrent analysis workers.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    analyzer = ResearchPerspectiveAnalyzer(
        classification_path=args.classification,
        paper_dataset_path=args.papers,
        output_path=args.output,
        model_name=args.model,
        reflector_model_name=args.reflector_model,
        temperature=args.temperature,
        reflection_temperature=args.reflection_temperature,
        max_rounds=args.max_rounds,
        request_interval=args.interval,
        max_workers=args.workers,
    )
    analyzer.run()


if __name__ == "__main__":
    main()
