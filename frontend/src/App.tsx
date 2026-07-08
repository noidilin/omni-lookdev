import { useCallback, useEffect, useRef, useState } from 'react';
import { isAssetCurrent } from './assets/assetStatus';
import { AssetLoader } from './components/AssetLoader';
import { PropertyPanel } from './components/PropertyPanel';
import { RenderSettingsPanel } from './components/RenderSettingsPanel';
import { StageTree } from './components/StageTree';
import { StatusBar } from './components/StatusBar';
import { Toolbar } from './components/Toolbar';
import { Viewport } from './components/Viewport';
import { useStreaming } from './streaming/StreamingProvider';
import type { RenderSettingCapability, ServerEvent } from './types/messages';
import type { AssetItem, ServerPrim, USDPrim } from './types/usd';
import { normalizePrim, updatePrimChildren } from './types/usd';

type Properties = Record<string, unknown>;
type StageOperation = 'idle' | 'switching' | 'reloading';

export function App() {
  const { status, errorMessage, sendMessage, onCustomEvent, config } = useStreaming();
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [rootPath, setRootPath] = useState('/');
  const [tree, setTree] = useState<USDPrim[]>([]);
  const [selectedPath, setSelectedPath] = useState('');
  const [properties, setProperties] = useState<Properties | null>(null);
  const [primCount, setPrimCount] = useState(0);
  const [currentAsset, setCurrentAsset] = useState('');
  const [pendingAssetPath, setPendingAssetPath] = useState('');
  const [failedAssetPath, setFailedAssetPath] = useState('');
  const [stageOperation, setStageOperation] = useState<StageOperation>('idle');
  const [reloadError, setReloadError] = useState('');
  const [settings, setSettings] = useState<Record<string, unknown>>({});
  const [capabilities, setCapabilities] = useState<RenderSettingCapability[]>([]);
  const [availableAovs, setAvailableAovs] = useState<string[]>(['LdrColor']);
  const [aovStatus, setAovStatus] = useState('');
  const [viewerError, setViewerError] = useState('');
  const selectedPathRef = useRef('');
  const rootPathRef = useRef('/');
  const stageVersionRef = useRef(0);
  const currentAssetRef = useRef('');
  const pendingAssetPathRef = useRef('');
  const stageOperationRef = useRef<StageOperation>('idle');

  const setStageOperationState = useCallback((operation: StageOperation) => {
    stageOperationRef.current = operation;
    setStageOperation(operation);
  }, []);

  const requestChildren = useCallback(
    (primPath: string) => {
      sendMessage({ event_type: 'getChildrenRequest', payload: { prim_path: primPath, stage_version: stageVersionRef.current } });
    },
    [sendMessage],
  );

  const isCurrentStage = useCallback((payload: Record<string, unknown>): boolean => {
    const version = payload.stage_version;
    return version === undefined || Number(version) === stageVersionRef.current;
  }, []);

  useEffect(() => {
    const unsubscribe = onCustomEvent((event: ServerEvent) => {
      const payload = event.payload as Record<string, unknown>;
      switch (event.event_type) {
        case 'listAssetsResult':
          setAssets((payload.assets as AssetItem[]) || []);
          break;
        case 'openStageResult': {
          const root = String(payload.root_prim_path || '/');
          const assetUrl = String(payload.url || '');
          const stageVersion = Number(payload.stage_version ?? stageVersionRef.current);
          stageVersionRef.current = stageVersion;
          rootPathRef.current = root;
          setRootPath(root);
          currentAssetRef.current = assetUrl;
          pendingAssetPathRef.current = '';
          setCurrentAsset(assetUrl);
          setPendingAssetPath('');
          setFailedAssetPath('');
          setReloadError('');
          setStageOperationState('idle');
          setTree([]);
          setSelectedPath('');
          selectedPathRef.current = '';
          setProperties(null);
          sendMessage({ event_type: 'getChildrenRequest', payload: { prim_path: root, stage_version: stageVersion } });
          sendMessage({ event_type: 'getPrimCountRequest', payload: { stage_version: stageVersion } });
          break;
        }
        case 'getChildrenResult': {
          if (!isCurrentStage(payload)) break;
          const primPath = String(payload.prim_path || rootPathRef.current);
          const children = ((payload.children as ServerPrim[]) || []).map(normalizePrim);
          setTree((previous) => (
            primPath === rootPathRef.current || previous.length === 0
              ? children
              : updatePrimChildren(previous, primPath, children)
          ));
          sendMessage({
            event_type: 'makePrimsSelectable',
            payload: { paths: children.map((child) => child.path), stage_version: stageVersionRef.current },
          });
          break;
        }
        case 'stageSelectionChanged': {
          const next = (((payload.prims as string[]) || [])[0] || '').toString();
          selectedPathRef.current = next;
          setSelectedPath(next);
          setProperties(null);
          if (next) sendMessage({ event_type: 'getPropertiesRequest', payload: { prim_path: next } });
          break;
        }
        case 'getPropertiesResponse': {
          if (!isCurrentStage(payload)) break;
          const primPath = String(payload.prim_path || '');
          if (primPath === selectedPathRef.current) setProperties((payload.properties as Properties) || {});
          break;
        }
        case 'getPrimCountResult':
          if (!isCurrentStage(payload)) break;
          setPrimCount(Number(payload.count || 0));
          break;
        case 'renderSettingsChanged':
          setSettings((payload.settings as Record<string, unknown>) || {});
          setCapabilities((payload.capabilities as RenderSettingCapability[]) || []);
          break;
        case 'activeAOVState': {
          const active = String(payload.active || 'LdrColor');
          setSettings((previous) => ({ ...previous, aov: active }));
          setAvailableAovs(((payload.available as string[]) || []).filter(Boolean));
          if (payload.result === 'error') {
            setAovStatus(String(payload.reason || 'AOV unavailable'));
          } else if (payload.result === 'success') {
            setAovStatus('');
          }
          break;
        }
        case 'availableAOVsResult':
          setAvailableAovs((((payload.aovs as string[]) || (payload.available as string[]) || []) as string[]).filter(Boolean));
          break;
        case 'assetReloadResult':
          setStageOperationState('idle');
          if (payload.result === 'error') {
            setReloadError(String(payload.message || 'Reload failed'));
          } else {
            setReloadError('');
          }
          break;
        case 'viewerError':
          setViewerError(String(payload.message || payload.code || 'Viewer error'));
          if (stageOperationRef.current === 'switching' && pendingAssetPathRef.current) {
            setFailedAssetPath(pendingAssetPathRef.current);
            pendingAssetPathRef.current = '';
            setPendingAssetPath('');
            setStageOperationState('idle');
          } else if (stageOperationRef.current === 'reloading') {
            setReloadError(String(payload.message || payload.code || 'Reload failed'));
            setStageOperationState('idle');
          }
          break;
      }
    });
    return unsubscribe;
  }, [isCurrentStage, onCustomEvent, sendMessage, setStageOperationState]);

  useEffect(() => {
    if (status !== 'connected') return;
    sendMessage({ event_type: 'listAssetsRequest', payload: {} });
    sendMessage({ event_type: 'getRenderSettingsRequest', payload: {} });
    sendMessage({ event_type: 'getAvailableAOVs', payload: {} });
  }, [status, sendMessage]);

  const selectPrim = useCallback(
    (path: string) => {
      sendMessage({ event_type: 'selectPrimsRequest', payload: { paths: path ? [path] : [] } });
    },
    [sendMessage],
  );

  const refreshAssets = useCallback(() => {
    if (stageOperationRef.current !== 'idle') return;
    setFailedAssetPath('');
    sendMessage({ event_type: 'listAssetsRequest', payload: {} });
  }, [sendMessage]);

  const requestAssetLoad = useCallback(
    (path: string) => {
      const nextPath = path.trim();
      if (stageOperationRef.current !== 'idle' || !nextPath || isAssetCurrent(currentAssetRef.current, nextPath)) return;
      setFailedAssetPath('');
      setReloadError('');
      pendingAssetPathRef.current = nextPath;
      setPendingAssetPath(nextPath);
      setStageOperationState('switching');
      sendMessage({ event_type: 'loadAssetRequest', payload: { path: nextPath } });
    },
    [sendMessage, setStageOperationState],
  );

  const requestAssetReload = useCallback(
    () => {
      if (stageOperationRef.current !== 'idle' || !currentAssetRef.current) return;
      setFailedAssetPath('');
      setReloadError('');
      setStageOperationState('reloading');
      sendMessage({ event_type: 'reloadAssetRequest', payload: {} });
    },
    [sendMessage, setStageOperationState],
  );

  const isSwitching = stageOperation === 'switching';
  const isReloading = stageOperation === 'reloading';
  const isStageBusy = stageOperation !== 'idle';

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <h1>Lookdev Studio</h1>
          <span className="subtitle">RTX streamed USD asset review</span>
        </div>
        <StatusBar
          status={status}
          server={`${config.server}:${config.signalingPort}`}
          primCount={primCount}
          currentAsset={currentAsset}
          error={viewerError || errorMessage}
        />
      </header>
      <main className="workspace">
        <aside className="panel left-panel" onPointerEnter={() => sendMessage({ event_type: 'setViewportInputActive', payload: { active: false } })}>
          <AssetLoader
            assets={assets}
            currentAsset={currentAsset}
            pendingAssetPath={pendingAssetPath}
            failedAssetPath={failedAssetPath}
            isSwitching={isSwitching}
            isReloading={isReloading}
            isStageBusy={isStageBusy}
            reloadError={reloadError}
            onRefresh={refreshAssets}
            onReload={requestAssetReload}
            onLoad={requestAssetLoad}
          />
          <StageTree prims={tree} selectedPath={selectedPath} onExpand={requestChildren} onSelect={selectPrim} />
        </aside>
        <section className="viewport-panel">
          <Toolbar
            onFit={() => sendMessage({ event_type: 'fitCameraRequest', payload: {} })}
            onReset={() => sendMessage({ event_type: 'resetViewRequest', payload: {} })}
            onClearSelection={() => selectPrim('')}
          />
          <Viewport />
        </section>
        <aside className="panel right-panel" onPointerEnter={() => sendMessage({ event_type: 'setViewportInputActive', payload: { active: false } })}>
          <PropertyPanel selectedPath={selectedPath} properties={properties} />
          <RenderSettingsPanel
            settings={settings}
            capabilities={capabilities}
            availableAovs={availableAovs}
            aovStatus={aovStatus}
            onChange={(key, value) => {
              if (key === 'aov') {
                sendMessage({ event_type: 'changeAOVRequest', payload: { aov: value } });
              } else {
                sendMessage({ event_type: 'setRenderSettingRequest', payload: { key, value } });
              }
            }}
          />
        </aside>
      </main>
    </div>
  );
}
