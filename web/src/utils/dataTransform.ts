import {
  ClusteringStatistics,
  EnrichedClusteringData,
  PaperPoint,
  RawClusteringPayload
} from '../types';

const normalizeCategory = (value: string) =>
  value
    .split(/[;,]/)
    .map((token) => token.trim())
    .filter(Boolean);

const collectCategories = (point: PaperPoint, payloadEntry: RawClusteringPayload['paper_details'][string]) => {
  const categories = new Set<string>();

  if (payloadEntry.metadata.primary_category) {
    categories.add(payloadEntry.metadata.primary_category);
  }

  if (payloadEntry.metadata.categories) {
    normalizeCategory(payloadEntry.metadata.categories).forEach((cat) => categories.add(cat));
  }

  if (payloadEntry.merged_analysis?.categories) {
    payloadEntry.merged_analysis.categories.forEach((cat) => categories.add(cat));
  }

  return Array.from(categories);
};

const buildStats = (payload: RawClusteringPayload, totalPapers: number, clusterCount: number) => {
  const stats: ClusteringStatistics = payload.statistics ? { ...payload.statistics } : {};
  if (!stats.total_papers) {
    stats.total_papers = totalPapers;
  }
  if (!stats.total_clusters) {
    stats.total_clusters = clusterCount;
  }
  return stats;
};

export const transformClusteringPayload = (
  date: string,
  payload: RawClusteringPayload
): EnrichedClusteringData => {
  const papers: PaperPoint[] = [];
  const clusterSummariesMap = new Map<
    number,
    {
      paperCount: number;
      categories: Map<string, number>;
    }
  >();
  const categoryTotals = new Map<string, number>();

  Object.values(payload.paper_details ?? {}).forEach((entry) => {
    const point: PaperPoint = {
      paperId: entry.paper_id,
      clusterId: entry.cluster_id,
      coordinates: entry.coordinates,
      title: entry.metadata.title,
      authors: entry.metadata.authors,
      abstract: entry.metadata.abstract,
      url: entry.metadata.paper_url ?? entry.metadata.pdf_link ?? entry.metadata.html_link,
      categories: [],
      primaryCategory: entry.metadata.primary_category,
      publishedTime: entry.metadata.published_time
    };

    point.categories = collectCategories(point, entry);

    papers.push(point);

    const clusterInfo =
      clusterSummariesMap.get(entry.cluster_id) ??
      (() => {
        const value = { paperCount: 0, categories: new Map<string, number>() };
        clusterSummariesMap.set(entry.cluster_id, value);
        return value;
      })();

    clusterInfo.paperCount += 1;
    point.categories.forEach((cat) => {
      clusterInfo.categories.set(cat, (clusterInfo.categories.get(cat) ?? 0) + 1);
      categoryTotals.set(cat, (categoryTotals.get(cat) ?? 0) + 1);
    });
  });

  const clusterSummaries = Array.from(clusterSummariesMap.entries())
    .map(([clusterId, entry]) => ({
      clusterId,
      keywords: payload.cluster_keywords?.[clusterId.toString()] ?? 'Unlabelled cluster',
      paperCount: entry.paperCount,
      categoryBreakdown: Object.fromEntries(entry.categories)
    }))
    .sort((a, b) => b.paperCount - a.paperCount);

  const totalPapers = papers.length;
  const totalClusters = clusterSummaries.length;

  return {
    date,
    stats: buildStats(payload, totalPapers, totalClusters),
    papers,
    clusterSummaries,
    categories: Object.fromEntries(
      Array.from(categoryTotals.entries()).sort((a, b) => b[1] - a[1])
    ),
    totalPapers,
    totalClusters
  };
};
