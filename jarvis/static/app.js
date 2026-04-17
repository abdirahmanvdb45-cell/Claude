(() => {
  const canvas = document.getElementById('canvas');
  const statusEl = document.getElementById('status');
  const transcriptEl = document.getElementById('transcript');
  const responseEl = document.getElementById('response');
  const micHint = document.getElementById('mic-hint');

  ParticleSystem.init(canvas);

  const WS_URL = `ws://${location.host}/ws`;
  let ws = null;
  let mediaRecorder = null;
  let audioChunks = [];
  let isRecording = false;
  let stream = null;
  let wsReady = false;

  function setStatus(text, dotAnim = false) {
    statusEl.textContent = text;
    statusEl.className = dotAnim ? 'dot-anim' : '';
  }

  function connectWS() {
    ws = new WebSocket(WS_URL);
    ws.binaryType = 'arraybuffer';

    ws.onopen = () => {
      wsReady = true;
      setStatus('online');
      ParticleSystem.setState('idle');
    };

    ws.onclose = () => {
      wsReady = false;
      setStatus('reconnecting', true);
      setTimeout(connectWS, 2000);
    };

    ws.onerror = () => {
      ws.close();
    };

    ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        // Audio response — play it
        const blob = new Blob([event.data], { type: 'audio/mpeg' });
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        audio.onended = () => URL.revokeObjectURL(url);
        audio.play().catch(console.error);
        return;
      }

      const msg = JSON.parse(event.data);

      switch (msg.status) {
        case 'transcribing':
          setStatus('transcribing', true);
          ParticleSystem.setState('transcribing');
          break;

        case 'thinking':
          setStatus('thinking', true);
          transcriptEl.textContent = `"${msg.transcript}"`;
          responseEl.textContent = '';
          ParticleSystem.setState('thinking');
          break;

        case 'speaking':
          setStatus('speaking', true);
          responseEl.textContent = msg.text;
          ParticleSystem.setState('speaking');
          break;

        case 'idle':
          setStatus('online');
          ParticleSystem.setState('idle');
          if (msg.error === 'no_speech') {
            transcriptEl.textContent = '';
          }
          break;
      }
    };
  }

  async function initMic() {
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    } catch (e) {
      setStatus('mic access denied');
      console.error(e);
    }
  }

  function startRecording() {
    if (!stream || isRecording) return;
    audioChunks = [];
    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus'
      : 'audio/webm';
    mediaRecorder = new MediaRecorder(stream, { mimeType });
    mediaRecorder.ondataavailable = e => {
      if (e.data.size > 0) audioChunks.push(e.data);
    };
    mediaRecorder.start(100);
    isRecording = true;
    setStatus('listening', true);
    ParticleSystem.setState('listening');
    micHint.style.opacity = '0';
  }

  function stopRecording() {
    if (!isRecording || !mediaRecorder) return;
    isRecording = false;
    micHint.style.opacity = '1';

    mediaRecorder.onstop = () => {
      const blob = new Blob(audioChunks, { type: mediaRecorder.mimeType });
      if (ws && ws.readyState === WebSocket.OPEN && blob.size > 0) {
        blob.arrayBuffer().then(buf => ws.send(buf));
      }
    };
    mediaRecorder.stop();
  }

  // Keyboard: hold Space
  document.addEventListener('keydown', e => {
    if (e.code === 'Space' && !e.repeat) {
      e.preventDefault();
      startRecording();
    }
  });
  document.addEventListener('keyup', e => {
    if (e.code === 'Space') {
      e.preventDefault();
      stopRecording();
    }
  });

  // Mouse/touch: click & hold on canvas
  const wrap = document.getElementById('canvas-wrap');
  wrap.addEventListener('mousedown', () => startRecording());
  wrap.addEventListener('mouseup', () => stopRecording());
  wrap.addEventListener('mouseleave', () => { if (isRecording) stopRecording(); });
  wrap.addEventListener('touchstart', e => { e.preventDefault(); startRecording(); });
  wrap.addEventListener('touchend', e => { e.preventDefault(); stopRecording(); });

  // Boot
  (async () => {
    await initMic();
    connectWS();
  })();
})();
