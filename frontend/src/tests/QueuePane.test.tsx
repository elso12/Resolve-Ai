import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueuePane } from '../pages/agent/inbox/QueuePane';
import type { QueueType } from '../pages/agent/inbox/types';

describe('QueuePane Component', () => {
  const mockCounts: Record<QueueType, number> = {
    all: 42,
    assigned: 7,
    unassigned: 15,
    high_priority: 3,
    resolved: 20,
  };

  it('renders all filter queues with correct labels and badge counts', () => {
    const handleSelectQueue = vi.fn();
    render(
      <QueuePane
        activeQueue="all"
        counts={mockCounts}
        onSelectQueue={handleSelectQueue}
      />
    );

    // Verify queue labels are present
    expect(screen.getByText('All Conversations')).toBeInTheDocument();
    expect(screen.getByText('Assigned to Me')).toBeInTheDocument();
    expect(screen.getByText('Unassigned')).toBeInTheDocument();
    expect(screen.getByText('SLA Risk / Urgent')).toBeInTheDocument();
    expect(screen.getByText('Resolved')).toBeInTheDocument();

    // Verify badge counts
    expect(screen.getByText('42')).toBeInTheDocument();
    expect(screen.getByText('7')).toBeInTheDocument();
    expect(screen.getByText('15')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('20')).toBeInTheDocument();
  });

  it('triggers onSelectQueue callback when a queue is clicked', () => {
    const handleSelectQueue = vi.fn();
    render(
      <QueuePane
        activeQueue="all"
        counts={mockCounts}
        onSelectQueue={handleSelectQueue}
      />
    );

    const urgentQueueBtn = screen.getByText('SLA Risk / Urgent').closest('button');
    expect(urgentQueueBtn).toBeTruthy();
    fireEvent.click(urgentQueueBtn!);

    expect(handleSelectQueue).toHaveBeenCalledWith('high_priority');
  });

  it('does not render badge count when count is 0', () => {
    const zeroCounts: Record<QueueType, number> = {
      all: 0,
      assigned: 0,
      unassigned: 0,
      high_priority: 0,
      resolved: 0,
    };
    render(
      <QueuePane
        activeQueue="all"
        counts={zeroCounts}
        onSelectQueue={vi.fn()}
      />
    );

    expect(screen.queryByText('0')).not.toBeInTheDocument();
  });
});
