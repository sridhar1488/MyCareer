const statuses: Record<string, string> = {
  DRAFT: 'Draft', NOT_STARTED: 'Not started', SUBMITTED: 'Submitted',
  UNDER_REVIEW: 'Under review', RETURNED_FOR_REVISION: 'Returned for revision',
  HR_REVIEW: 'HR review', HR_APPROVED: 'HR approved', FINALIZED: 'Finalized',
  RELEASED: 'Released', ACKNOWLEDGED: 'Acknowledged', ACTIVE: 'Active',
  CLOSED: 'Closed', DRAFT_SAVED: 'Draft saved', SUBMITTED_FOR_HR: 'Submitted to HR',
};

export function statusLabel(state: string) {
  return statuses[state] ?? state.replaceAll('_', ' ').toLowerCase().replace(/^./, c => c.toUpperCase());
}

export function cycleLabel(text: string) {
  return text.replace(/\bPerformace\b/g, 'Performance');
}

export function competencyLabel(text: string) {
  return text.replace(/\bCommuniction\b/g, 'Communication').replace(/\s*:\s*$/, '');
}
