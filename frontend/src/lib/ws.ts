import type { ServerMessage } from './types';

const WS_URL =
  import.meta.env.VITE_SENTINEL_WS ?? 'ws://localhost:8000/ws/session';

type Handler = (msg: ServerMessage) => void;
type StatusHandler = (status: 'connecting' | 'open' | 'closed') => void;

export class SentinelSocket {
  private ws: WebSocket | null = null;
  private onMessage: Handler;
  private onStatus: StatusHandler;

  constructor(onMessage: Handler, onStatus: StatusHandler) {
    this.onMessage = onMessage;
    this.onStatus = onStatus;
  }

  connect() {
    this.onStatus('connecting');
    const ws = new WebSocket(WS_URL);
    ws.binaryType = 'arraybuffer';
    ws.onopen = () => this.onStatus('open');
    ws.onclose = () => this.onStatus('closed');
    ws.onerror = () => this.onStatus('closed');
    ws.onmessage = (ev) => {
      try {
        this.onMessage(JSON.parse(ev.data) as ServerMessage);
      } catch {
        /* binary or malformed — ignore */
      }
    };
    this.ws = ws;
  }

  get ready() {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  sendAudio(buf: ArrayBuffer) {
    if (this.ready) this.ws!.send(buf);
  }

  sendControl(obj: unknown) {
    if (this.ready) this.ws!.send(JSON.stringify(obj));
  }

  close() {
    this.ws?.close();
    this.ws = null;
  }
}
