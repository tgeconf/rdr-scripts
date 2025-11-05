import argparse
import json
import logging
import os
from collections import defaultdict
from typing import Dict, List, Any, Optional, Tuple
import numpy as np

from utils.llm import call_embedding_model, call_llm_model

LOGGER = logging.getLogger(__name__)

DEFAULT_CLUSTERING_MODEL = os.environ.get("CLUSTERING_MODEL", "deepseek-reasoner")

class ResearchPaperClustering:
    def __init__(
        self,
        perspective_path: str,
        paper_metadata_path: str,
        output_path: str,
        temperature: float = 0.1,
    ):
        self.perspective_path = perspective_path
        self.paper_metadata_path = paper_metadata_path
        self.output_path = output_path
        self.clustering_model = DEFAULT_CLUSTERING_MODEL
        self.temperature = temperature
        
        # Load data
        self.perspective_data = self._load_perspective_data()
        self.paper_metadata = self._load_paper_metadata()
        self.perspective_index = self._index_perspective_entries()
        
        # Processed data
        self.merged_papers = None
        self.embeddings = None
        self.clusters = None
        self.cluster_keywords = None

    def _load_perspective_data(self) -> List[Dict[str, Any]]:
        """Load research perspective analysis data"""
        try:
            with open(self.perspective_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            LOGGER.error(f"Failed to load perspective data from {self.perspective_path}: {e}")
            raise

    def _load_paper_metadata(self) -> Dict[str, Dict[str, Any]]:
        """Load paper metadata and create lookup dictionary"""
        try:
            with open(self.paper_metadata_path, 'r', encoding='utf-8') as f:
                papers = json.load(f)
            return {paper["paper_id"]: paper for paper in papers}
        except Exception as e:
            LOGGER.error(f"Failed to load paper metadata from {self.paper_metadata_path}: {e}")
            raise

    def _index_perspective_entries(self) -> Dict[str, List[Dict[str, Any]]]:
        """Create a lookup from paper_id to all perspective entries."""
        index: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for entry in self.perspective_data:
            paper_id = str(entry.get("paper_id", "")).strip()
            if not paper_id:
                continue
            index[paper_id].append(entry)
        return dict(index)

    def merge_paper_entries(self) -> Dict[str, Dict[str, Any]]:
        """
        Merge duplicate paper entries and organize by categories
        Returns: Dictionary mapping paper_id to merged paper data
        """
        merged_papers = defaultdict(lambda: {
            "paper_id": "",
            "title": "",
            "categories": [],
            "category_analysis": {},
            "all_analysis": []
        })

        for entry in self.perspective_data:
            paper_id = entry["paper_id"]
            area = entry["area"]
            categories = entry.get("categories", [])
            analysis = entry.get("analysis", {})
            
            # Update basic paper info
            merged_papers[paper_id]["paper_id"] = paper_id
            merged_papers[paper_id]["title"] = entry.get("title", "")
            
            # Add categories
            for category in categories:
                if category not in merged_papers[paper_id]["categories"]:
                    merged_papers[paper_id]["categories"].append(category)
            
            # Add analysis for this category
            if area and analysis:
                merged_papers[paper_id]["category_analysis"][area] = analysis
            
            # Store all analysis entries
            merged_papers[paper_id]["all_analysis"].append({
                "area": area,
                "analysis": analysis,
                "categories": categories
            })

        LOGGER.info(f"Merged {len(self.perspective_data)} entries into {len(merged_papers)} unique papers")
        return dict(merged_papers)

    def format_content_for_embedding(self, paper_data: Dict[str, Any]) -> str:
        """
        Format paper analysis content for embedding generation
        Format: category 1: perspective 1: text, perspective 2: text...
        """
        content_parts = []
        
        # Process each category's analysis
        for category, analysis in paper_data["category_analysis"].items():
            if not analysis:  # Skip empty analysis
                continue
            content_parts.append(f"{category}:")
            for perspective, text in analysis.items():
                if text and text.strip():  # Only add non-empty text
                    content_parts.append(f"  {perspective}: {text}")
        
        # If no content, use title as fallback
        if not content_parts:
            title = paper_data.get("title", "Untitled paper")
            content_parts.append(f"Title: {title}")
        
        return "\n".join(content_parts)

    def generate_embeddings(self) -> np.ndarray:
        """Generate embeddings for all papers"""
        if self.merged_papers is None:
            self.merged_papers = self.merge_paper_entries()
        
        paper_ids = list(self.merged_papers.keys())
        contents = []
        
        LOGGER.info(f"Generating embeddings for {len(paper_ids)} papers...")
        
        for paper_id in paper_ids:
            content = self.format_content_for_embedding(self.merged_papers[paper_id])
            # Ensure content is not empty
            if not content or not content.strip():
                LOGGER.warning(f"Empty content for paper {paper_id}, using fallback")
                content = f"Paper ID: {paper_id}"
            contents.append(content)
        
        # Filter out any remaining empty strings
        valid_contents = [c for c in contents if c and c.strip()]
        if len(valid_contents) != len(contents):
            LOGGER.warning(f"Filtered out {len(contents) - len(valid_contents)} empty content strings")
        
        if not valid_contents:
            LOGGER.error("No valid content to generate embeddings")
            raise ValueError("No valid content for embedding generation")
        
        LOGGER.info(f"Generating embeddings for {len(valid_contents)} valid content strings...")
        
        # Generate embeddings using the existing embedding function
        embeddings = call_embedding_model(valid_contents)
        
        if embeddings is None or len(embeddings) == 0:
            LOGGER.error("Failed to generate embeddings")
            raise ValueError("Embedding generation failed")
        
        LOGGER.info(f"Successfully generated embeddings with shape {embeddings.shape}")
        return embeddings

    def perform_clustering(self, embeddings: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Perform UMAP dimensionality reduction and HDBSCAN clustering
        Returns: (cluster_labels, reduced_embeddings)
        """
        try:
            import umap
            import hdbscan
            from sklearn.preprocessing import StandardScaler
            
            LOGGER.info("Performing UMAP dimensionality reduction...")
            
            # Standardize embeddings
            scaler = StandardScaler()
            scaled_embeddings = scaler.fit_transform(embeddings)
            
            # Reduce to 3D using UMAP
            reducer = umap.UMAP(
                n_components=3,
                random_state=42,
                n_neighbors=min(15, len(embeddings) - 1),
                min_dist=0.1
            )
            reduced_embeddings = reducer.fit_transform(scaled_embeddings)
            
            LOGGER.info("Performing HDBSCAN clustering...")
            
            # Perform HDBSCAN clustering
            clusterer = hdbscan.HDBSCAN(
                min_cluster_size=max(2, len(embeddings) // 10),
                min_samples=1,
                cluster_selection_epsilon=0.5
            )
            cluster_labels = clusterer.fit_predict(reduced_embeddings)
            
            n_clusters = len(set(cluster_labels)) - (1 if -1 in cluster_labels else 0)
            LOGGER.info(f"Found {n_clusters} clusters with {np.sum(cluster_labels == -1)} noise points")
            
            return cluster_labels, reduced_embeddings
            
        except ImportError as e:
            LOGGER.warning(f"Clustering libraries not available, using fallback clustering: {e}")
            return self._fallback_clustering(embeddings)

    def _fallback_clustering(self, embeddings: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Fallback clustering using simple K-means when advanced clustering is not available
        """
        LOGGER.info("Using fallback clustering with K-means")
        
        # Simple PCA for dimensionality reduction
        from sklearn.decomposition import PCA
        
        # Reduce to 3D using PCA
        pca = PCA(n_components=3, random_state=42)
        reduced_embeddings = pca.fit_transform(embeddings)
        
        # Simple clustering - assign all to cluster 0 for now
        # In a real implementation, you could use a simple distance-based clustering
        cluster_labels = np.zeros(len(embeddings), dtype=int)
        
        LOGGER.info("Fallback clustering completed - all papers assigned to single cluster")
        return cluster_labels, reduced_embeddings

    def extract_cluster_keywords(self, cluster_labels: np.ndarray) -> Dict[str, str]:
        """
        Extract representative keywords for each cluster using LLM
        """
        if self.merged_papers is None:
            raise ValueError("Papers must be merged before keyword extraction")
        
        paper_ids = list(self.merged_papers.keys())
        cluster_keywords: Dict[str, str] = {}
        
        unique_clusters = {int(label) for label in set(cluster_labels)}
        if -1 in unique_clusters:
            unique_clusters.remove(-1)  # Remove noise cluster
        
        for cluster_id in unique_clusters:
            # Get papers in this cluster
            cluster_paper_indices = np.where(cluster_labels == cluster_id)[0]
            
            if len(cluster_paper_indices) < 2:
                LOGGER.warning(f"Cluster {cluster_id} has only {len(cluster_paper_indices)} papers, skipping")
                continue
            
            # Randomly select 2 papers
            selected_indices = np.random.choice(
                cluster_paper_indices, 
                size=min(2, len(cluster_paper_indices)), 
                replace=False
            )
            
            selected_papers = []
            for idx in selected_indices:
                paper_id = paper_ids[idx]
                if paper_id in self.paper_metadata:
                    paper_info = self.paper_metadata[paper_id]
                    selected_papers.append({
                        "paper_id": paper_id,
                        "title": paper_info.get("title", ""),
                        "abstract": paper_info.get("abstract", "")
                    })
            
            if len(selected_papers) < 2:
                LOGGER.warning(f"Could not find metadata for selected papers in cluster {cluster_id}")
                continue
            
            # Generate keywords using LLM
            keywords = self._generate_keywords_for_papers(selected_papers)
            cluster_keywords[str(cluster_id)] = keywords
            LOGGER.info(f"Cluster {cluster_id} keywords: {keywords}")
        
        return cluster_keywords

    def _generate_keywords_for_papers(self, papers: List[Dict[str, str]]) -> str:
        """Generate keywords for a set of papers using LLM"""
        papers_text = ""
        for i, paper in enumerate(papers, 1):
            papers_text += f"\nPaper {i}:\n"
            papers_text += f"Title: {paper['title']}\n"
            papers_text += f"Abstract: {paper['abstract'][:500]}...\n"  # Limit abstract length
        
        prompt = f"""Can you summarize the following research papers into three distinct keywords that capture their common themes and research focus? 

Here are the papers:{papers_text}

Please provide exactly three keywords in the format: "keyword1, keyword2, keyword3"
The keywords should be short, precise, and representative of the shared research themes across these papers.

Output only the three keywords in the specified format, nothing else."""
        
        try:
            response = call_llm_model(self.clustering_model, prompt, self.temperature)
            if response:
                # Clean up response to ensure proper format
                response = response.strip()
                if response.startswith('"') and response.endswith('"'):
                    response = response[1:-1]
                return response
            else:
                return "analysis_failed, clustering, research"
        except Exception as e:
            LOGGER.error(f"Failed to generate keywords: {e}")
            return "error, analysis, research"

    def run_pipeline(self) -> Dict[str, Any]:
        """Run the complete clustering pipeline"""
        LOGGER.info("Starting research paper clustering pipeline...")
        
        # Step 1: Merge paper entries
        self.merged_papers = self.merge_paper_entries()
        
        # Step 2: Generate embeddings
        self.embeddings = self.generate_embeddings()
        
        # Step 3: Perform clustering
        cluster_labels, reduced_embeddings = self.perform_clustering(self.embeddings)
        
        # Step 4: Extract keywords
        self.cluster_keywords = self.extract_cluster_keywords(cluster_labels)
        
        # Prepare results
        results = self._prepare_results(cluster_labels, reduced_embeddings)
        
        # Save results
        self._save_results(results)
        
        LOGGER.info("Clustering pipeline completed successfully")
        return results

    def _prepare_results(self, cluster_labels: np.ndarray, reduced_embeddings: np.ndarray) -> Dict[str, Any]:
        """Prepare comprehensive results for output"""
        paper_ids = list(self.merged_papers.keys())
        
        cluster_mapping: Dict[str, Dict[str, Any]] = {}
        paper_details: List[Dict[str, Any]] = []
        perspective_total_entries = 0

        for i, paper_id in enumerate(paper_ids):
            cluster_id = int(cluster_labels[i])
            coordinates = reduced_embeddings[i].tolist() if i < len(reduced_embeddings) else [0, 0, 0]
            cluster_mapping[paper_id] = {
                "cluster_id": cluster_id,
                "coordinates": coordinates,
            }

            metadata = self.paper_metadata.get(paper_id, {})
            perspective_entries = self.perspective_index.get(paper_id, [])
            perspective_total_entries += len(perspective_entries)
            merged_entry = self.merged_papers.get(paper_id, {})

            paper_details.append(
                {
                    "paper_id": paper_id,
                    "cluster_id": cluster_id,
                    "coordinates": coordinates,
                    "metadata": metadata,
                    "merged_analysis": merged_entry,
                    "perspective_entries": perspective_entries,
                }
            )

        total_clusters = len(set(int(label) for label in cluster_labels)) - (1 if -1 in cluster_labels else 0)
        noise_papers = int(np.sum(cluster_labels == -1))

        return {
            "cluster_mapping": cluster_mapping,
            "cluster_keywords": self.cluster_keywords,
            "statistics": {
                "total_papers": len(paper_ids),
                "total_clusters": total_clusters,
                "noise_papers": noise_papers,
                "clustering_algorithm": "HDBSCAN",
                "dimensionality_reduction": "UMAP",
                "perspective_entries_included": perspective_total_entries,
            },
            "papers_processed": len(paper_ids),
            "paper_details": paper_details,
            "sources": {
                "perspective_data_path": self.perspective_path,
                "paper_metadata_path": self.paper_metadata_path,
            },
        }

    def _save_results(self, results: Dict[str, Any]) -> None:
        """Save clustering results to output file"""
        output_dir = os.path.dirname(self.output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        with open(self.output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        LOGGER.info(f"Results saved to {self.output_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Cluster research papers based on perspective analysis and extract representative keywords"
    )
    parser.add_argument(
        "--perspective-data",
        default=os.path.join("dataset", "arxiv_research_perspective.json"),
        help="Path to research perspective analysis JSON file"
    )
    parser.add_argument(
        "--paper-metadata",
        default=os.path.join("dataset", "arxiv_web.json"),
        help="Path to paper metadata JSON file"
    )
    parser.add_argument(
        "--output",
        default=os.path.join("dataset", "arxiv_clustering_results.json"),
        help="Output path for clustering results"
    )
    parser.add_argument(
        "--embedding-model",
        default="text-embedding-ada-002",
        help="Embedding model to use"
    )
    parser.add_argument(
        "--clustering-model",
        default="deepseek-reasoner",
        help="LLM model for keyword extraction"
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.1,
        help="Temperature for LLM keyword generation"
    )
    return parser


def main(argv: Optional[List[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    
    clustering = ResearchPaperClustering(
        perspective_path=args.perspective_data,
        paper_metadata_path=args.paper_metadata,
        output_path=args.output,
        temperature=args.temperature,
    )
    
    results = clustering.run_pipeline()
    
    # Print summary
    stats = results["statistics"]
    print(f"\nClustering Summary:")
    print(f"- Total papers processed: {stats['total_papers']}")
    print(f"- Clusters found: {stats['total_clusters']}")
    print(f"- Noise papers: {stats['noise_papers']}")
    print(f"\nCluster Keywords:")
    for cluster_id, keywords in results["cluster_keywords"].items():
        print(f"  Cluster {cluster_id}: {keywords}")


if __name__ == "__main__":
    main()
