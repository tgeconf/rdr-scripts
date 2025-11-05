# Real Deep Research (RDR) for AI, Robotics and Beyond

<img width="4335" height="1952" alt="teaser" src="https://github.com/user-attachments/assets/8af54ece-055e-4691-b2a1-7a991e00c115" />

## Overview

Real Deep Research (RDR) is a systematic framework for analyzing research landscapes, identifying emerging trends, discovering cross-domain opportunities, and providing concrete starting points for new research. The core of RDR is an embedding-based analysis pipeline consisting of four main components: **Data Preparation**, **Content Reasoning**, **Content Projection**, and **Embedding Analysis**.

## Method Implementation

### 1. Data Preparation

#### Paper Collection (Selection)
RDR collects papers from top-tier computer vision, robotics, and machine learning conferences (CVPR, ECCV, ICCV, CoRL, RSS, ICRA, NeurIPS, etc.) as well as industry research platforms (Nvidia, Meta, OpenAI). This corpus provides a comprehensive overview of research in foundation models and robotics, highlighting key technical advances, existing challenges, and future research directions.

**Implementation:**
- **Conference Scrapers**: Individual venue modules in `/venue/` directory (e.g., `rss22.py`, `cvpr.py`, `icra.py`) scrape paper titles, authors, abstracts, and PDF links directly from conference websites
- **Journal Scrapers**: Modules like `science.py`, `nature.py`, and `quantum.py` use OpenAlex API to fetch papers from scientific journals
- **Industry Scrapers**: `meta.py`, `nvidia.py` collect research from industry platforms

```python
# Example from venue/rss22.py
class PaperDatabase:
    def __init__(self, output_dir: str = "dataset"):
        self.output_dir = output_dir
        self.filename = os.path.join(output_dir, "rss22.json")
        self.papers: Dict[str, Paper] = {}
        self._load_existing_papers()
```

#### Area Filtering
To ensure collected papers are relevant to the research scope, RDR employs a domain filtering process using efficient LLMs with predefined prompts to identify papers related to foundation models and robotics.

**Foundation Model Definition**: "Deep learning models (especially Transformer models) trained on large amounts of data, capable of fitting generalized factual realities. These models typically serve as universal backbones for various downstream tasks across multiple domains." Key indicators include Large Multimodal Models (LMM) and Large Language Models (LLM).

**Robotics Definition**: "Systems equipped with input sensors and mechanical kinematics hardware, capable of producing joint motion. These systems are controlled by learning-based algorithms that facilitate automated or robust mapping from sensor input to actuator output." Key indicators include reinforcement learning in robotics contexts and imitation learning in physical systems.

After filtering, the resulting paper set P' belongs to foundation model domain ($D_f$), robotics domain ($D_r$), or both. Formally: $P' = \{p | p \in D_f \cup D_r\}$.

**Implementation:**
- Filtered datasets are stored as `*_filter1.json` files in `/dataset/` directory
- Each filtered paper includes boolean flags `is_foundation_model` and `is_robotics` with reasoning
- Example from `meta_filter1.json`:
```json
{
  "is_foundation_model": true,
  "foundation_reason": "The paper uses vision-language models (VLM), which are key indicators of foundation model research...",
  "is_robotics": false,
  "robotic_reason": "The paper focuses on unified benchmark for vision-language models without hardware connections..."
}
```

### 2. Content Reasoning

#### Defining Research Perspectives
For the filtered paper set P', RDR performs in-depth analysis to determine each paper's specific positioning. Guided by domain experts in foundation models and robotics, RDR defines perspectives aligned with established domain structures, emerging trends, and evolving knowledge. Beyond predefined perspectives, the RDR pipeline supports user-defined perspectives to accommodate new research questions.

#### Foundation Model Perspectives
RDR systematically analyzes foundation model development through five fundamental perspectives: Input (I), Modeling (M), Output (O), Objective (W), and Learning Strategy (R).

- **Input (I)**: Foundation model input processing typically involves raw data and tokenization procedures. Standard input sources include images, videos, audio, LiDAR, etc., processed through transformations and neural networks.
- **Modeling (M)**: The modeling component extracts key knowledge from inputs, performs reasoning, and decodes to output space.
- **Output (O)**: Tasks determine the decoding space, the final step of decoding latent representations into outputs for loss computation or final interaction.
- **Objective (W)**: To align foundation models with corresponding inputs and outputs, given model architectures are constrained by learning objectives that align model distributions with task-given transformations.
- **Strategy (R)**: Strategy is the "recipe" for adjusting model weights through inputs, outputs, and objectives, controlling training phases, convergence speed, and parameter updates.

Formally: $D'_f = \bigcup_{p \in P'} F(p)$, where $F(p) = \text{LLM}(p | \text{I, M, O, W, R})$. $D'_f$ represents the perspective projection of a given paper on foundation model research.

#### Robotics Perspectives
The core perspectives of robotics research emphasize hardware and interaction in real-world environments. RDR defines five key perspectives to map each paper's position in the broader robotics application domain: Input Sensors (S), Physical Body (B), Joint Output (J), Action Space (A), and Environment (E).

- **Input Sensors (S)**: Hardware devices that measure physical quantities or environmental conditions and convert them into digital signals processable by robot control systems.
- **Physical Body (P)**: In robotics, the physical body refers to mechanical structures and architectures capable of physical interaction with the environment.
- **Joint Output (J)**: Joint output refers to the physical motion or configuration produced by robot joints due to actuator commands.
- **Action Space (A)**: The action space is the set of all permissible actions a robot can execute in a given context, ranging from low-level joint commands to high-level behaviors.
- **Environment (E)**: The environment includes the physical space where the robot operates, characterized by spatial layout, structural features, and contextual elements.

Formally: $D'_r = \bigcup_{p \in P'} F(p)$, where $F(p) = \text{LMM}(p | \text{S, B, J, A, E})$. $D'_r$ represents the perspective projection of a given paper on robotics research.

#### Prompt Engineering
RDR uses specific prompts to extract information for each perspective from paper content. For example, prompts require analyzing paper content and identifying defined perspectives, returning answers in specified formats.

### 3. Content Projection

#### Natural Language to Latent Space Projection
RDR aims to project natural language descriptions extracted from research papers through defined perspectives into an informative latent space. This projection enables large-scale analysis of current research in foundation models and robotics, revealing potential future research directions.

RDR leverages pre-trained embedding foundation models G to project $D'_f$ (processed foundation model paper content) and $D'_r$ (processed robotics paper content) from natural language space to a more abstract embedding space. The embedding model maps text to a high-dimensional vector space where semantically similar concepts occupy nearby regions.

Formally, for any text fragment $x \in D$, its embedding is computed as $v_x = G(x) \in R^d$.

The core hypothesis is that by projecting paper content through this perspective-aware embedding process and analyzing them in high-dimensional manifolds, meaningful patterns, research trends, and potential gaps in the literature can be revealed through systematic visualization and cluster analysis.

### 4. Embedding Analysis

#### Structured Understanding
The goal of embedding analysis is to structure understanding of previously extracted embeddings. The embedding analysis pipeline contains three components:
- Clustering extracted embeddings and analyzing main concepts of each cluster
- Structuring concepts of each cluster to form an informative table
- Tracing back to reference papers based on structured understanding

#### Clustering for Embeddings
RDR first embeds each paper to obtain its vector representation V, and divides the corpus into k clusters. From each cluster, 50 papers are randomly sampled, and their text is input to a reasoning-based model with the following prompt:

"Please summarize the following content into three distinct keywords: Here is an example output: 'Keyword1, Keyword2, Keyword3'. The output should be short and precise, with only one output per paper."

The model returns three compact keywords capturing the cluster's core themes, providing each paper with cluster labels and a set of interpretable keywords for subsequent analysis.

#### Structured Investigation
After obtaining clustered embeddings and their associated thematic keywords, the next step is to generate structured investigations for given research fields. RDR utilizes 03 language models, using cluster keywords as prompts to guide the formulation of final investigation content.

Incorporating clustering results into prompts ensures generated text is grounded in actual research landscapes, enhancing coherence and relevance. RDR uses the following prompt to generate final output:

"These are keywords from clustering scientific papers by abstract content, but they are ambiguous and content may overlap between clusters. Can you summarize the information in a more structured way for the audience according to the following criteria:..."

## Project Structure

```
rdr-scripts/
├── dataset/                    # Collected and filtered paper datasets
│   ├── *.json                 # Raw paper collections by venue/year
│   └── *_filter1.json         # Filtered papers with domain classification
├── venue/                     # Data collection modules
│   ├── *.py                  # Individual venue scrapers
│   ├── science.py            # OpenAlex-based journal fetcher
│   ├── nature.py             # Nature journal fetcher
│   ├── quantum.py            # Quantum journal fetcher
│   └── arxiv.py              # arXiv API-based paper fetcher (NEW)
├── requirements.txt           # Python dependencies
├── ARXIV_USAGE.md            # arXiv module usage guide (NEW)
└── README.md                 # This documentation
```

## Usage

1. **Data Collection**: Run individual venue scripts in `/venue/` directory to collect papers
2. **Domain Filtering**: Apply filtering logic to classify papers into foundation models and robotics domains
3. **Content Analysis**: Use perspective-based reasoning to extract structured information
4. **Embedding Projection**: Project processed content into embedding space
5. **Cluster Analysis**: Perform clustering and thematic analysis on embeddings

### Daily Visualization Workflow

To refresh the 3D visualization and publish it to GitHub Pages after updating the dataset:

1. Run the daily clustering pipeline (or copy the new snapshot) so `dataset/YYYY-MM-DD/arxiv_clustering_results.json` reflects the latest data.
2. From the `web/` directory install dependencies (once) and export the datasets into the static bundle assets:
   ```bash
   cd web
   npm install        # only needed the first time or after dependency changes
   npm run export:data
   ```
3. Preview locally if desired:
   ```bash
   npm run dev
   ```
4. Commit the updated `dataset/**` files together with the generated `web/public/data/**` outputs, then push to the default branch. The `deploy.yml` GitHub Actions workflow automatically builds the site (respecting the repo’s Pages base path) and deploys the contents of `web/dist` to GitHub Pages.

## Citation

If you use this framework in your research, please cite the original RDR paper.

---

*This implementation provides the data collection and preprocessing pipeline for the Real Deep Research methodology. The embedding analysis and visualization components are implemented separately.*
