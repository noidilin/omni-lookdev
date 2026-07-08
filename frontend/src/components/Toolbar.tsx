type Props = {
  onFit: () => void;
  onReset: () => void;
  onClearSelection: () => void;
};

export function Toolbar({ onFit, onReset, onClearSelection }: Props) {
  return (
    <div className="toolbar" role="toolbar" aria-label="Viewport tools">
      <button type="button" title="Fit camera" aria-label="Fit camera" onClick={onFit}>⛶</button>
      <button type="button" title="Reset view" aria-label="Reset view" onClick={onReset}>↺</button>
      <button type="button" title="Clear selection" aria-label="Clear selection" onClick={onClearSelection}>×</button>
    </div>
  );
}

