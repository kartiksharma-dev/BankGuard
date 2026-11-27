import React from 'react';
import {
  AlertCircle,
  Archive,
  CheckCircle2,
  Clock,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react';
import { Badge } from '../common/Badge';
import { InvestigationOutcome, InvestigationStatusRead } from '../../types/api';

interface StatusBadgeProps {
  status: InvestigationStatusRead;
}

export const InvestigationStatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const normalized = (status || '').toUpperCase();

  if (normalized === 'OPEN') {
    return (
      <Badge variant="warning" size="sm">
        <Clock className="w-3 h-3" />
        OPEN
      </Badge>
    );
  }

  if (normalized === 'IN_PROGRESS') {
    return (
      <Badge variant="info" size="sm">
        <AlertCircle className="w-3 h-3" />
        IN PROGRESS
      </Badge>
    );
  }

  if (normalized === 'RESOLVED') {
    return (
      <Badge variant="success" size="sm">
        <CheckCircle2 className="w-3 h-3" />
        RESOLVED
      </Badge>
    );
  }

  if (normalized === 'CLOSED') {
    return (
      <Badge variant="neutral" size="sm">
        <Archive className="w-3 h-3" />
        CLOSED (Legacy)
      </Badge>
    );
  }

  return (
    <Badge variant="neutral" size="sm">
      {status}
    </Badge>
  );
};

interface OutcomeBadgeProps {
  outcome: InvestigationOutcome | null | undefined;
}

export const InvestigationOutcomeBadge: React.FC<OutcomeBadgeProps> = ({ outcome }) => {
  if (outcome === 'CONFIRMED_FRAUD') {
    return (
      <Badge variant="danger" size="sm">
        <ShieldAlert className="w-3 h-3" />
        CONFIRMED FRAUD
      </Badge>
    );
  }

  if (outcome === 'LEGITIMATE') {
    return (
      <Badge variant="success" size="sm">
        <ShieldCheck className="w-3 h-3" />
        LEGITIMATE
      </Badge>
    );
  }

  return <span className="text-xs text-slate-500 italic">Pending</span>;
};

export function isInvestigationTerminal(status: InvestigationStatusRead): boolean {
  const normalized = (status || '').toUpperCase();
  return normalized === 'RESOLVED' || normalized === 'CLOSED';
}
