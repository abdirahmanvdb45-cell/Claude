// Neural network particle sphere — canvas 2D with perspective projection

const ParticleSystem = (() => {
  const PARTICLE_COUNT = 180;
  const RADIUS = 140;
  const CONNECTION_DIST = 72;
  const FOV = 400;

  let canvas, ctx, W, H, cx, cy;
  let particles = [];
  let state = 'idle'; // idle | listening | thinking | speaking
  let animFrame;
  let time = 0;
  let pulseIntensity = 0;
  let targetPulse = 0;

  const STATE_CONFIG = {
    idle:        { speed: 0.0004, color: [120, 180, 255], glow: 0.3, pulse: 0.0 },
    listening:   { speed: 0.0012, color: [80, 255, 180],  glow: 0.7, pulse: 0.6 },
    transcribing:{ speed: 0.0008, color: [100, 200, 255], glow: 0.5, pulse: 0.4 },
    thinking:    { speed: 0.0022, color: [80, 140, 255],  glow: 1.0, pulse: 1.0 },
    speaking:    { speed: 0.0016, color: [160, 220, 255], glow: 0.8, pulse: 0.7 },
  };

  function init(canvasEl) {
    canvas = canvasEl;
    ctx = canvas.getContext('2d');
    W = canvas.width;
    H = canvas.height;
    cx = W / 2;
    cy = H / 2;
    createParticles();
    loop();
  }

  function createParticles() {
    particles = [];
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      // Fibonacci sphere distribution
      const phi = Math.acos(1 - 2 * (i + 0.5) / PARTICLE_COUNT);
      const theta = Math.PI * (1 + Math.sqrt(5)) * i;
      particles.push({
        bx: RADIUS * Math.sin(phi) * Math.cos(theta),
        by: RADIUS * Math.sin(phi) * Math.sin(theta),
        bz: RADIUS * Math.cos(phi),
        rx: 0, ry: 0, rz: 0,
        vx: (Math.random() - 0.5) * 0.003,
        vy: (Math.random() - 0.5) * 0.003,
        vz: (Math.random() - 0.5) * 0.003,
        size: 1.2 + Math.random() * 1.6,
      });
    }
  }

  function rotatePoint(p, ax, ay, az) {
    let { bx: x, by: y, bz: z } = p;
    // rotation around Y
    let cos = Math.cos(ay), sin = Math.sin(ay);
    let nx = x * cos + z * sin, nz = -x * sin + z * cos;
    x = nx; z = nz;
    // rotation around X
    cos = Math.cos(ax); sin = Math.sin(ax);
    let ny = y * cos - z * sin; nz = y * sin + z * cos;
    y = ny; z = nz;
    return { x, y, z };
  }

  function project(x, y, z) {
    const scale = FOV / (FOV + z + RADIUS);
    return {
      sx: cx + x * scale,
      sy: cy + y * scale,
      scale,
    };
  }

  function loop() {
    animFrame = requestAnimationFrame(loop);
    render();
  }

  function render() {
    time += 1;
    const cfg = STATE_CONFIG[state] || STATE_CONFIG.idle;

    // Smooth pulse
    targetPulse = cfg.pulse;
    pulseIntensity += (targetPulse - pulseIntensity) * 0.05;

    ctx.clearRect(0, 0, W, H);

    const speed = cfg.speed;
    const ax = speed * 0.7;
    const ay = speed;

    const [r, g, b] = cfg.color;

    // Projected points
    const pts = particles.map(p => {
      const { x, y, z } = rotatePoint(p, time * ax, time * ay, 0);
      return { ...project(x, y, z), z, raw: { x, y, z } };
    });

    // Sort back-to-front
    pts.sort((a, b) => a.z - b.z);

    // Draw connections
    for (let i = 0; i < pts.length; i++) {
      for (let j = i + 1; j < pts.length; j++) {
        const dx = pts[i].raw.x - pts[j].raw.x;
        const dy = pts[i].raw.y - pts[j].raw.y;
        const dz = pts[i].raw.z - pts[j].raw.z;
        const dist = Math.sqrt(dx*dx + dy*dy + dz*dz);
        if (dist < CONNECTION_DIST) {
          const alpha = (1 - dist / CONNECTION_DIST) * 0.35 * (0.5 + 0.5 * pulseIntensity);
          const depthFade = Math.max(0, (pts[i].z + RADIUS) / (RADIUS * 2));
          ctx.beginPath();
          ctx.moveTo(pts[i].sx, pts[i].sy);
          ctx.lineTo(pts[j].sx, pts[j].sy);
          ctx.strokeStyle = `rgba(${r},${g},${b},${alpha * depthFade})`;
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }
      }
    }

    // Draw particles
    for (const pt of pts) {
      const depthScale = Math.max(0.2, (pt.z + RADIUS * 1.5) / (RADIUS * 3));
      const baseAlpha = 0.4 + 0.6 * depthScale;
      const glowPulse = 1 + pulseIntensity * 0.5 * Math.sin(time * 0.08 + pt.z * 0.02);
      const radius = (particles[pts.indexOf(pt)]?.size || 1.5) * depthScale * glowPulse;

      // Glow
      const grd = ctx.createRadialGradient(pt.sx, pt.sy, 0, pt.sx, pt.sy, radius * 4);
      grd.addColorStop(0, `rgba(${r},${g},${b},${baseAlpha * cfg.glow * 0.6})`);
      grd.addColorStop(1, `rgba(${r},${g},${b},0)`);
      ctx.beginPath();
      ctx.arc(pt.sx, pt.sy, radius * 4, 0, Math.PI * 2);
      ctx.fillStyle = grd;
      ctx.fill();

      // Core
      ctx.beginPath();
      ctx.arc(pt.sx, pt.sy, radius, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${r},${g},${b},${baseAlpha})`;
      ctx.fill();
    }

    // Center glow
    if (pulseIntensity > 0.1) {
      const pulseR = 80 + 40 * Math.sin(time * 0.06);
      const grd = ctx.createRadialGradient(cx, cy, 0, cx, cy, pulseR);
      grd.addColorStop(0, `rgba(${r},${g},${b},${0.12 * pulseIntensity})`);
      grd.addColorStop(1, `rgba(${r},${g},${b},0)`);
      ctx.beginPath();
      ctx.arc(cx, cy, pulseR, 0, Math.PI * 2);
      ctx.fillStyle = grd;
      ctx.fill();
    }
  }

  function setState(s) {
    state = s;
  }

  return { init, setState };
})();
