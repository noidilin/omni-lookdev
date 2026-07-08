import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { AppStreamer, StreamType } from '@nvidia/ov-web-rtc';
import type { ServerEvent, StreamMessage, StreamStatus } from '../types/messages';
import { resolveStreamingConfig } from './streamingConfig';

type StreamingContextValue = {
  status: StreamStatus;
  errorMessage: string;
  sendMessage: (message: StreamMessage) => void;
  onCustomEvent: (handler: (event: ServerEvent) => void) => () => void;
  config: { server: string; signalingPort: number };
};

const StreamingContext = createContext<StreamingContextValue | null>(null);

export function StreamingProvider({ children }: { children: React.ReactNode }) {
  const config = useMemo(() => resolveStreamingConfig(), []);
  const [status, setStatus] = useState<StreamStatus>('connecting');
  const [errorMessage, setErrorMessage] = useState('');
  const connectedRef = useRef(false);
  const handlersRef = useRef(new Set<(event: ServerEvent) => void>());

  const onCustomEvent = useCallback((handler: (event: ServerEvent) => void) => {
    handlersRef.current.add(handler);
    return () => handlersRef.current.delete(handler);
  }, []);

  const sendMessage = useCallback((message: StreamMessage) => {
    if (!connectedRef.current) return;
    void AppStreamer.sendMessage(message).catch(() => undefined);
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function connect() {
      setStatus('connecting');
      try {
        await AppStreamer.connect({
          streamSource: StreamType.DIRECT,
          streamConfig: {
            videoElementId: 'remote-video',
            audioElementId: 'remote-audio',
            server: config.server,
            signalingPort: config.signalingPort,
            nativeTouchEvents: true,
            fps: 60,
            maxReconnects: 5,
            reconnectDelay: 3000,
            onStart: () => {
              if (cancelled) return;
              connectedRef.current = true;
              setStatus('connected');
            },
            onUpdate: () => undefined,
            onCustomEvent: (event: unknown) => {
              if (!isServerEvent(event)) return;
              handlersRef.current.forEach((handler) => handler(event));
            },
            onStop: () => {
              connectedRef.current = false;
              if (!cancelled) setStatus('disconnected');
            },
            onTerminate: () => {
              connectedRef.current = false;
              if (!cancelled) setStatus('disconnected');
            },
          },
        });
      } catch (error) {
        if (cancelled) return;
        connectedRef.current = false;
        setStatus('failed');
        setErrorMessage(error instanceof Error ? error.message : String(error));
      }
    }
    void connect();
    return () => {
      cancelled = true;
      connectedRef.current = false;
      void AppStreamer.terminate?.().catch?.(() => undefined);
    };
  }, [config.server, config.signalingPort]);

  const value = useMemo(
    () => ({ status, errorMessage, sendMessage, onCustomEvent, config }),
    [status, errorMessage, sendMessage, onCustomEvent, config],
  );

  return <StreamingContext.Provider value={value}>{children}</StreamingContext.Provider>;
}

export function useStreaming() {
  const value = useContext(StreamingContext);
  if (!value) throw new Error('useStreaming must be used inside StreamingProvider');
  return value;
}

function isServerEvent(value: unknown): value is ServerEvent {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as { event_type?: unknown; payload?: unknown };
  return typeof candidate.event_type === 'string' && typeof candidate.payload === 'object';
}
