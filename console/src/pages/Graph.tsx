import { useCallback, useEffect, useRef, useState } from "react";
import { api, type EntityResult, type RelationRow, type Event } from "../api";
import DetailDrawer, { type DrawerTarget } from "../DetailDrawer";

/* ── Types ── */

interface GNode {
  id: string;
  label: string;
  type: string;
  nodeKind: "entity" | "event" | "thesis";
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
  person: "#6366F1",
  company: "#16A34A",
  technology: "#D97706",
  product: "#DC2626",
  concept: "#9333EA",
  organization: "#059669",
  thesis: "#B45A38",
};

function colorFor(type: string): string {
  return TYPE_COLORS[type.toLowerCase()] ?? "#94a3b8";
}

/* ── Force simulation (simple spring-charge model) ── */

function simulate(nodes: GNode[], edges: GEdge[], width: number, height: number) {
  const cx = width / 2;
  const cy = height / 2;
  const nodeMap = new Map(nodes.map((n) => [n.id, n]));

  // Repulsion: stronger to spread nodes out
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const a = nodes[i];
      const b = nodes[j];
      let dx = b.x - a.x;
      let dy = b.y - a.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const force = 2000 / (dist * dist);
      dx = (dx / dist) * force;
      dy = (dy / dist) * force;
      if (!a.pinned) { a.vx -= dx; a.vy -= dy; }
      if (!b.pinned) { b.vx += dx; b.vy += dy; }
    }
  }

  // Spring attraction along edges
  for (const e of edges) {
    const a = nodeMap.get(e.source);
    const b = nodeMap.get(e.target);
    if (!a || !b) continue;
    let dx = b.x - a.x;
    let dy = b.y - a.y;
    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
    const restLen = 150;
    const force = (dist - restLen) * 0.015;
    dx = (dx / dist) * force;
    dy = (dy / dist) * force;
    if (!a.pinned) { a.vx += dx; a.vy += dy; }
    if (!b.pinned) { b.vx -= dx; b.vy -= dy; }
  }

  // Gentle gravity toward center
  for (const n of nodes) {
    if (n.pinned) continue;
    n.vx += (cx - n.x) * 0.003;
    n.vy += (cy - n.y) * 0.003;
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
    ctx.strokeStyle = isHovered ? "rgba(180,90,56,0.45)" : "rgba(0,0,0,0.10)";
    ctx.lineWidth = isHovered ? 1.5 : 1;
    ctx.stroke();

    if (isHovered) {
      const mx = (a.x + b.x) / 2;
      const my = (a.y + b.y) / 2;
      ctx.font = "10px 'IBM Plex Mono', monospace";
      ctx.fillStyle = "rgba(87,83,78,0.7)";
      ctx.textAlign = "center";
      ctx.fillText(e.relation, mx, my - 4);
    }
  }

  for (const n of nodes) {
    const isHovered = hoveredId === n.id;
    const isThesis = n.nodeKind === "thesis";
    const r = isThesis ? 14 : isHovered ? 8 : 5;
    const c = colorFor(n.type);

    ctx.beginPath();
    if (isThesis) {
      // Diamond shape for thesis nodes
      ctx.moveTo(n.x, n.y - r);
      ctx.lineTo(n.x + r, n.y);
      ctx.lineTo(n.x, n.y + r);
      ctx.lineTo(n.x - r, n.y);
      ctx.closePath();
    } else {
      ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
    }
    ctx.fillStyle = isHovered ? c : isThesis ? c : c + "BB";
    ctx.fill();

    // Thesis nodes get a subtle stroke
    if (isThesis) {
      ctx.strokeStyle = c;
      ctx.lineWidth = 2;
      ctx.stroke();
    }

    // Only show labels for thesis nodes and hovered nodes
    if (isThesis || isHovered) {
      const fontSize = isThesis ? 14 : 12;
      const fontWeight = "bold";
      const fontFamily = isThesis ? "'Crimson Pro', serif" : "'Source Sans 3', sans-serif";
      ctx.font = `${fontWeight} ${fontSize}px ${fontFamily}`;
      ctx.fillStyle = isThesis ? "#B45A38" : "#1C1917";
      ctx.textAlign = "center";
      ctx.fillText(n.label, n.x, n.y - r - 5);
    }
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
  const [error, setError] = useState<string | null>(null);
  const [graphInfo, setGraphInfo] = useState<string>("");
  const [showAll, setShowAll] = useState(false);
  const [overviewData, setOverviewData] = useState<{
    entities: { id: string; name: string; type: string; theses: string[]; mention_count: number }[];
    relations: RelationRow[];
    thesis_links: { source: string; target: string; shared_events: number }[];
    all_theses: string[];
  } | null>(null);
  const [drawer, setDrawer] = useState<DrawerTarget | null>(null);

  // Side panel for clicked entity
  const [clickedNode, setClickedNode] = useState<GNode | null>(null);
  const [nodeEvents, setNodeEvents] = useState<Event[]>([]);
  const [nodeEventsLoading, setNodeEventsLoading] = useState(false);

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
    setEntityResults([]);
    setClickedNode(null);
    setLoading(true);
    setError(null);
    try {
      const relations = await api.entityGraph(entity.id);
      buildGraphFromRelations([{ center: entity, relations }]);
      setGraphInfo(`${entity.name}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load graph");
    } finally {
      setLoading(false);
    }
  }, []);

  // Auto-load: thesis-centered entity graph
  useEffect(() => {
    let cancelled = false;
    async function autoLoad() {
      setLoading(true);
      setError(null);
      try {
        const data = await api.graphOverview();
        if (cancelled) return;

        // Use all_theses from config as the source of truth
        const allTheses = data.all_theses || [];
        const hasThesisData = allTheses.length > 0 || data.entities.length > 0;

        if (!hasThesisData) {
          // Fallback: no thesis config and no entity data
          const topEnts = await api.topEntities(10);
          if (cancelled || topEnts.length === 0) {
            setLoading(false);
            setGraphInfo("No entities found. Ingest some content to build the graph.");
            return;
          }
          const top3 = topEnts.slice(0, 3);
          const results = await Promise.all(
            top3.map(async (ent) => {
              try {
                const relations = await api.entityGraph(ent.id);
                return { center: ent, relations };
              } catch {
                return { center: ent, relations: [] as RelationRow[] };
              }
            })
          );
          if (cancelled) return;
          buildGraphFromRelations(results);
          setGraphInfo(`Top entities`);
        } else {
          setOverviewData({
            entities: data.entities,
            relations: data.relations,
            thesis_links: data.thesis_links || [],
            all_theses: allTheses,
          });
          buildThesisGraph(data.entities, data.relations, data.thesis_links || [], allTheses, false);
          const thesesInGraph = new Set([
            ...allTheses,
            ...data.entities.flatMap(e => e.theses),
          ]);
          setGraphInfo(`${thesesInGraph.size} theses`);
        }
      } catch (err: unknown) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load graph");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    autoLoad();
    return () => { cancelled = true; };
  }, []);

  function buildThesisGraph(
    entities: { id: string; name: string; type: string; theses: string[]; mention_count: number }[],
    relations: RelationRow[],
    thesisLinks: { source: string; target: string; shared_events: number }[] = [],
    allTheses: string[] = [],
    showAllEntities: boolean = false,
  ) {
    const nodeSet = new Map<string, GNode>();
    const edgeSet: GEdge[] = [];
    const canvas = canvasRef.current;
    const w = canvas?.width ?? 800;
    const h = canvas?.height ?? 500;
    const cx = w / 2;
    const cy = h / 2;

    // Collect ALL theses: configured list + any from entities/links
    const thesisNames = new Set<string>(allTheses);
    for (const ent of entities) {
      for (const t of ent.theses) thesisNames.add(t);
    }
    for (const link of thesisLinks) {
      thesisNames.add(link.source);
      thesisNames.add(link.target);
    }

    // Create thesis hub nodes in a circle around center
    const thesesArr = [...thesisNames];
    thesesArr.forEach((thesis, i) => {
      const angle = (i / thesesArr.length) * Math.PI * 2 - Math.PI / 2;
      const dist = Math.min(w, h) * 0.25;
      const thesisId = `thesis:${thesis}`;
      nodeSet.set(thesisId, {
        id: thesisId,
        label: thesis,
        type: "thesis",
        nodeKind: "thesis",
        x: cx + Math.cos(angle) * dist,
        y: cy + Math.sin(angle) * dist,
        vx: 0,
        vy: 0,
      });
    });

    // Limit to top entities by mention count (unless showAll)
    const sortedEntities = [...entities].sort((a, b) => b.mention_count - a.mention_count);
    const visibleEntities = showAllEntities ? sortedEntities : sortedEntities.slice(0, 30);

    // Create entity nodes scattered around their thesis
    for (const ent of visibleEntities) {
      if (nodeSet.has(ent.id)) continue;
      // Position near the first thesis it belongs to
      const primaryThesis = ent.theses[0];
      const thesisNode = nodeSet.get(`thesis:${primaryThesis}`);
      const bx = thesisNode?.x ?? cx;
      const by = thesisNode?.y ?? cy;
      nodeSet.set(ent.id, {
        id: ent.id,
        label: ent.name,
        type: ent.type,
        nodeKind: "entity",
        x: bx + (Math.random() - 0.5) * 200,
        y: by + (Math.random() - 0.5) * 200,
        vx: 0,
        vy: 0,
      });

      // Add edges from entity to each of its theses
      for (const t of ent.theses) {
        edgeSet.push({
          source: ent.id,
          target: `thesis:${t}`,
          relation: "supports",
          confidence: 1,
        });
      }
    }

    // Add entity-entity relations
    for (const r of relations) {
      if (!nodeSet.has(r.source_id) || !nodeSet.has(r.target_id)) continue;
      const edgeKey = `${r.source_id}-${r.target_id}-${r.relation}`;
      if (!edgeSet.some(e => `${e.source}-${e.target}-${e.relation}` === edgeKey)) {
        edgeSet.push({
          source: r.source_id,
          target: r.target_id,
          relation: r.relation,
          confidence: r.confidence,
        });
      }
    }

    // Add thesis-to-thesis edges from co-occurrence data
    const addedThesisPairs = new Set<string>();
    for (const link of thesisLinks) {
      const srcId = `thesis:${link.source}`;
      const tgtId = `thesis:${link.target}`;
      if (nodeSet.has(srcId) && nodeSet.has(tgtId)) {
        const key = [link.source, link.target].sort().join("||");
        if (!addedThesisPairs.has(key)) {
          addedThesisPairs.add(key);
          edgeSet.push({
            source: srcId,
            target: tgtId,
            relation: `${link.shared_events} events`,
            confidence: Math.min(link.shared_events / 5, 1),
          });
        }
      }
    }

    // Also add thesis edges from shared entities (if not already linked)
    const thesisEntityMap = new Map<string, Set<string>>();
    for (const ent of entities) {
      for (const t of ent.theses) {
        if (!thesisEntityMap.has(t)) thesisEntityMap.set(t, new Set());
        thesisEntityMap.get(t)!.add(ent.id);
      }
    }
    const thesisList = [...thesisNames];
    for (let i = 0; i < thesisList.length; i++) {
      for (let j = i + 1; j < thesisList.length; j++) {
        const a = thesisList[i];
        const b = thesisList[j];
        const key = [a, b].sort().join("||");
        if (addedThesisPairs.has(key)) continue;
        const setA = thesisEntityMap.get(a) || new Set();
        const setB = thesisEntityMap.get(b) || new Set();
        const shared = [...setA].filter(id => setB.has(id)).length;
        if (shared > 0) {
          edgeSet.push({
            source: `thesis:${a}`,
            target: `thesis:${b}`,
            relation: `${shared} shared`,
            confidence: Math.min(shared / 3, 1),
          });
        }
      }
    }

    nodesRef.current = Array.from(nodeSet.values());
    edgesRef.current = edgeSet;
  }

  // Rebuild graph when showAll toggles
  useEffect(() => {
    if (overviewData) {
      buildThesisGraph(
        overviewData.entities,
        overviewData.relations,
        overviewData.thesis_links,
        overviewData.all_theses,
        showAll,
      );
    }
  }, [showAll]);

  function buildGraphFromRelations(inputs: { center: EntityResult; relations: RelationRow[] }[]) {
    const nodeSet = new Map<string, GNode>();
    const edgeSet: GEdge[] = [];
    const canvas = canvasRef.current;
    const w = canvas?.width ?? 800;
    const h = canvas?.height ?? 500;
    const cx = w / 2;
    const cy = h / 2;

    for (const { center, relations } of inputs) {
      if (!nodeSet.has(center.id)) {
        const angle = Math.random() * Math.PI * 2;
        const dist = Math.random() * 100;
        nodeSet.set(center.id, {
          id: center.id,
          label: center.name,
          type: center.type,
          nodeKind: "entity",
          x: cx + Math.cos(angle) * dist,
          y: cy + Math.sin(angle) * dist,
          vx: 0,
          vy: 0,
        });
      }

      for (const r of relations) {
        if (!nodeSet.has(r.source_id)) {
          // Use entity type if available, otherwise fall back to source_type
          const nodeType = r.source_entity_type || r.source_type;
          const kind = r.source_type === "event" ? "event" as const : "entity" as const;
          nodeSet.set(r.source_id, {
            id: r.source_id,
            label: r.source_name,
            type: nodeType,
            nodeKind: kind,
            x: cx + (Math.random() - 0.5) * 400,
            y: cy + (Math.random() - 0.5) * 400,
            vx: 0,
            vy: 0,
          });
        }
        if (!nodeSet.has(r.target_id)) {
          const nodeType = r.target_entity_type || r.target_type;
          const kind = r.target_type === "event" ? "event" as const : "entity" as const;
          nodeSet.set(r.target_id, {
            id: r.target_id,
            label: r.target_name,
            type: nodeType,
            nodeKind: kind,
            x: cx + (Math.random() - 0.5) * 400,
            y: cy + (Math.random() - 0.5) * 400,
            vx: 0,
            vy: 0,
          });
        }

        const edgeKey = `${r.source_id}-${r.target_id}-${r.relation}`;
        if (!edgeSet.some(e => `${e.source}-${e.target}-${e.relation}` === edgeKey)) {
          edgeSet.push({
            source: r.source_id,
            target: r.target_id,
            relation: r.relation,
            confidence: r.confidence,
          });
        }
      }
    }

    nodesRef.current = Array.from(nodeSet.values());
    edgesRef.current = edgeSet;
  }

  // Load events for a clicked node
  async function loadNodeEvents(node: GNode) {
    setClickedNode(node);

    // Thesis nodes — load related events by thesis name
    if (node.nodeKind === "thesis") {
      setNodeEventsLoading(true);
      try {
        const events = await api.thesisEvidence(node.label);
        setNodeEvents(events);
      } catch {
        setNodeEvents([]);
      }
      setNodeEventsLoading(false);
      return;
    }

    setNodeEventsLoading(true);
    try {
      if (node.nodeKind === "event") {
        // It's an event node — fetch the event directly
        const event = await api.event(node.id);
        setNodeEvents([event]);
      } else {
        // It's an entity node — fetch related events
        const events = await api.entityEvents(node.id, 10);
        setNodeEvents(events);
      }
    } catch {
      // Fallback: try the other approach
      try {
        if (node.nodeKind === "event") {
          setNodeEvents([]);
        } else {
          const event = await api.event(node.id);
          setNodeEvents([event]);
        }
      } catch {
        setNodeEvents([]);
      }
    }
    setNodeEventsLoading(false);
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
        loadNodeEvents(n);
        return;
      }
    }
    // Click on empty space -> close side panel
    setClickedNode(null);
  }

  function handleDoubleClick(e: React.MouseEvent<HTMLCanvasElement>) {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    for (const n of nodesRef.current) {
      const dx = n.x - mx;
      const dy = n.y - my;
      if (dx * dx + dy * dy < 144) {
        if (n.nodeKind === "thesis") return; // thesis nodes can't expand
        loadGraph({ id: n.id, name: n.label, type: n.type, aliases: [], score: 0, mention_count: 0 });
        return;
      }
    }
  }

  return (
    <div className="flex flex-col" style={{ height: "calc(100vh - 120px)" }}>
      <div className="flex flex-col md:flex-row md:items-baseline justify-between mb-4 gap-2 animate-in">
        <div>
          <h1 className="text-heading">Entity Graph</h1>
          <p className="text-caption mt-1">Click a node to see related events. Double-click to expand.</p>
        </div>

        {/* Legend */}
        <div className="flex gap-3 flex-wrap">
          {Object.entries(TYPE_COLORS).map(([type, color]) => (
            <div key={type} className="flex items-center gap-1">
              <div
                className="rounded-full"
                style={{
                  background: color,
                  width: type === "thesis" ? 8 : 6,
                  height: type === "thesis" ? 8 : 6,
                  clipPath: type === "thesis" ? "polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%)" : undefined,
                }}
              />
              <span className="text-[10px]" style={{ color: "var(--text-tertiary)" }}>{type === "thesis" ? "theme" : type}</span>
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
            style={{ background: "var(--bg-surface)", border: "1px solid var(--border-default)", boxShadow: "var(--shadow-elevated)" }}
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

      {graphInfo && (
        <div className="text-[12px] mb-2 flex items-center gap-3" style={{ color: "var(--text-secondary)" }}>
          <span>
            {graphInfo}
            <span className="text-meta ml-2">({nodesRef.current.length} nodes, {edgesRef.current.length} edges)</span>
          </span>
          {overviewData && overviewData.entities.length > 30 && (
            <button
              onClick={() => setShowAll(!showAll)}
              className="text-[11px] px-2 py-0.5 rounded"
              style={{
                background: "var(--bg-elevated)",
                border: "1px solid var(--border-default)",
                color: "var(--text-secondary)",
              }}
            >
              {showAll ? "Top 30" : `Show all ${overviewData.entities.length}`}
            </button>
          )}
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

      {/* Canvas + Side panel */}
      <div className="flex-1 flex gap-4" style={{ minHeight: 400 }}>
        <div
          className="flex-1 rounded-xl overflow-hidden"
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}
        >
          <canvas
            ref={canvasRef}
            onMouseMove={handleMouseMove}
            onClick={handleClick}
            onDoubleClick={handleDoubleClick}
            style={{ width: "100%", height: "100%" }}
          />
        </div>

        {/* Entity events side panel */}
        {clickedNode && (
          <div
            className="w-72 shrink-0 rounded-xl overflow-y-auto"
            style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)", maxHeight: "100%" }}
          >
            <div className="px-4 py-3 border-b" style={{ borderColor: "var(--border-subtle)" }}>
              <div className="flex items-center gap-2 mb-1">
                <div className="w-3 h-3 rounded-full" style={{ background: colorFor(clickedNode.type) }} />
                <span className="text-[14px] font-medium" style={{ color: "var(--text-primary)" }}>
                  {clickedNode.label}
                </span>
              </div>
              <div className="text-[11px]" style={{ color: "var(--text-tertiary)" }}>{clickedNode.nodeKind === "thesis" ? "theme" : clickedNode.type}</div>
            </div>

            <div className="px-4 py-3">
              <div className="text-subheading mb-2">
                {clickedNode.nodeKind === "thesis" ? "Theme Events" : "Related Events"}
              </div>
                  {nodeEventsLoading ? (
                    <div className="text-meta py-4 text-center">Loading...</div>
                  ) : nodeEvents.length === 0 ? (
                    <div className="text-meta py-4 text-center">No events found</div>
                  ) : (
                    <div className="space-y-1.5">
                      {nodeEvents.map((ev) => (
                        <button
                          key={ev.id}
                          onClick={() => setDrawer({ kind: "event", id: ev.id })}
                          className="event-row w-full text-left px-2 py-2 rounded-lg"
                        >
                          <div className="text-[12px] font-medium truncate" style={{ color: "var(--text-primary)" }}>
                            {ev.title || "\u2014"}
                          </div>
                          <div className="text-meta mt-0.5">
                            {new Date(ev.created_at).toLocaleDateString()}
                          </div>
                          {ev.summary && (
                            <div className="text-[11px] mt-1 line-clamp-2" style={{ color: "var(--text-tertiary)" }}>
                              {ev.summary}
                            </div>
                          )}
                        </button>
                      ))}
                    </div>
                  )}
            </div>
          </div>
        )}
      </div>

      <DetailDrawer target={drawer} onClose={() => setDrawer(null)} />
    </div>
  );
}
