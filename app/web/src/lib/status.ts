export type Status =
  | { kind: 'checking' }
  | { kind: 'up'; cluster: string; region: string; readOnly: boolean }
  | { kind: 'outage'; since: number };

export type HealthEvent =
  | { kind: 'success'; cluster: string; region: string; readOnly: boolean; at: number }
  | { kind: 'failure'; at: number };

export interface Machine {
  status: Status;
  consecutiveFailures: number;
  firstFailureAt: number | null;
  notice: string | null;
}

export const newMachine = (): Machine => ({ status: { kind: 'checking' }, consecutiveFailures: 0, firstFailureAt: null, notice: null });

export function formatDuration(ms: number): string {
  const seconds = Math.max(0, Math.round(ms / 1000));
  const minutes = Math.floor(seconds / 60);
  return minutes > 0 ? `${minutes} phút ${seconds % 60} giây` : `${seconds} giây`;
}

export function step(m: Machine, s: HealthEvent): Machine {
  if (s.kind === 'failure') {
    const firstFailureAt = m.firstFailureAt ?? s.at;
    const consecutiveFailures = m.consecutiveFailures + 1;
    const status: Status = consecutiveFailures >= 2 ? { kind: 'outage', since: firstFailureAt } : m.status;
    return { status, consecutiveFailures, firstFailureAt, notice: m.notice };
  }
  const notice = m.status.kind === 'outage' ? `Đã chạy lại sau ${formatDuration(s.at - m.status.since)}` : m.notice;
  return { status: { kind: 'up', cluster: s.cluster, region: s.region, readOnly: s.readOnly }, consecutiveFailures: 0, firstFailureAt: null, notice };
}

export const dismissNotice = (m: Machine): Machine => ({ ...m, notice: null });

export const pollInterval = (m: Machine): number => (m.status.kind === 'outage' ? 2000 : 5000);

const REGION_NAMES: Record<string, string> = { koreacentral: 'Hàn Quốc', japanwest: 'Nhật Bản' };

export function badge(t: Status): { text: string; color: 'green' | 'amber' | 'grey' } {
  if (t.kind === 'checking') return { text: 'Đang kiểm tra…', color: 'grey' };
  if (t.kind === 'outage') return { text: 'Đang khôi phục…', color: 'amber' };
  const cluster = t.cluster === 'primary' ? 'Cụm chính' : 'Cụm dự phòng';
  const region = REGION_NAMES[t.region] ?? t.region;
  return { text: region ? `${cluster} · ${region}` : cluster, color: 'green' };
}
