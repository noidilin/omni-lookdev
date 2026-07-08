import { getAssetRowStatus, isAssetCurrent, type AssetRowStatus } from '../assets/assetStatus';
import type { AssetItem } from '../types/usd';

type Props = {
  assets: AssetItem[];
  currentAsset: string;
  pendingAssetPath: string;
  failedAssetPath: string;
  isSwitching: boolean;
  isReloading: boolean;
  isStageBusy: boolean;
  reloadError: string;
  onRefresh: () => void;
  onReload: () => void;
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
  isReloading,
  isStageBusy,
  reloadError,
  onRefresh,
  onReload,
  onLoad,
}: Props) {
  return (
    <section className="pane">
      <div className="pane-header">
        <div>
          <h2>Asset</h2>
          {isSwitching && <span className="asset-pane-status">Switching asset...</span>}
          {isReloading && <span className="asset-pane-status">Reloading asset...</span>}
        </div>
        <div className="pane-actions">
          <button type="button" onClick={onRefresh} disabled={isStageBusy}>Refresh</button>
          <button type="button" onClick={onReload} disabled={isStageBusy || !currentAsset}>Reload Asset</button>
        </div>
      </div>
      {reloadError && <p className="asset-error">Reload failed: {reloadError}</p>}
      <div className="asset-list">
        {assets.map((asset) => {
          const status = getAssetRowStatus(asset.path, currentAsset, pendingAssetPath, failedAssetPath);
          const isCurrent = isAssetCurrent(currentAsset, asset.path);
          const isDisabled = isStageBusy || isCurrent;
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
