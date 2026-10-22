import { describe, expect, it } from 'vitest';

import { dismissNotice, step, formatDuration, pollInterval, newMachine, badge } from './status';

const up = (at: number) => ({ kind: 'success' as const, cluster: 'primary', region: 'koreacentral', readOnly: false, at });
const error = (at: number) => ({ kind: 'failure' as const, at });

describe('máy trạng thái của nhãn', () => {
  it('một lần lỗi chưa chuyển sự cố, hai lần mới chuyển, tính từ lần lỗi đầu', () => {
    let m = step(newMachine(), up(0));
    m = step(m, error(1000));
    expect(m.status.kind).toBe('up');
    m = step(m, error(6000));
    expect(m.status).toEqual({ kind: 'outage', since: 1000 });
    expect(pollInterval(m)).toBe(2000);
  });

  it('chạy lại thì báo thời gian mất kết nối và về khoảng 5 giây', () => {
    let m = step(step(step(newMachine(), up(0)), error(1000)), error(3000));
    m = step(m, { ...up(253_000), cluster: 'standby' });
    expect(m.status).toEqual({ kind: 'up', cluster: 'standby', region: 'koreacentral', readOnly: false });
    expect(m.notice).toBe('Đã chạy lại sau 4 phút 12 giây');
    expect(pollInterval(m)).toBe(5000);
    expect(dismissNotice(m).notice).toBeNull();
  });

  it('một lần lỗi rồi thành công thì không báo gì', () => {
    const m = step(step(step(newMachine(), up(0)), error(1000)), up(2000));
    expect(m.notice).toBeNull();
    expect(m.consecutiveFailures).toBe(0);
  });

  it('chữ trên nhãn', () => {
    expect(badge({ kind: 'checking' })).toEqual({ text: 'Đang kiểm tra…', color: 'grey' });
    expect(badge({ kind: 'outage', since: 0 })).toEqual({ text: 'Đang khôi phục…', color: 'amber' });
    expect(badge({ kind: 'up', cluster: 'primary', region: 'koreacentral', readOnly: false }).text).toBe('Cụm chính · Hàn Quốc');
    expect(badge({ kind: 'up', cluster: 'standby', region: 'thu', readOnly: false }).text).toBe('Cụm dự phòng · thu');
    expect(badge({ kind: 'up', cluster: 'primary', region: '', readOnly: false }).text).toBe('Cụm chính');
  });

  it('định dạng khoảng thời gian', () => {
    expect(formatDuration(45_400)).toBe('45 giây');
    expect(formatDuration(60_000)).toBe('1 phút 0 giây');
    expect(formatDuration(-5)).toBe('0 giây');
  });
});
