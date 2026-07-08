import type { RenderSettingCapability } from '../types/messages';

type Props = {
  settings: Record<string, unknown>;
  capabilities: RenderSettingCapability[];
  availableAovs: string[];
  onChange: (key: string, value: unknown) => void;
};

export function RenderSettingsPanel({ settings, capabilities, availableAovs, onChange }: Props) {
  const caps = new Map(capabilities.map((capability) => [capability.key, capability]));
  const lighting = (settings.viewer_lighting || {}) as Record<string, unknown>;
  return (
    <section className="pane settings-pane">
      <div className="pane-header">
        <h2>Render</h2>
      </div>
      {caps.has('aov') && (
        <label className="field-row">
          <span>AOV</span>
          <select value={String(settings.aov || 'LdrColor')} onChange={(event) => onChange('aov', event.target.value)}>
            {(availableAovs.length ? availableAovs : ['LdrColor']).map((aov) => <option key={aov}>{aov}</option>)}
          </select>
        </label>
      )}
      {caps.has('samples_per_pixel') && (
        <SettingWithMode capability={caps.get('samples_per_pixel')!}>
          <input
            type="range"
            min={1}
            max={4096}
            step={1}
            value={Number(settings.samples_per_pixel || 64)}
            onChange={(event) => onChange('samples_per_pixel', Number(event.target.value))}
          />
          <input
            type="number"
            min={1}
            max={4096}
            value={Number(settings.samples_per_pixel || 64)}
            onChange={(event) => onChange('samples_per_pixel', Number(event.target.value))}
          />
        </SettingWithMode>
      )}
      {caps.has('denoiser') && (
        <label className="field-row">
          <span>Denoiser <ModeTag capability={caps.get('denoiser')!} /></span>
          <input type="checkbox" checked={Boolean(settings.denoiser)} onChange={(event) => onChange('denoiser', event.target.checked)} />
        </label>
      )}
      {caps.has('resolution') && (
        <label className="field-row">
          <span>Resolution <ModeTag capability={caps.get('resolution')!} /></span>
          <select value={resolutionValue(settings.resolution)} onChange={(event) => {
            const [width, height] = event.target.value.split('x').map(Number);
            onChange('resolution', { width, height });
          }}>
            <option value="1280x720">1280 × 720</option>
            <option value="1920x1080">1920 × 1080</option>
            <option value="2560x1440">2560 × 1440</option>
            <option value="3840x2160">3840 × 2160</option>
          </select>
        </label>
      )}
      {caps.has('viewer_lighting') && (
        <div className="field-group">
          <div className="group-title">Lighting <ModeTag capability={caps.get('viewer_lighting')!} /></div>
          <label className="field-row">
            <span>Enabled</span>
            <input type="checkbox" checked={Boolean(lighting.enabled ?? true)} onChange={(event) => onChange('viewer_lighting', { ...lighting, enabled: event.target.checked })} />
          </label>
          <LightingSlider label="Key" value={Number(lighting.key_intensity ?? 500)} onChange={(value) => onChange('viewer_lighting', { ...lighting, key_intensity: value })} />
          <LightingSlider label="Fill" value={Number(lighting.fill_intensity ?? 80)} onChange={(value) => onChange('viewer_lighting', { ...lighting, fill_intensity: value })} />
          <LightingSlider label="Environment" value={Number(lighting.environment_intensity ?? 1)} max={10} step={0.1} onChange={(value) => onChange('viewer_lighting', { ...lighting, environment_intensity: value })} />
        </div>
      )}
    </section>
  );
}

function SettingWithMode({ capability, children }: { capability: RenderSettingCapability; children: React.ReactNode }) {
  return (
    <div className="field-row stacked">
      <span>{capability.label} <ModeTag capability={capability} /></span>
      <div className="range-pair">{children}</div>
    </div>
  );
}

function LightingSlider({ label, value, max = 2000, step = 1, onChange }: { label: string; value: number; max?: number; step?: number; onChange: (value: number) => void }) {
  return (
    <label className="field-row stacked">
      <span>{label}</span>
      <div className="range-pair">
        <input type="range" min={0} max={max} step={step} value={value} onChange={(event) => onChange(Number(event.target.value))} />
        <input type="number" min={0} max={max} step={step} value={value} onChange={(event) => onChange(Number(event.target.value))} />
      </div>
    </label>
  );
}

function ModeTag({ capability }: { capability: RenderSettingCapability }) {
  return <small className={`mode-tag ${capability.applies_at}`}>{capability.applies_at.replace('_', ' ')}</small>;
}

function resolutionValue(value: unknown): string {
  const resolution = (value || {}) as { width?: number; height?: number };
  return `${resolution.width || 1920}x${resolution.height || 1080}`;
}

