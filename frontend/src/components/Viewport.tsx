import { useStreaming } from '../streaming/StreamingProvider';

export function Viewport() {
  const { sendMessage, status } = useStreaming();
  const setActive = (active: boolean) => sendMessage({ event_type: 'setViewportInputActive', payload: { active } });
  return (
    <div
      className="viewport"
      onPointerEnter={() => setActive(true)}
      onPointerDown={() => setActive(true)}
      onPointerLeave={() => setActive(false)}
    >
      <video id="remote-video" muted autoPlay playsInline />
      <audio id="remote-audio" />
      {status !== 'connected' && <div className="viewport-state">{status}</div>}
    </div>
  );
}

