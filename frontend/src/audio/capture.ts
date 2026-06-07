// Mic capture → AudioWorklet (16 kHz linear16 PCM) → callback.
// Returns a stop() that tears everything down.

import workletUrl from './pcmWorklet.js?url';

export type StopCapture = () => void;

export async function startCapture(
  onPcm: (buf: ArrayBuffer) => void,
): Promise<StopCapture> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
  });

  const ctx = new AudioContext();
  await ctx.audioWorklet.addModule(workletUrl);

  const source = ctx.createMediaStreamSource(stream);
  const node = new AudioWorkletNode(ctx, 'pcm-worklet');
  node.port.onmessage = (e: MessageEvent<ArrayBuffer>) => onPcm(e.data);

  // Some browsers won't run a worklet unless it reaches the destination;
  // route through a silent gain so nothing is actually heard.
  const silent = ctx.createGain();
  silent.gain.value = 0;
  source.connect(node);
  node.connect(silent);
  silent.connect(ctx.destination);

  return () => {
    try {
      node.port.onmessage = null;
      node.disconnect();
      source.disconnect();
      silent.disconnect();
      stream.getTracks().forEach((t) => t.stop());
      void ctx.close();
    } catch {
      /* ignore teardown races */
    }
  };
}
