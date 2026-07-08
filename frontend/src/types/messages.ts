export type StreamStatus = 'connecting' | 'connected' | 'failed' | 'disconnected';

export type StreamMessage<TPayload = Record<string, unknown>> = {
  event_type: string;
  payload: TPayload;
};

export type ServerEvent<TPayload = Record<string, unknown>> = {
  event_type: string;
  payload: TPayload;
};

export type RenderSettingCapability = {
  key: string;
  label: string;
  control: string;
  applies_at: 'immediate' | 'reload_required' | 'reconnect_required' | 'next_scene_load' | 'unsupported';
  apply_path: string;
  validated: boolean;
  min?: number | null;
  max?: number | null;
  step?: number | null;
};

