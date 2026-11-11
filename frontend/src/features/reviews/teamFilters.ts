export function teamAppraisalParams(status: string): Record<string, string> {
  if (status === 'READY_FOR_RELEASE') return { state: 'HR_APPROVED', release_ready: 'true' };
  return status ? { state: status } : {};
}
