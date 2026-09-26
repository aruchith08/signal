import React from 'react';
import { SourceConflict } from '../../types/opportunity';
import { AlertTriangle, HelpCircle } from 'lucide-react';
import { Badge } from '../common/Badge';

interface ConflictAlertProps {
  conflicts: SourceConflict[];
}

export const ConflictAlert: React.FC<ConflictAlertProps> = ({ conflicts }) => {
  if (!conflicts || conflicts.length === 0) {
    return null;
  }

  return (
    <div className="p-4 rounded-xl border border-amber-700/40 bg-amber-950/20 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-amber-300">
          <AlertTriangle className="w-4 h-4 text-amber-400" />
          <h4 className="text-xs font-semibold uppercase tracking-wider">
            Source Discrepancies Detected ({conflicts.length})
          </h4>
        </div>
        <Badge variant="warning" size="xs">
          Human / Official Verification in Progress
        </Badge>
      </div>

      <div className="space-y-2">
        {conflicts.map((conflict, idx) => (
          <div
            key={conflict.id || idx}
            className="p-3 rounded-lg border border-amber-800/40 bg-slate-950/60 text-xs text-slate-300 space-y-1.5"
          >
            <div className="flex items-center justify-between font-mono">
              <span className="font-semibold text-amber-200 capitalize">
                Field: {conflict.field_name.replace(/_/g, ' ')}
              </span>
              <span className="text-[10px] uppercase px-1.5 py-0.5 rounded bg-amber-900/60 text-amber-300">
                {conflict.resolution_status || 'OPEN'}
              </span>
            </div>

            {conflict.resolved_value ? (
              <p className="text-emerald-300">
                Resolved official value: <span className="font-medium">{conflict.resolved_value}</span>
              </p>
            ) : (
              <div className="text-[11px] text-slate-400">
                Different sources report conflicting values for this field. The intelligence engine has downgraded this field's confidence until official confirmation is reached.
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
