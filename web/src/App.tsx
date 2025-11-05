import { useCallback, useEffect, useMemo, useState } from 'react';
import ClusterScene from './components/ClusterScene';
import { useClusteringData } from './hooks/useClusteringData';
import { ClusterSummary, PaperPoint } from './types';
import { getClusterColorHex } from './utils/color';

type HoverState = {
  paper: PaperPoint | null;
  position: { x: number; y: number } | null;
};

const App = () => {
  const { availableDates, selectedDate, data, loading, error, selectDate, refresh } = useClusteringData();
  const [hoverState, setHoverState] = useState<HoverState>({ paper: null, position: null });
  const [selectedClusters, setSelectedClusters] = useState<Set<number>>(new Set());

  const clusterLegend = useMemo(() => {
    if (!data) {
      return [];
    }
    return data.clusterSummaries
      .slice()
      .sort((a, b) => a.clusterId - b.clusterId)
      .map((cluster) => ({
        clusterId: cluster.clusterId,
        color: getClusterColorHex(cluster.clusterId),
        label: cluster.keywords
      }));
  }, [data]);

  const handleHoverChange = (payload: { paper: PaperPoint | null; screenPosition?: { x: number; y: number } }) => {
    if (!payload.paper) {
      setHoverState({ paper: null, position: null });
      return;
    }
    setHoverState({
      paper: payload.paper,
      position: payload.screenPosition ?? null
    });
  };

  const toggleClusterSelection = (paper: PaperPoint) => {
    setSelectedClusters((prev) => {
      const next = new Set(prev);
      if (next.has(paper.clusterId)) {
        next.delete(paper.clusterId);
      } else {
        next.add(paper.clusterId);
      }
      return next;
    });
  };

  useEffect(() => {
    if (!data) {
      setSelectedClusters(new Set());
      setHoverState({ paper: null, position: null });
      return;
    }
    setSelectedClusters(new Set());
    setHoverState({ paper: null, position: null });
  }, [data]);

  const clearSelections = useCallback(() => {
    setSelectedClusters(new Set());
    setHoverState({ paper: null, position: null });
  }, []);

  const selectedClusterDetails = useMemo(() => {
    if (!data || selectedClusters.size === 0) {
      return [] as Array<{ cluster: ClusterSummary; papers: PaperPoint[] }>;
    }

    const clusterLookup = new Map<number, ClusterSummary>(
      data.clusterSummaries.map((cluster) => [cluster.clusterId, cluster])
    );

    const papersByCluster = new Map<number, PaperPoint[]>();
    data.papers.forEach((paper) => {
      if (selectedClusters.has(paper.clusterId)) {
        const bucket = papersByCluster.get(paper.clusterId) ?? [];
        bucket.push(paper);
        papersByCluster.set(paper.clusterId, bucket);
      }
    });

    return Array.from(selectedClusters)
      .map((clusterId) => {
        const cluster = clusterLookup.get(clusterId);
        if (!cluster) {
          return null;
        }
        const papers = (papersByCluster.get(clusterId) ?? []).slice().sort((a, b) =>
          a.title.localeCompare(b.title)
        );
        return { cluster, papers };
      })
      .filter((entry): entry is { cluster: ClusterSummary; papers: PaperPoint[] } =>
        entry !== null
      )
      .sort((a, b) => a.cluster.clusterId - b.cluster.clusterId);
  }, [data, selectedClusters]);

  return (
    <div className="app-container">
      <div className="canvas-wrapper">
        {data && (
          <ClusterScene
            papers={data.papers}
            hoveringPaperId={hoverState.paper?.paperId ?? null}
            hoveringClusterId={hoverState.paper?.clusterId ?? null}
            selectedClusterIds={selectedClusters}
            onHoverChange={handleHoverChange}
            onTogglePin={toggleClusterSelection}
            onBackgroundClick={clearSelections}
          />
        )}
        {loading && (
          <div className="loading-state">
            Loading clustering data...
          </div>
        )}
        {error && (
          <div className="error-banner">
            {error}
          </div>
        )}
        {hoverState.paper && hoverState.position && (
          <div
            className="paper-tooltip"
            style={{ left: hoverState.position.x, top: hoverState.position.y }}
          >
            <h4>{hoverState.paper.title}</h4>
            {hoverState.paper.authors && (
              <p><strong>Authors:</strong> {hoverState.paper.authors}</p>
            )}
            {hoverState.paper.categories.length > 0 && (
              <p><strong>Categories:</strong> {hoverState.paper.categories.join(', ')}</p>
            )}
          </div>
        )}
      </div>

      <div className="overlay">
        <div className="floating-panel panel-snapshot">
          <div className="panel-row date-picker">
            <h2>Dataset Snapshot</h2>
          </div>
          <div className="date-buttons">
            {availableDates.length === 0 ? (
              <span className="panel-tag">No snapshots available</span>
            ) : (
              availableDates.map((date) => (
                <button
                  type="button"
                  key={date}
                  className={`date-button ${selectedDate === date ? 'active' : ''}`}
                  onClick={() => selectDate(date)}
                >
                  {date}
                </button>
              ))
            )}
          </div>
          {data && (
            <>
              <div className="stats-grid">
                <div className="stat-tile">
                  <div className="stat-label">Total Papers</div>
                  <div className="stat-value">{data.totalPapers}</div>
                </div>
                <div className="stat-tile">
                  <div className="stat-label">Clusters</div>
                  <div className="stat-value">{data.totalClusters}</div>
                </div>
                {typeof data.stats.noise_papers === 'number' && (
                  <div className="stat-tile">
                    <div className="stat-label">Noise Papers</div>
                    <div className="stat-value">{data.stats.noise_papers}</div>
                  </div>
                )}
                {typeof data.stats.perspective_entries_included === 'number' && (
                  <div className="stat-tile">
                    <div className="stat-label">Perspectives</div>
                    <div className="stat-value">{data.stats.perspective_entries_included}</div>
                  </div>
                )}
              </div>
              <div className="panel-row panel-row-compact">
                {data.stats.clustering_algorithm && (
                  <span className="panel-tag">
                    <strong>Clustering</strong> {data.stats.clustering_algorithm}
                  </span>
                )}
                {data.stats.dimensionality_reduction && (
                  <span className="panel-tag">
                    <strong>Embedding</strong> {data.stats.dimensionality_reduction}
                  </span>
                )}
                <button
                  type="button"
                  className="panel-tag"
                  onClick={() => refresh()}
                >
                  Refresh
                </button>
              </div>
            </>
          )}
        </div>

        {data && (
          <>
            <div className="floating-panel panel-legend">
              <h3>Cluster Legend</h3>
              <div className="legend">
                {clusterLegend.map((cluster) => {
                  const isHovered = hoverState.paper?.clusterId === cluster.clusterId;
                  const isSelected = selectedClusters.has(cluster.clusterId);
                  return (
                    <div
                      className={`legend-item ${isHovered || isSelected ? 'active' : ''}`}
                      key={cluster.clusterId}
                    >
                      <span
                        className="legend-swatch"
                        style={{ backgroundColor: cluster.color, boxShadow: `0 0 10px ${cluster.color}` }}
                      />
                      <span className="legend-label">
                        C{cluster.clusterId}: {cluster.label}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="floating-panel panel-insights">
              <h3>Cluster Insights</h3>
              <div className="cluster-list">
                {data.clusterSummaries.map((cluster) => (
                  <div className="cluster-item" key={cluster.clusterId}>
                    <div className="cluster-meta">
                      <div className="cluster-title">
                        Cluster {cluster.clusterId} · {cluster.paperCount} papers
                      </div>
                      <div className="cluster-keywords">
                        {cluster.keywords}
                      </div>
                    </div>
                    <div className="cluster-count">
                      {Object.entries(cluster.categoryBreakdown)
                        .slice(0, 2)
                        .map(([category, count]) => (
                          <div key={category}>
                            {category}: {count}
                          </div>
                        ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="floating-panel panel-categories">
              <h3>Selected Clusters</h3>
              <div className="category-panel">
                {selectedClusterDetails.length === 0 ? (
                  <div className="category-empty">
                    Click a paper bubble to pin its cluster. Select multiple clusters to compare; click the background to reset.
                  </div>
                ) : (
                  selectedClusterDetails.map((entry) => (
                    <div className="category-section" key={entry.cluster.clusterId}>
                      <div className="category-header">
                        <div className="category-label">
                          Cluster {entry.cluster.clusterId} · {entry.papers.length} papers
                        </div>
                        <div className="category-keywords">{entry.cluster.keywords}</div>
                      </div>
                      <ul className="category-list">
                        {entry.papers.map((paper) => (
                          <li key={paper.paperId}>{paper.title}</li>
                        ))}
                      </ul>
                    </div>
                  ))
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default App;
