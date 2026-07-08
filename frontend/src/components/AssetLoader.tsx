import { useState } from 'react';
import type { AssetItem } from '../types/usd';

type Props = {
  assets: AssetItem[];
  onRefresh: () => void;
  onLoad: (path: string) => void;
};

export function AssetLoader({ assets, onRefresh, onLoad }: Props) {
  const [path, setPath] = useState('');
  return (
    <section className="pane">
      <div className="pane-header">
        <h2>Asset</h2>
        <button type="button" onClick={onRefresh}>Refresh</button>
      </div>
      <div className="asset-load-row">
        <input value={path} onChange={(event) => setPath(event.target.value)} placeholder="relative/path.usd" aria-label="Asset path" />
        <button type="button" onClick={() => onLoad(path)}>Load</button>
      </div>
      <div className="asset-list">
        {assets.map((asset) => (
          <button key={asset.id} type="button" className="asset-row" onClick={() => onLoad(asset.path)}>
            <span>{asset.name}</span>
            <small>{asset.path}</small>
          </button>
        ))}
        {assets.length === 0 && <p className="empty">No USD assets found in assets/.</p>}
      </div>
    </section>
  );
}

