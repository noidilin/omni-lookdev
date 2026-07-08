import type { StreamStatus } from '../types/messages';

type Props = {
  status: StreamStatus;
  server: string;
  primCount: number;
  currentAsset: string;
  error: string;
};

export function StatusBar({ status, server, primCount, currentAsset, error }: Props) {
  return (
    <div className="status-bar">
      <span className={`status-pill ${status}`}>{status}</span>
      <span>{server}</span>
      <span>{primCount} prims</span>
      {currentAsset && <span title={currentAsset}>{currentAsset.split(/[\\/]/).pop()}</span>}
      {error && <span className="status-error" title={error}>{error}</span>}
    </div>
  );
}

