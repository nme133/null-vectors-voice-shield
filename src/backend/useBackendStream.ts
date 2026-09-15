import { useCallback, useEffect, useRef, useState } from 'react';
import {
  BACKEND_WS_URL,
  BackendConnectionStatus,
  BackendStreamMessage,
  UseBackendStreamOptions,
} from './streamTypes';

export interface UseBackendStreamReturn {
  status: BackendConnectionStatus;
  connect: () => void;
  disconnect: () => void;
  sendAudio: (chunk: Float32Array) => void;
  sendControl: (type: string, data?: Record<string, unknown>) => void;
}

export function useBackendStream({
  url = BACKEND_WS_URL,
  onStatusChange,
  onMessage,
}: UseBackendStreamOptions = {}): UseBackendStreamReturn {
  const [status, setStatus] = useState<BackendConnectionStatus>('closed');

  const wsRef = useRef<WebSocket | null>(null);
  const intentionallyClosedRef = useRef(false);
  const handlersRef = useRef({ onStatusChange, onMessage });
  handlersRef.current = { onStatusChange, onMessage };

  const emitStatus = useCallback(
    (s: BackendConnectionStatus, info?: { error?: string }) => {
      setStatus(s);
      handlersRef.current.onStatusChange?.(s, info);
    },
    [],
  );

  const connect = useCallback(() => {
    if (wsRef.current) {
      const st = wsRef.current.readyState;
      if (st === WebSocket.OPEN || st === WebSocket.CONNECTING) return;
    }

    intentionallyClosedRef.current = false;
    emitStatus('connecting');

    const ws = new WebSocket(url);

    ws.onopen = () => {
      if (wsRef.current !== ws) return;
      emitStatus('open');
    };

    ws.onmessage = (evt) => {
      if (wsRef.current !== ws) return;
      if (typeof evt.data !== 'string') return;
      try {
        const parsed: unknown = JSON.parse(evt.data);
        if (
          typeof parsed === 'object' &&
          parsed !== null &&
          'type' in parsed
        ) {
          handlersRef.current.onMessage?.(parsed as BackendStreamMessage);
        }
      } catch {
        // Non-JSON text frame
      }
    };

    ws.onerror = () => {
      if (wsRef.current !== ws) return;
      emitStatus('error', { error: 'WebSocket connection failed' });
    };

    ws.onclose = (evt) => {
      if (wsRef.current !== ws) return;
      wsRef.current = null;
      if (intentionallyClosedRef.current) {
        emitStatus('closed');
      } else {
        emitStatus('error', {
          error: `Connection closed (code ${evt.code}${evt.reason ? ': ' + evt.reason : ''})`,
        });
      }
    };

    wsRef.current = ws;
  }, [url, emitStatus]);

  const disconnect = useCallback(() => {
    const ws = wsRef.current;
    if (!ws) return;

    intentionallyClosedRef.current = true;
    ws.onopen = null;
    ws.onmessage = null;
    ws.onerror = null;
    ws.onclose = null;

    try {
      ws.close();
    } catch {
      // Ignore close errors
    }

    wsRef.current = null;
    emitStatus('closed');
  }, [emitStatus]);

const sendAudio = useCallback((chunk: Float32Array) => {
  const ws = wsRef.current;

  if (!ws || ws.readyState !== WebSocket.OPEN) {
    console.log("AUDIO NOT SENT — WS state:", ws?.readyState);
    return;
  }

  console.log("🔥 SENDING AUDIO:", chunk.length, "samples");

  const ab = new ArrayBuffer(chunk.byteLength);
  new Float32Array(ab).set(chunk);
  ws.send(ab);
}, []);

  const sendControl = useCallback(
    (type: string, data?: Record<string, unknown>) => {
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) return;

      const msg: Record<string, unknown> = { type };
      if (data !== undefined) msg.data = data;
      ws.send(JSON.stringify(msg));
    },
    [],
  );

  useEffect(() => {
    return () => {
      const ws = wsRef.current;
      if (ws) {
        intentionallyClosedRef.current = true;
        ws.onopen = null;
        ws.onmessage = null;
        ws.onerror = null;
        ws.onclose = null;
        try {
          ws.close();
        } catch {
          // Ignore
        }
        wsRef.current = null;
      }
    };
  }, []);

  return { status, connect, disconnect, sendAudio, sendControl };
}
