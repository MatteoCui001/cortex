import { useCallback, useEffect, useRef, useState } from "react";
import { api, type EntityResult, type RelationRow } from "../api";

/* ── Types ── */

interface GNode {
  id: string;
  label: string;
  type: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  pinned?: boolean;
}

interface GEdge {
  source: string;
  target: string;
  relation: string;
  confidence: number;
}

const TYPE_COLORS: Record<string, string> = {
  person: "#818cf8",
  company: "#4ade80",
  technology: "#f59e0b",
  product: "#f87171",
  concept: "#a78bfa",
  organization: "#34d399",
};

function colorFor(type: string): string {
  return TYPE_COLORS[type.toLowerCase()] ?? "#94a3b8";
}

/* ── Force simulation (simple spring-charge model) ── */

function simulate(nodes: GNode[], edges: GEdge[], width: number, height: number) {
  const cx = width / 2;
  const cy = height / 2;
  const nodeMap = new Map(nodes.map((n) => [n.id, n]));

  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const a = nodes[i];
      const b = nodes[j];
      let dx = b.x - a.x;
      let dy = b.y - a.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const force = 800 / (dist * dist);
      dx = (dx / dist) * force;
      dy = (dy / dist) * force;
      if (!a.pinned) { a.vx -= dx; a.vy -= dy; }
      if (!b.pinned) { b.vx += dx; b.vy += dy; }
    }
  }

  for (const e of edges) {
    const a = nodeMap.get(e.source);
    const b = nodeMap.get(e.target);
    if (!a || !b) continue;
    let dx = b.x - a.x;
    let dy = b.y - a.y;
    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
    const force = (dist - 120) * 0.02;
    dx = (dx / dist) * force;
    dy = (dy / dist) * force;
    if (!a.pinned) { a.vx += dx; a.vy += dy; }
    if (!b.pinned) { b.vx -= dx; b.vy -= dy; }
  }

  for (const n of nodes) {
    if (n.pinned) continue;
    n.vx += (cx - n.x) * 0.005;
    n.vy += (cy - n.y) * 0.005;
  }

  for (const n of nodes) {
    if (n.pinned) continue;
    n.vx *= 0.8;
    n.vy *= 0.8;
    n.x += n.vx;
    n.y += n.vy;
    n.x = Math.max(40, Math.min(width - 40, n.x));
    n.y = Math.max(40, Math.min(height - 40, n.y));
  }
}

/* ── Canvas renderer ── */

function drawGraph(
  ctx: CanvasRenderingContext2D,
  nodes: GNode[],
  edges: GEdge[],
  width: number,
  height: number,
  hoveredId: string | null,
) {
  ctx.clearRect(0, 0, width, height);
  const nodeMap = new Map(nodes.map((n) => [n.id, n]));

  for (const e of edges) {
    const a = nodeMap.get(e.source);
    const b = nodeMap.get(e.target);
    if (!a || !b) continue;
    const isHovered = hoveredId === a.id || hoveredId === b.id;
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.strokeStyle = isHovered ? "rgba(129,140,248,0.5)" : "rgba(148,163,184,0.15)";
    ctx.lineWidth = isHovered ? 1.5 : 1;
    ctx.stroke();

    if (isHovered) {
      const mx = (a.x + b.x) / 2;
      const my = (a.y + b.y) / 2;
      ctx.font = "10px 'JetBrains Mono', monospace";
      ctx.fillStyle = "rgba(148,163,184,0.6)";
      ctx.textAlign = "center";
      ctx.fillText(e.relation, mx, my - 4);
    }
  }

  for (const n of nodes) {
    const isHovered = hoveredId === n.id;
    const r = isHovered ? 8 : 6;
    const c = colorFor(n.type);

    ctx.beginPath();
    ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
    ctx.fillStyle = isHovered ? c : c + "99";
    ctx.fill();

    ctx.font = isHovered ? "bold 12px 'Instrument Sans', sans-serif" : "11px 'Instrument Sans', sans-serif";
    ctx.fillStyle = isHovered ? "#e2e8f0" : "#94a3b8";
    ctx.textAlign = "center";
    ctx.fillText(n.label, n.x, n.y - r - 4);
  }
}

/* ── Main component ── */

export default function Graph() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const nodesRef = useRef<GNode[]>([]);
  const edgesRef = useRef<GEdge[]>([]);
  const animRef = useRef(0);
  const hoveredRef = useRef<string | null>(null);

  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [entityResults, setEntityResults] = useState<EntityResult[]>([]);
  const [selectedEntity, setSelectedEntity] = useState<EntityResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function searchEntities(q: string) {
    if (!q.trim()) { setEntityResults([]); return; }
    try {
      const results = await api.searchEntities(q.trim(), 10);
      setEntityResults(results);
    } catch {
      setEntityResults([]);
    }
  }

  const loadGraph = useCallback(async (entity: EntityResult) => {
    setSelectedEntity(entity);
    setEntityResults([]);
    setLoading(true);
    setError(null);
    try {
      const relations = await api.entityGraph(entity.id);
      buildGraph(entity, relations);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load graph");
    } finally {
      setLoading(false);
    }
  }, []);

  function buildGraph(center: EntityResult, relations: RelationRow[]) {
    const nodeSet = new Map<string, GNode>();
    const canvas = canvasRef.current;
    const w = canvas?.width ?? 800;
    const h = canvas?.height ?? 500;
    const cx = w / 2;
    const cy = h / 2;

    nodeSet.set(center.id, {
      id: center.id,
      label: center.name,
      type: center.type,
      x: cx,
      y: cy,
      vx: 0,
      vy: 0,
      pinned: true,
    });

    for (const r of relations) {
      if (!nodeSet.has(r.source_id)) {
        nodeSet.set(r.source_id, {
          id: r.source_id,
          label: r.source_name,
          type: r.source_type,
          x: cx + (Math.random() - 0.5) * 300,
          y: cy + (Math.random() - 0.5) * 300,
          vx: 0,
          vy: 0,
        });
      }
      if (!nodeSet.has(r.target_id)) {
        nodeSet.set(r.target_id, {
          id: r.target_id,
          label: r.target_name,
          type: r.target_type,
          x: cx + (Math.random() - 0.5) * 300,
          y: cy + (Math.random() - 0.5) * 300,
          vx: 0,
          vy: 0,
        });
      }
    }

    const edges: GEdge[] = relations.map((r) => ({
      source: r.source_id,
      target: r.target_id,
      relation: r.relation,
      confidence: r.confidence,
    }));

    nodesRef.current = Array.from(nodeSet.values());
    edgesRef.current = edges;
  }

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    function tick() {
      const w = canvas!.width;
      const h = canvas!.height;
      if (nodesRef.current.length > 0) {
        simulate(nodesRef.current, edgesRef.current, w, h);
        drawGraph(ctx!, nodesRef.current, edgesRef.current, w, h, hoveredRef.current);
      }
      animRef.current = requestAnimationFrame(tick);
    }
    animRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animRef.current);
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const parent = canvas.parentElement;
    if (!parent) return;
    const ro = new ResizeObserver(() => {
      canvas.width = parent.clientWidth;
      canvas.height = parent.clientHeight;
    });
    ro.observe(parent);
    canvas.width = parent.clientWidth;
    canvas.height = parent.clientHeight;
    return () => ro.disconnect();
  }, []);

  function handleMouseMove(e: React.MouseEvent<HTMLCanvasElement>) {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    let found: string | null = null;
    for (const n of nodesRef.current) {
      const dx = n.x - mx;
      const dy = n.y - my;
      if (dx * dx + dy * dy < 144) {
        found = n.id;
        break;
      }
    }
    hoveredRef.current = found;
    canvas.style.cursor = found ? "pointer" : "default";
  }

  function handleClick(e: React.MouseEvent<HTMLCanvasElement>) {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    for (const n of nodesRef.current) {
      const dx = n.x - mx;
      const dy = n.y - my;
      if (dx * dx + dy * dy < 144) {
        loadGraph({ id: n.id, name: n.label, type: n.type, aliases: [], score: 0, mention_count: 0 });
        break;
      }
    }
  }

  return (
    <div className="flex flex-col" style={{ height: "calc(100vh - 120px)" }}>
      <div className="flex flex-col md:flex-row md:items-baseline justify-between mb-4 gap-2 animate-in">
        <div>
          <h1 className="text-heading">Entity Graph</h1>
          <p className="text-caption mt-1">Explore relationships between entities</p>
        </div>

        {/* Legend */}
        <div className="flex gap-3 flex-wrap">
          {Object.entries(TYPE_COLORS).map(([type, color]) => (
            <div key={type} className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full" style={{ background: color }} />
              <span className="text-[10px]" style={{ color: "var(--text-tertiary)" }}>{type}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Search bar */}
      <div className="relative mb-4 animate-in animate-in-delay-1">
        <input
          type="text"
          value={query}
          onChange={(e) => { setQuery(e.target.value); searchEntities(e.target.value); }}
          placeholder="Search for an entity to visualize..."
          className="input-field w-full text-[13px] px-4 py-2.5"
        />

        {/* Dropdown results */}
        {entityResults.length > 0 && (
          <div
            className="absolute top-full left-0 right-0 mt-1 rounded-lg overflow-hidden z-10"
            style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)", boxShadow: "0 8px 32px rgba(0,0,0,0.3)" }}
          >
            {entityResults.map((ent) => (
              <button
                key={ent.id}
                onMouseDown={() => { setQuery(ent.name); loadGraph(ent); }}
                className="search-result w-full text-left px-4 py-2.5 flex items-center justify-between"
              >
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full" style={{ background: colorFor(ent.type) }} />
                  <span className="text-[13px]" style={{ color: "var(--text-primary)" }}>{ent.name}</span>
                  <span className="text-[10px]" style={{ color: "var(--text-tertiary)" }}>{ent.type}</span>
                </div>
                <span className="text-meta text-[10px]">{ent.mention_count} mentions</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {selectedEntity && (
        <div className="text-[12px] mb-2" style={{ color: "var(--text-secondary)" }}>
          Showing graph for{" "}
          <span style={{ color: colorFor(selectedEntity.type) }}>{selectedEntity.name}</span>
          <span className="text-meta ml-2">({nodesRef.current.length} nodes, {edgesRef.current.length} edges)</span>
        </div>
      )}

      {error && (
        <div
          className="text-[12px] py-3 px-4 rounded-lg mb-4"
          style={{ background: "var(--status-high-bg)", color: "var(--status-high)" }}
        >
          {error}
        </div>
      )}

      {loading && (
        <div className="py-16 text-center text-body" style={{ color: "var(--text-tertiary)" }}>Loading graph...</div>
      )}

      {/* Canvas */}
      <div
        className="flex-1 rounded-xl overflow-hidden"
        style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)", minHeight: 400 }}
      >
        <canvas
          ref={canvasRef}
          onMouseMove={handleMouseMove}
          onClick={handleClick}
          style={{ width: "100%", height: "100%" }}
        />
      </div>
    </div>
  );
}