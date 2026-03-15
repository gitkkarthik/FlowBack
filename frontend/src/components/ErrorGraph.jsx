import { useCallback, useEffect, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";

const API = "http://localhost:8000";

const NODE_COLORS = {
  error: "#ef4444",
  project: "#3b82f6",
  tag: "#a855f7",
};

const NODE_LABELS = {
  error: "Error",
  project: "Project",
  tag: "Skill Tag",
};

function nodeRadius(node) {
  return Math.min(24, Math.max(6, 4 + (node.count || 1) * 3));
}

export function ErrorGraph() {
  const [graphData, setGraphData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tooltip, setTooltip] = useState(null); // { node, x, y }
  const [dimensions, setDimensions] = useState({
    width: window.innerWidth,
    height: window.innerHeight - 56, // subtract nav height
  });
  const wrapperRef = useRef(null);

  // Fetch graph data
  useEffect(() => {
    setLoading(true);
    fetch(`${API}/error-graph`)
      .then((r) => r.json())
      .then((data) => {
        setGraphData(data);
        setLoading(false);
      })
      .catch(() => {
        setGraphData({ nodes: [], links: [] });
        setLoading(false);
      });
  }, []);

  // Resize observer
  useEffect(() => {
    function handleResize() {
      setDimensions({
        width: window.innerWidth,
        height: window.innerHeight - 56,
      });
    }
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const nodeCanvasObject = useCallback((node, ctx, globalScale) => {
    const r = nodeRadius(node);
    const color = NODE_COLORS[node.type] || "#94a3b8";

    // Draw circle
    ctx.beginPath();
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI, false);
    ctx.fillStyle = color;
    ctx.fill();

    // Draw label below node
    const label = node.label || node.id;
    const fontSize = Math.max(8, 10 / globalScale);
    ctx.font = `${fontSize}px sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    ctx.fillStyle = "rgba(226, 232, 240, 0.85)";
    ctx.fillText(label, node.x, node.y + r + 2);
  }, []);

  const handleNodeHover = useCallback((node, prevNode) => {
    if (!node) {
      setTooltip(null);
      return;
    }
    // We'll update tooltip position on mousemove separately
    setTooltip((prev) => ({
      node,
      x: prev?.x ?? window.innerWidth / 2,
      y: prev?.y ?? window.innerHeight / 2,
    }));
  }, []);

  // Track mouse for tooltip position
  useEffect(() => {
    function handleMouseMove(e) {
      setTooltip((prev) => {
        if (!prev) return prev;
        return { ...prev, x: e.clientX + 14, y: e.clientY + 14 };
      });
    }
    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, []);

  if (loading) {
    return (
      <div
        className="flex items-center justify-center"
        style={{ background: "#0f172a", width: dimensions.width, height: dimensions.height }}
      >
        <p className="text-slate-400 text-sm animate-pulse">Loading graph…</p>
      </div>
    );
  }

  const hasData = graphData && graphData.nodes && graphData.nodes.length > 0;

  if (!hasData) {
    return (
      <div
        className="flex flex-col items-center justify-center gap-3"
        style={{ background: "#0f172a", width: dimensions.width, height: dimensions.height }}
      >
        <p className="text-slate-300 text-lg font-medium">No errors tracked yet.</p>
        <p className="text-slate-500 text-sm">
          Run <code className="bg-slate-800 px-2 py-0.5 rounded text-slate-300">flowback error</code> to start.
        </p>
      </div>
    );
  }

  return (
    <div ref={wrapperRef} style={{ background: "#0f172a", position: "relative" }}>
      {/* Legend */}
      <div
        style={{
          position: "absolute",
          top: 16,
          left: 16,
          zIndex: 10,
          background: "rgba(15, 23, 42, 0.85)",
          border: "1px solid rgba(148, 163, 184, 0.2)",
          borderRadius: 8,
          padding: "10px 14px",
        }}
      >
        <p style={{ color: "#94a3b8", fontSize: 11, fontWeight: 600, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.05em" }}>
          Legend
        </p>
        {Object.entries(NODE_COLORS).map(([type, color]) => (
          <div key={type} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <div style={{ width: 10, height: 10, borderRadius: "50%", background: color, flexShrink: 0 }} />
            <span style={{ color: "#cbd5e1", fontSize: 12 }}>{NODE_LABELS[type]}</span>
          </div>
        ))}
        <p style={{ color: "#64748b", fontSize: 10, marginTop: 8 }}>Node size = occurrence count</p>
      </div>

      <ForceGraph2D
        graphData={graphData}
        width={dimensions.width}
        height={dimensions.height}
        backgroundColor="#0f172a"
        nodeCanvasObject={nodeCanvasObject}
        nodeCanvasObjectMode={() => "replace"}
        linkColor={() => "rgba(148,163,184,0.2)"}
        linkWidth={1}
        onNodeHover={handleNodeHover}
        cooldownTicks={100}
        nodeRelSize={1}
      />

      {/* Hover Tooltip */}
      {tooltip && tooltip.node && (
        <div
          style={{
            position: "fixed",
            left: tooltip.x,
            top: tooltip.y,
            zIndex: 100,
            background: "rgba(15, 23, 42, 0.95)",
            border: "1px solid rgba(148, 163, 184, 0.25)",
            borderRadius: 8,
            padding: "10px 14px",
            minWidth: 180,
            maxWidth: 280,
            pointerEvents: "none",
          }}
        >
          {/* Type badge */}
          <span
            style={{
              display: "inline-block",
              background: NODE_COLORS[tooltip.node.type] || "#94a3b8",
              color: "#fff",
              fontSize: 10,
              fontWeight: 700,
              borderRadius: 4,
              padding: "1px 6px",
              marginBottom: 6,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
            }}
          >
            {tooltip.node.type}
          </span>
          <p style={{ color: "#f1f5f9", fontSize: 13, fontWeight: 600, margin: "0 0 4px 0", wordBreak: "break-word" }}>
            {tooltip.node.label}
          </p>
          <p style={{ color: "#94a3b8", fontSize: 11, margin: 0 }}>
            Occurrences: <span style={{ color: "#e2e8f0", fontWeight: 600 }}>{tooltip.node.count || 1}</span>
          </p>
          {tooltip.node.type === "error" && tooltip.node.root_cause && (
            <p style={{ color: "#94a3b8", fontSize: 11, margin: "6px 0 0 0", lineHeight: 1.5 }}>
              <span style={{ color: "#fbbf24", fontWeight: 600 }}>Root cause: </span>
              {tooltip.node.root_cause}
            </p>
          )}
          {tooltip.node.type === "error" && tooltip.node.fingerprint && (
            <p style={{ color: "#475569", fontSize: 10, margin: "4px 0 0 0", fontFamily: "monospace" }}>
              {tooltip.node.fingerprint}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
