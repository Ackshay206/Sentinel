import { useCallback, useEffect, useRef, useState } from 'react';
import './App.css';

import { SentinelSocket } from './lib/ws';
import { startCapture, type StopCapture } from './audio/capture';
import type { Capabilities, Classification, ServerMessage, Stage } from './lib/types';
import { SCAM_LABEL, VECTOR_LABEL } from './lib/ui';

import { SeverityMeter } from './components/SeverityMeter';
import { StageLadder } from './components/StageLadder';
import { Transcript } from './components/Transcript';
import { RedFlagChips } from './components/RedFlagChips';
import { InterventionLog, type LogEntry } from './components/InterventionLog';
import { DemoPanel } from './components/DemoPanel';

const THRESHOLD = 70;

type Conn = 'connecting' | 'open' | 'closed';

function now() {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export default function App() {
  const sockRef = useRef<SentinelSocket | null>(null);
  const stopCaptureRef = useRef<StopCapture | null>(null);

  const [conn, setConn] = useState<Conn>('connecting');
  const [caps, setCaps] = useState<Capabilities>({ deepgram: false, openai: false, elevenlabs: false, twilio: false });
  const [listening, setListening] = useState(false);

  const [finals, setFinals] = useState<string[]>([]);
  const [interim, setInterim] = useState('');

  const [score, setScore] = useState(0);
  const [stage, setStage] = useState<Stage>('benign');
  const [scamType, setScamType] = useState('none');
  const [vector, setVector] = useState('');
  const [flags, setFlags] = useState<string[]>([]);
  const [fired, setFired] = useState(false);
  const [banner, setBanner] = useState<string | null>(null);

  const [log, setLog] = useState<LogEntry[]>([]);

  const handleMessage = useCallback((msg: ServerMessage) => {
    switch (msg.type) {
      case 'ready':
        setCaps(msg.capabilities);
        break;
      case 'transcript':
        if (msg.is_final) {
          setFinals((f) => [...f, msg.text]);
          setInterim('');
        } else {
          setInterim(msg.text);
        }
        break;
      case 'risk':
        setScore(msg.score);
        setStage(msg.stage);
        setScamType(msg.scam_type);
        setVector(msg.payment_vector ?? '');
        setFlags(msg.red_flags);
        setFired(msg.fired);
        break;
      case 'intervention':
        setBanner(msg.warning_text);
        setLog((l) => [{ ts: now(), kind: 'warning', text: msg.warning_text }, ...l]);
        break;
      case 'tts':
        try {
          const audio = new Audio(`data:${msg.mime};base64,${msg.audio_b64}`);
          void audio.play();
        } catch {
          /* autoplay blocked — banner still shows */
        }
        break;
      case 'sms':
        setLog((l) => [{ ts: now(), kind: 'sms', ok: msg.sent, text: msg.sent ? `Family alerted via SMS` : `SMS not sent (Twilio not configured)` }, ...l]);
        break;
      case 'reset_ok':
        setFinals([]); setInterim(''); setScore(0); setStage('benign');
        setScamType('none'); setVector(''); setFlags([]); setFired(false); setBanner(null);
        break;
    }
  }, []);

  useEffect(() => {
    const sock = new SentinelSocket(handleMessage, setConn);
    sock.connect();
    sockRef.current = sock;
    return () => {
      sock.close();
      stopCaptureRef.current?.();
    };
  }, [handleMessage]);

  const toggleListening = async () => {
    if (listening) {
      stopCaptureRef.current?.();
      stopCaptureRef.current = null;
      setListening(false);
      return;
    }
    try {
      const stop = await startCapture((buf) => sockRef.current?.sendAudio(buf));
      stopCaptureRef.current = stop;
      setListening(true);
    } catch (e) {
      alert('Microphone access is required to listen. ' + (e as Error).message);
    }
  };

  const reset = () => sockRef.current?.sendControl({ type: 'reset' });

  const demoStep = (line: string, cls: Classification) =>
    sockRef.current?.sendControl({ type: 'inject_classification', line, classification: cls });

  const capDot = (on: boolean, label: string) => (
    <span className={`cap ${on ? 'cap--on' : ''}`} title={`${label}: ${on ? 'connected' : 'not configured'}`}>
      <i /> {label}
    </span>
  );

  return (
    <div className={`app ${fired ? 'app--alarm' : ''}`}>
      <div className="alarm-vignette" aria-hidden />

      <header className="topbar">
        <div className="brand">
          <span className="brand__mark" />
          <span className="brand__name">SENTINEL</span>
          <span className="brand__tag">scam-interception guardian</span>
        </div>
        <div className="status">
          {capDot(caps.deepgram, 'ASR')}
          {capDot(caps.openai, 'Classifier')}
          {capDot(caps.elevenlabs, 'Voice')}
          {capDot(caps.twilio, 'SMS')}
          <span className={`conn conn--${conn}`}>
            <i /> {conn === 'open' ? 'live' : conn}
          </span>
        </div>
      </header>

      <main className="grid">
        {/* Left: transcript */}
        <section className="col col--left">
          <Transcript finals={finals} interim={interim} listening={listening} asrEnabled={caps.deepgram} />
        </section>

        {/* Center: the hero meter + readout */}
        <section className="col col--center">
          <SeverityMeter score={score} threshold={THRESHOLD} fired={fired} />
          <div className="readout">
            <span className="readout__kicker">Assessment</span>
            <span className="readout__scam">{SCAM_LABEL[scamType] ?? scamType}</span>
            {vector && VECTOR_LABEL[vector] && (
              <span className="readout__vector">ask&nbsp;→&nbsp;{VECTOR_LABEL[vector]}</span>
            )}
          </div>
        </section>

        {/* Right: trajectory + flags + log */}
        <section className="col col--right">
          <StageLadder stage={stage} />
          <RedFlagChips flags={flags} />
          <InterventionLog entries={log} />
        </section>
      </main>

      <footer className="controls">
        <button className={`btn btn--listen ${listening ? 'is-on' : ''}`} onClick={toggleListening} disabled={conn !== 'open'}>
          {listening ? '■ Stop listening' : '● Start listening'}
        </button>
        <button className="btn btn--ghost" onClick={reset} disabled={conn !== 'open'}>
          Reset call
        </button>
        <div className="controls__spacer" />
        <DemoPanel onStep={demoStep} onReset={reset} disabled={conn !== 'open'} />
      </footer>

      {banner && (
        <div className="intervene-banner" role="alert">
          <span className="intervene-banner__tag">SENTINEL INTERVENED</span>
          <span className="intervene-banner__text">{banner}</span>
          <button className="intervene-banner__x" onClick={() => setBanner(null)}>✕</button>
        </div>
      )}
    </div>
  );
}
