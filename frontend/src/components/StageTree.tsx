import { useState } from 'react';
import type { USDPrim } from '../types/usd';

type Props = {
  prims: USDPrim[];
  selectedPath: string;
  onExpand: (path: string) => void;
  onSelect: (path: string) => void;
};

export function StageTree({ prims, selectedPath, onExpand, onSelect }: Props) {
  return (
    <section className="pane tree-pane">
      <div className="pane-header">
        <h2>Stage</h2>
      </div>
      <div className="tree">
        {prims.map((prim) => (
          <TreeRow key={prim.path} prim={prim} depth={0} selectedPath={selectedPath} onExpand={onExpand} onSelect={onSelect} />
        ))}
        {prims.length === 0 && <p className="empty">Waiting for stage hierarchy.</p>}
      </div>
    </section>
  );
}

function TreeRow({ prim, depth, selectedPath, onExpand, onSelect }: { prim: USDPrim; depth: number; selectedPath: string; onExpand: (path: string) => void; onSelect: (path: string) => void }) {
  const [expanded, setExpanded] = useState(false);
  const hasChildren = Boolean(prim.hasChildren);
  function toggle(event: React.MouseEvent) {
    event.stopPropagation();
    if (!hasChildren) return;
    const next = !expanded;
    setExpanded(next);
    if (next && !prim.children?.length) onExpand(prim.path);
  }
  return (
    <>
      <button
        type="button"
        className={`tree-row ${selectedPath === prim.path ? 'selected' : ''}`}
        style={{ paddingLeft: 8 + depth * 14 }}
        onClick={() => onSelect(prim.path)}
        title={prim.path}
      >
        <span className="chevron" onClick={toggle}>{hasChildren ? (expanded ? '▾' : '▸') : ''}</span>
        <span className={`type-dot ${prim.type || 'xform'}`} />
        <span className="tree-name">{prim.name}</span>
      </button>
      {expanded && prim.children?.map((child) => (
        <TreeRow key={child.path} prim={child} depth={depth + 1} selectedPath={selectedPath} onExpand={onExpand} onSelect={onSelect} />
      ))}
    </>
  );
}

