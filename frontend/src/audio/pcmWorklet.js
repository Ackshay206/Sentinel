// AudioWorklet: resample mic audio to 16 kHz mono and emit 16-bit linear PCM.
// `sampleRate` is a global in the AudioWorkletGlobalScope (the context's rate).
class PCMWorklet extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buf = [];
    this._ratio = sampleRate / 16000; // e.g. 48000/16000 = 3
    this._pos = 0;
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;
    const ch = input[0];

    for (let i = 0; i < ch.length; i++) this._buf.push(ch[i]);

    const out = [];
    while (this._pos + this._ratio < this._buf.length) {
      out.push(this._buf[Math.floor(this._pos)]);
      this._pos += this._ratio;
    }

    const consumed = Math.floor(this._pos);
    if (consumed > 0) {
      this._buf.splice(0, consumed);
      this._pos -= consumed;
    }

    if (out.length) {
      const pcm = new Int16Array(out.length);
      for (let i = 0; i < out.length; i++) {
        const s = Math.max(-1, Math.min(1, out[i]));
        pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
      this.port.postMessage(pcm.buffer, [pcm.buffer]);
    }
    return true;
  }
}

registerProcessor('pcm-worklet', PCMWorklet);
