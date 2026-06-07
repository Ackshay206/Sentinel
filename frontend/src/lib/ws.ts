import type { ServerMessage } from './types';

// Derive the backend host from the page so the phone (on the LAN IP) reaches
// the same backend as the laptop. Override with VITE_SENTINEL_WS if needed.
const WS_URL =
  import.meta.env.VITE_SENTINEL_WS ??
  `ws://${window.location.hostname}:8000/ws/session`;

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

  connect(role: 'victim' | 'caller' = 'victim') {
    this.onStatus('connecting');
    const ws = new WebSocket(WS_URL);
    ws.binaryType = 'arraybuffer';
    ws.onopen = () => {
      this.onStatus('open');
      ws.send(JSON.stringify({ type: 'join', role })); // role handshake (first message)
    };
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
