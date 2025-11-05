export interface RawClusteringPayload {
  cluster_keywords: Record<string, string>;
  cluster_mapping: Record<
    string,
    {
      cluster_id: number;
      coordinates: [number, number, number];
    }
  >;
  paper_details: Record<
    string,
    {
      paper_id: string;
      cluster_id: number;
      coordinates: [number, number, number];
      metadata: PaperMetadata;
      merged_analysis?: MergedAnalysis;
    }
  >;
  papers_processed: number;
  sources?: string[];
  statistics?: ClusteringStatistics;
}

export interface PaperMetadata {
  paper_id: string;
  title: string;
  authors?: string;
  paper_url?: string;
  pdf_link?: string;
  html_link?: string;
  abstract?: string;
  published_time?: string | null;
  updated_time?: string | null;
  primary_category?: string;
  categories?: string;
  comments?: string | null;
  doi?: string | null;
  journal_ref?: string | null;
}

export interface MergedAnalysis {
  paper_id: string;
  title: string;
  categories?: string[];
  [key: string]: unknown;
}

export interface ClusteringStatistics {
  total_papers?: number;
  total_clusters?: number;
  noise_papers?: number;
  clustering_algorithm?: string;
  dimensionality_reduction?: string;
  perspective_entries_included?: number;
  [key: string]: unknown;
}

export interface PaperPoint {
  paperId: string;
  clusterId: number;
  coordinates: [number, number, number];
  title: string;
  authors?: string;
  abstract?: string;
  url?: string;
  categories: string[];
  primaryCategory?: string;
  publishedTime?: string | null;
}

export interface ClusterSummary {
  clusterId: number;
  keywords: string;
  paperCount: number;
  categoryBreakdown: Record<string, number>;
}

export interface EnrichedClusteringData {
  date: string;
  stats: ClusteringStatistics;
  papers: PaperPoint[];
  clusterSummaries: ClusterSummary[];
  categories: Record<string, number>;
  totalPapers: number;
  totalClusters: number;
}
