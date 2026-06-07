import { useEffect, useRef, useState } from 'react';
import './App.css';
import { SentinelSocket } from './lib/ws';
import { startCapture, type StopCapture } from './audio/capture';

// Minimal page for the second device (phone) = the CALLER / scammer mic.
// Open with ?caller=1. Its audio is transcribed as "Caller" and bridged to the
// guardian agent during a takeover. Hume does NOT listen to this side.
export default function CallerApp() {
  const sockRef = useRef<SentinelSocket | null>(null);
  const stopRef = useRef<StopCapture | null>(null);
  const [conn, setConn] = useState<'connecting' | 'open' | 'closed'>('connecting');
  const [live, setLive] = useState(false);

  useEffect(() => {
    const sock = new SentinelSocket(() => {}, setConn);
    sock.connect('caller');
    sockRef.current = sock;
    return () => {
      sock.close();
      stopRef.current?.();
    };
  }, []);

  const toggle = async () => {
    if (live) {
      stopRef.current?.();
      stopRef.current = null;
      setLive(false);
      return;
    }
    try {
      const stop = await startCapture((buf) => sockRef.current?.sendAudio(buf));
      stopRef.current = stop;
      setLive(true);
    } catch (e) {
      alert('Microphone access is required. ' + (e as Error).message);
    }
  };

  return (
    <div className="callerpage">
      <div className="callerpage__card">
        <span className="callerpage__badge">CALLER MIC</span>
        <h1>You are the caller</h1>
        <p>
          This phone is the <b>caller (scammer)</b> side of the call. Speak the scammer's lines — the
          laptop is the victim. Sentinel listens to both, but only reads the victim's emotion.
        </p>
        <button
          className={`btn btn--scam callerpage__btn ${live ? 'is-on' : ''}`}
          onClick={toggle}
          disabled={conn !== 'open'}
        >
          {live ? '■ Stop caller mic' : '● Start caller mic'}
        </button>
        <span className={`conn conn--${conn}`}>
          <i /> {conn === 'open' ? 'connected to session' : conn}
        </span>
      </div>
    </div>
  );
}
