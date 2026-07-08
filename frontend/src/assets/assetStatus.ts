export type AssetRowStatus = 'idle' | 'loading' | 'current' | 'failed';

export function normalizeAssetPath(path: string): string {
  return path.replace(/\\/g, '/').trim().toLowerCase();
}

export function isAssetCurrent(currentAsset: string, assetPath: string): boolean {
  const current = normalizeAssetPath(currentAsset);
  const asset = normalizeAssetPath(assetPath);
  return Boolean(current && asset && (current === asset || current.endsWith(`/${asset}`)));
}

export function getAssetRowStatus(
  assetPath: string,
  currentAsset: string,
  pendingAssetPath: string,
  failedAssetPath: string,
): AssetRowStatus {
  if (pendingAssetPath === assetPath) return 'loading';
  if (failedAssetPath === assetPath) return 'failed';
  if (isAssetCurrent(currentAsset, assetPath)) return 'current';
  return 'idle';
}
