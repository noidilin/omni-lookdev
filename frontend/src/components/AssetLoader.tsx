import { getAssetRowStatus, isAssetCurrent, type AssetRowStatus } from '../assets/assetStatus';
import type { AssetItem } from '../types/usd';

type Props = {
  assets: AssetItem[];
  currentAsset: string;
  pendingAssetPath: string;
  failedAssetPath: string;
  isSwitching: boolean;
  onRefresh: () => void;
  onLoad: (path: string) => void;
};

const statusLabel: Record<Exclude<AssetRowStatus, 'idle'>, string> = {
  loading: 'Loading...',
  current: 'Current',
  failed: 'Failed',
};

export function AssetLoader({
  assets,
  currentAsset,
  pendingAssetPath,
  failedAssetPath,
  isSwitching,
  onRefresh,
  onLoad,
}: Props) {
  return (
    <section className="pane">
      <div className="pane-header">
        <div>
          <h2>Asset</h2>
          {isSwitching && <span className="asset-pane-status">Switching asset...</span>}
        </div>
        <button type="button" onClick={onRefresh} disabled={isSwitching}>Refresh</button>
      </div>
      <div className="asset-list">
        {assets.map((asset) => {
          const status = getAssetRowStatus(asset.path, currentAsset, pendingAssetPath, failedAssetPath);
          const isCurrent = isAssetCurrent(currentAsset, asset.path);
          const isDisabled = isSwitching || isCurrent;
          return (
            <button
              key={asset.id}
              type="button"
              className={`asset-row ${status}`}
              disabled={isDisabled}
              onClick={() => {
                if (!isDisabled) onLoad(asset.path);
              }}
            >
              <span className="asset-copy">
                <span>{asset.name}</span>
                <small>{asset.path}</small>
              </span>
              {status !== 'idle' && <span className={`asset-status ${status}`}>{statusLabel[status]}</span>}
            </button>
          );
        })}
        {assets.length === 0 && <p className="empty">No USD assets found in assets/.</p>}
      </div>
    </section>
  );
}
