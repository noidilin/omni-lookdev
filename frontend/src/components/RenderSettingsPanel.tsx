import type { RenderSettingCapability } from '../types/messages';

type Props = {
  settings: Record<string, unknown>;
  capabilities: RenderSettingCapability[];
  availableAovs: string[];
  aovStatus: string;
  onChange: (key: string, value: unknown) => void;
};

const AOV_OPTIONS = [
  { name: 'LdrColor', label: 'Beauty' },
  { name: 'NormalSD', label: 'Normals' },
  { name: 'DepthSD', label: 'Depth' },
];

export function RenderSettingsPanel({ settings, capabilities, availableAovs, aovStatus, onChange }: Props) {
  const canChangeAov = capabilities.some((capability) => capability.key === 'aov');
  const activeAov = String(settings.aov || 'LdrColor');
  const available = new Set(availableAovs.length ? availableAovs : ['LdrColor']);

  return (
    <section className="pane settings-pane">
      <div className="pane-header">
        <h2>Render</h2>
      </div>
      {canChangeAov && (
        <div className="field-row stacked">
          <span>Debug AOV</span>
          <div className="segmented-control" role="group" aria-label="Debug AOV">
            {AOV_OPTIONS.map((option) => {
              const disabled = !available.has(option.name);
              return (
                <button
                  key={option.name}
                  type="button"
                  className={activeAov === option.name ? 'active' : ''}
                  disabled={disabled}
                  aria-pressed={activeAov === option.name}
                  title={disabled ? `${option.label} is unavailable for this render product` : option.label}
                  onClick={() => onChange('aov', option.name)}
                >
                  {option.label}
                </button>
              );
            })}
          </div>
          {aovStatus && <p className="inline-status">{aovStatus}</p>}
        </div>
      )}
    </section>
  );
}
