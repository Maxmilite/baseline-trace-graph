interface Props {
  showMedium: boolean;
  onToggleMedium: () => void;
}

export default function FilterBar({ showMedium, onToggleMedium }: Props) {
  return (
    <div className="filter-bar">
      <label className="filter-toggle">
        <input
          type="checkbox"
          checked={showMedium}
          onChange={onToggleMedium}
        />
        Show medium edges
      </label>
    </div>
  );
}
