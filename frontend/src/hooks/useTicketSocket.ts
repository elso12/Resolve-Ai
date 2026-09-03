import { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';

export interface ActiveViewer {
  user_id: number;
  full_name: string;
  email: string;
  role: string;
  last_heartbeat: number;
}

export interface TypingAgent {
  user_id: number;
  full_name: string;
}

interface UseTicketSocketOptions {
  ticketId: string | number | undefined | null;
  onMessageReceived?: (message: any) => void;
  onStatusUpdated?: (status: string, updatedBy?: string) => void;
}

export const useTicketSocket = ({
  ticketId,
  onMessageReceived,
  onStatusUpdated,
}: UseTicketSocketOptions) => {
  const { user } = useAuth();
  const [activeViewers, setActiveViewers] = useState<ActiveViewer[]>([]);
  const [typingAgents, setTypingAgents] = useState<TypingAgent[]>([]);
  const [isConnected, setIsConnected] = useState(false);

  const socketRef = useRef<WebSocket | null>(null);
  const heartbeatTimerRef = useRef<any>(null);
  const typingTimersRef = useRef<Map<number, any>>(new Map());

  // Keep latest callbacks in refs to avoid socket reconnect churn
  const onMessageRef = useRef(onMessageReceived);
  onMessageRef.current = onMessageReceived;
  const onStatusRef = useRef(onStatusUpdated);
  onStatusRef.current = onStatusUpdated;

  // Send typing state through socket
  const sendTyping = useCallback(
    (isTyping: boolean) => {
      if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
        socketRef.current.send(JSON.stringify({ type: 'typing', is_typing: isTyping }));
      }
    },
    []
  );

  useEffect(() => {
    if (!ticketId) {
      setActiveViewers([]);
      setTypingAgents([]);
      setIsConnected(false);
      return;
    }

    const token = localStorage.getItem('token');
    if (!token) return;

    // Determine WS protocol and host
    const isSecure = window.location.protocol === 'https:';
    const wsProto = isSecure ? 'wss:' : 'ws:';
    // In dev, frontend is 5173/3000 while backend is 8000
    const host = window.location.port ? `${window.location.hostname}:8000` : window.location.host;
    const wsUrl = `${wsProto}//${host}/api/v1/ws/tickets/${ticketId}?token=${encodeURIComponent(token)}`;

    let socket: WebSocket | null = null;
    let reconnectTimeout: any = null;
    let isCleanedUp = false;

    const connect = () => {
      if (isCleanedUp) return;

      try {
        socket = new WebSocket(wsUrl);
        socketRef.current = socket;

        socket.onopen = () => {
          if (isCleanedUp) return;
          setIsConnected(true);

          // Start periodic 15-second heartbeat
          heartbeatTimerRef.current = setInterval(() => {
            if (socket && socket.readyState === WebSocket.OPEN) {
              socket.send(JSON.stringify({ type: 'heartbeat' }));
            }
          }, 15000);
        };

        socket.onmessage = (event) => {
          if (isCleanedUp) return;
          try {
            const payload = JSON.parse(event.data);
            const { type, data } = payload;

            switch (type) {
              case 'AGENT_VIEWING': {
                // Filter out self so activeViewers only contains other colliding agents
                const viewers: ActiveViewer[] = data.viewers || [];
                const otherViewers = viewers.filter((v) => !user || String(v.user_id) !== String(user.id));
                setActiveViewers(otherViewers);
                break;
              }

              case 'AGENT_TYPING': {
                const typingUserId = data.user_id;
                const typingName = data.full_name;
                const isTyping = data.is_typing;

                // Ignore typing events from self
                if (user && String(typingUserId) === String(user.id)) break;

                // Clear previous auto-expire timer for this user
                const existingTimer = typingTimersRef.current.get(typingUserId);
                if (existingTimer) {
                  clearTimeout(existingTimer);
                  typingTimersRef.current.delete(typingUserId);
                }

                if (isTyping) {
                  setTypingAgents((prev) => {
                    const exists = prev.some((a) => a.user_id === typingUserId);
                    if (!exists) {
                      return [...prev, { user_id: typingUserId, full_name: typingName }];
                    }
                    return prev;
                  });

                  // Automatically clear typing status after 3.5 seconds of inactivity
                  const timer = setTimeout(() => {
                    setTypingAgents((prev) => prev.filter((a) => a.user_id !== typingUserId));
                    typingTimersRef.current.delete(typingUserId);
                  }, 3500);
                  typingTimersRef.current.set(typingUserId, timer);
                } else {
                  setTypingAgents((prev) => prev.filter((a) => a.user_id !== typingUserId));
                }
                break;
              }

              case 'NEW_MESSAGE': {
                if (onMessageRef.current && data.message) {
                  onMessageRef.current(data.message);
                }
                break;
              }

              case 'TICKET_STATUS_UPDATED': {
                if (onStatusRef.current && data.status) {
                  onStatusRef.current(data.status, data.updated_by);
                }
                break;
              }

              default:
                break;
            }
          } catch {
            // Failed to parse message
          }
        };

        socket.onclose = () => {
          setIsConnected(false);
          if (heartbeatTimerRef.current) {
            clearInterval(heartbeatTimerRef.current);
          }
          // Attempt reconnect after 3 seconds if not unmounted
          if (!isCleanedUp) {
            reconnectTimeout = setTimeout(connect, 3000);
          }
        };

        socket.onerror = () => {
          // Socket error
        };
      } catch {
        // Failed to initialize WebSocket
      }
    };

    connect();

    return () => {
      isCleanedUp = true;
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (heartbeatTimerRef.current) clearInterval(heartbeatTimerRef.current);
      typingTimersRef.current.forEach((t) => clearTimeout(t));
      typingTimersRef.current.clear();
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
      setActiveViewers([]);
      setTypingAgents([]);
      setIsConnected(false);
    };
  }, [ticketId, user]);

  return {
    activeViewers,
    typingAgents,
    isConnected,
    sendTyping,
  };
};
