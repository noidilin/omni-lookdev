import { useCallback, useEffect, useRef, useState } from 'react';
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

export function App() {
  const { status, errorMessage, sendMessage, onCustomEvent, config } = useStreaming();
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [rootPath, setRootPath] = useState('/');
  const [tree, setTree] = useState<USDPrim[]>([]);
  const [selectedPath, setSelectedPath] = useState('');
  const [properties, setProperties] = useState<Properties | null>(null);
  const [primCount, setPrimCount] = useState(0);
  const [currentAsset, setCurrentAsset] = useState('');
  const [settings, setSettings] = useState<Record<string, unknown>>({});
  const [capabilities, setCapabilities] = useState<RenderSettingCapability[]>([]);
  const [availableAovs, setAvailableAovs] = useState<string[]>(['LdrColor']);
  const [viewerError, setViewerError] = useState('');
  const selectedPathRef = useRef('');

  const requestChildren = useCallback(
    (primPath: string) => {
      sendMessage({ event_type: 'getChildrenRequest', payload: { prim_path: primPath } });
    },
    [sendMessage],
  );

  useEffect(() => {
    const unsubscribe = onCustomEvent((event: ServerEvent) => {
      const payload = event.payload as Record<string, unknown>;
      switch (event.event_type) {
        case 'listAssetsResult':
          setAssets((payload.assets as AssetItem[]) || []);
          break;
        case 'openStageResult': {
          const root = String(payload.root_prim_path || '/');
          setRootPath(root);
          setCurrentAsset(String(payload.url || ''));
          setTree([]);
          setSelectedPath('');
          selectedPathRef.current = '';
          setProperties(null);
          requestChildren(root);
          sendMessage({ event_type: 'getPrimCountRequest', payload: {} });
          break;
        }
        case 'getChildrenResult': {
          const primPath = String(payload.prim_path || rootPath);
          const children = ((payload.children as ServerPrim[]) || []).map(normalizePrim);
          if (primPath === rootPath || tree.length === 0) setTree(children);
          else setTree((previous) => updatePrimChildren(previous, primPath, children));
          sendMessage({
            event_type: 'makePrimsSelectable',
            payload: { paths: children.map((child) => child.path) },
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
          const primPath = String(payload.prim_path || '');
          if (primPath === selectedPathRef.current) setProperties((payload.properties as Properties) || {});
          break;
        }
        case 'getPrimCountResult':
          setPrimCount(Number(payload.count || 0));
          break;
        case 'renderSettingsChanged':
          setSettings((payload.settings as Record<string, unknown>) || {});
          setCapabilities((payload.capabilities as RenderSettingCapability[]) || []);
          break;
        case 'activeAOVState':
          setAvailableAovs(((payload.available as string[]) || []).filter(Boolean));
          break;
        case 'availableAOVsResult':
          setAvailableAovs((((payload.aovs as string[]) || (payload.available as string[]) || []) as string[]).filter(Boolean));
          break;
        case 'viewerError':
          setViewerError(String(payload.message || payload.code || 'Viewer error'));
          break;
      }
    });
    return unsubscribe;
  }, [onCustomEvent, requestChildren, rootPath, sendMessage, tree.length]);

  useEffect(() => {
    if (status !== 'connected') return;
    sendMessage({ event_type: 'listAssetsRequest', payload: {} });
    sendMessage({ event_type: 'getRenderSettingsRequest', payload: {} });
  }, [status, sendMessage]);

  const selectPrim = useCallback(
    (path: string) => {
      sendMessage({ event_type: 'selectPrimsRequest', payload: { paths: path ? [path] : [] } });
    },
    [sendMessage],
  );

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
          <AssetLoader assets={assets} onRefresh={() => sendMessage({ event_type: 'listAssetsRequest', payload: {} })} onLoad={(path) => sendMessage({ event_type: 'loadAssetRequest', payload: { path } })} />
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
            onChange={(key, value) => sendMessage({ event_type: 'setRenderSettingRequest', payload: { key, value } })}
          />
        </aside>
      </main>
    </div>
  );
}

