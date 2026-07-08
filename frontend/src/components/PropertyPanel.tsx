type Props = {
  selectedPath: string;
  properties: Record<string, unknown> | null;
};

export function PropertyPanel({ selectedPath, properties }: Props) {
  return (
    <section className="pane property-pane">
      <div className="pane-header">
        <h2>Properties</h2>
      </div>
      {!selectedPath && <p className="empty">Select a prim to inspect its properties.</p>}
      {selectedPath && !properties && <p className="empty">Loading properties.</p>}
      {properties && (
        <div className="property-grid">
          {Object.entries(properties).map(([key, value]) => (
            <div className="property-row" key={key}>
              <span className="property-key">{key}</span>
              <span className="property-value">{formatValue(value)}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

