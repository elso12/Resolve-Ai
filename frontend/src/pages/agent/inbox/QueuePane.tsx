import React from 'react';
import { Inbox, User, Users, AlertTriangle, CheckCircle2 } from 'lucide-react';
import type { QueueType, Queue } from './types';

interface QueuePaneProps {
  activeQueue: QueueType;
  counts: Record<QueueType, number>;
  onSelectQueue: (queueId: QueueType) => void;
}

export const QueuePane: React.FC<QueuePaneProps> = ({ activeQueue, counts, onSelectQueue }) => {
  const queues: Queue[] = [
    { id: 'all', label: 'All Conversations', icon: Inbox, count: counts.all ?? 0 },
    { id: 'assigned', label: 'Assigned to Me', icon: User, count: counts.assigned ?? 0 },
    { id: 'unassigned', label: 'Unassigned', icon: Users, count: counts.unassigned ?? 0 },
    { id: 'high_priority', label: 'SLA Risk / Urgent', icon: AlertTriangle, count: counts.high_priority ?? 0 },
    { id: 'resolved', label: 'Resolved', icon: CheckCircle2, count: counts.resolved ?? 0 },
  ];

  return (
    <div className="w-64 border-r border-neutral-800 bg-neutral-950 flex flex-col h-full overflow-y-auto shrink-0">
      <div className="p-4 border-b border-neutral-800">
        <h2 className="text-xs font-semibold text-neutral-500 uppercase tracking-wider">Smart Queues</h2>
      </div>
      <div className="p-3 space-y-1">
        {queues.map((queue) => (
          <button
            key={queue.id}
            onClick={() => onSelectQueue(queue.id)}
            className={`w-full flex items-center justify-between px-3 py-2 rounded-md text-sm transition-colors ${
              activeQueue === queue.id
                ? 'bg-neutral-800 text-white'
                : 'text-neutral-400 hover:text-white hover:bg-neutral-800/50'
            }`}
          >
            <div className="flex items-center gap-3">
              <queue.icon size={16} className={queue.id === 'high_priority' ? 'text-red-400' : ''} />
              <span className="font-medium">{queue.label}</span>
            </div>
            {queue.count > 0 && (
              <span
                className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                  activeQueue === queue.id ? 'bg-neutral-700 text-white' : 'bg-neutral-800 text-neutral-400'
                }`}
              >
                {queue.count}
              </span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
};
