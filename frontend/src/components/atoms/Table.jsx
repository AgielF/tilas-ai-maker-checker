import { memo } from 'react';

/**
 * Table — dark theme table wrapper with consistent styling.
 * Usage: <Table><thead>...</thead><tbody>...</tbody></Table>
 */
function Table({ children, className = '' }) {
  return (
    <div className={`border border-[var(--border-dark)] rounded-lg overflow-hidden ${className}`}>
      <table className="w-full text-sm">
        {children}
      </table>
    </div>
  );
}

export default memo(Table);