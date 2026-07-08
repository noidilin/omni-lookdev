export type StreamingConfig = {
  server: string;
  signalingPort: number;
};

export function resolveStreamingConfig(): StreamingConfig {
  const params = new URLSearchParams(window.location.search);
  const server =
    params.get('server') ||
    import.meta.env.VITE_SERVER_HOST ||
    window.location.hostname ||
    'localhost';
  const signalingPort = Number(params.get('signalingport') || import.meta.env.VITE_SIGNALING_PORT || 49100);
  return { server, signalingPort };
}

