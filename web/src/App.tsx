import { useCallback, useEffect, useMemo, useState } from 'react';
import ClusterScene from './components/ClusterScene';
import { useClusteringData } from './hooks/useClusteringData';
import { PaperPoint } from './types';
import { getClusterColorHex } from './utils/color';

type HoverState = {
  paper: PaperPoint | null;
  position: { x: number; y: number } | null;
};

const App = () => {
  const { availableDates, selectedDate, data, loading, error, selectDate, refresh } = useClusteringData();
  const [hoverState, setHoverState] = useState<HoverState>({ paper: null, position: null });
  const [pinnedPapers, setPinnedPapers] = useState<Map<string, PaperPoint>>(new Map());

  const pinnedList = useMemo(() => Array.from(pinnedPapers.values()).reverse(), [pinnedPapers]);
  const pinnedIds = useMemo(() => new Set(pinnedPapers.keys()), [pinnedPapers]);

  const topCategories = useMemo(() => {
    if (!data) {
      return [];
    }
    return Object.entries(data.categories)
      .slice(0, 6)
      .map(([name, count]) => ({ name, count }));
  }, [data]);

  const clusterLegend = useMemo(() => {
    if (!data) {
      return [];
    }
    return data.clusterSummaries.map((cluster) => ({
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

  const togglePin = (paper: PaperPoint) => {
    setPinnedPapers((prev) => {
      const next = new Map(prev);
      if (next.has(paper.paperId)) {
        next.delete(paper.paperId);
      } else {
        next.set(paper.paperId, paper);
      }
      return next;
    });
  };

  useEffect(() => {
    if (!data) {
      setPinnedPapers(new Map());
      setHoverState({ paper: null, position: null });
      return;
    }
    const lookup = new Map(data.papers.map((paper) => [paper.paperId, paper]));
    setPinnedPapers((prev) => {
      const next = new Map<string, PaperPoint>();
      prev.forEach((_value, key) => {
        const updated = lookup.get(key);
        if (updated) {
          next.set(key, updated);
        }
      });
      return next;
    });
    setHoverState({ paper: null, position: null });
  }, [data]);

  const clearPinned = useCallback(() => {
    setPinnedPapers(new Map());
    setHoverState({ paper: null, position: null });
  }, []);

  return (
    <div className="app-container">
      <div className="canvas-wrapper">
        {data && (
          <ClusterScene
            papers={data.papers}
            hoveringPaperId={hoverState.paper?.paperId ?? null}
            hoveringClusterId={hoverState.paper?.clusterId ?? null}
            pinnedPaperIds={pinnedIds}
            onHoverChange={handleHoverChange}
            onTogglePin={togglePin}
            onBackgroundClick={clearPinned}
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
        <div
          className="floating-panel"
          style={{ position: 'absolute', top: 24, left: 24, width: 360 }}
        >
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
              <div className="panel-row" style={{ marginTop: 14 }}>
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
            <div
              className="floating-panel"
              style={{ position: 'absolute', top: 24, right: 24, width: 320 }}
            >
              <h3>Cluster Legend</h3>
              <div className="legend">
                {clusterLegend.map((cluster) => (
                  <div className="legend-item" key={cluster.clusterId}>
                    <span
                      className="legend-swatch"
                      style={{ backgroundColor: cluster.color, boxShadow: `0 0 12px ${cluster.color}` }}
                    />
                    <span>
                      C{cluster.clusterId}: {cluster.label}
                    </span>
                  </div>
                ))}
              </div>
              {topCategories.length > 0 && (
                <>
                  <h3 style={{ marginTop: 16 }}>Top Categories</h3>
                  <div className="legend">
                    {topCategories.map((category) => (
                      <span className="panel-tag" key={category.name}>
                        <strong>{category.count}</strong> {category.name}
                      </span>
                    ))}
                  </div>
                </>
              )}
            </div>

            <div
              className="floating-panel"
              style={{ position: 'absolute', bottom: 24, left: 24, width: 340, maxHeight: '48vh', overflowY: 'auto' }}
            >
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

            <div
              className="floating-panel"
              style={{ position: 'absolute', bottom: 24, right: 24, width: 360, maxHeight: '48vh', overflowY: 'auto' }}
            >
              <h3>Pinned Papers</h3>
              <div className="pinned-panel">
                {pinnedList.length === 0 && (
                  <div className="cluster-item">
                    <span style={{ color: 'rgba(210, 220, 255, 0.6)' }}>
                      Click any bubble to pin the paper in this panel.
                    </span>
                  </div>
                )}
                {pinnedList.map((paper) => (
                  <div className="pinned-item" key={paper.paperId}>
                    <h4>{paper.title}</h4>
                    <div className="meta">
                      {paper.authors && <span>{paper.authors}</span>}
                      {paper.publishedTime && (
                        <span> · {new Date(paper.publishedTime).toLocaleDateString()}</span>
                      )}
                    </div>
                    {paper.categories.length > 0 && (
                      <p>
                        <strong>Categories:</strong> {paper.categories.join(', ')}
                      </p>
                    )}
                    {paper.abstract && (
                      <p>
                        <strong>Abstract:</strong> {paper.abstract.slice(0, 220)}
                        {paper.abstract.length > 220 ? '...' : ''}
                      </p>
                    )}
                    {paper.url && (
                      <p>
                        <a href={paper.url} target="_blank" rel="noreferrer" style={{ color: '#93c5fd' }}>
                          View on arXiv
                        </a>
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default App;
