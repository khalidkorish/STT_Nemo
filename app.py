# app.py
# ============================================================
# Arabic STT — Streamlit Frontend (Standalone)
#
# Deployable to Streamlit Cloud with zero local dependencies.
# Connects to a remote FastAPI backend via:
#   - HTTP REST  → /transcribe/file
#   - WebSocket  → /ws/stream  (mic streaming)
#
# Tabs:
#   🎤  Live microphone  — WebSocket streaming
#   📁  File upload      — REST POST
# ============================================================

import os
import time
import requests
import streamlit as st
import streamlit.components.v1 as components

# ══════════════════════════════════════════════════════════
# PAGE CONFIG
# ══════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Arabic STT — FastConformer",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ────────────────────────────────────────────
st.markdown("""
<style>
  /* ── Fonts ── */
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Tajawal:wght@400;700&display=swap');
  html, body, [class*="css"] { font-family: 'Tajawal', 'Segoe UI', sans-serif; }

  /* ── Page title gradient ── */
  .main-title {
    font-size: 2.1rem; font-weight: 700; letter-spacing: -0.5px;
    background: linear-gradient(135deg, #58a6ff 30%, #3fb950 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }

  /* ── Tabs ── */
  .stTabs [data-baseweb="tab-list"] {
    gap: 4px; background: #0d1117; border-radius: 10px;
    padding: 4px; border: 1px solid #21262d;
  }
  .stTabs [data-baseweb="tab"] {
    font-size: 15px; font-weight: 600;
    padding: 10px 28px; border-radius: 8px; color: #8b949e;
  }
  .stTabs [aria-selected="true"] { background: #21262d !important; color: #e6edf3 !important; }

  /* ── Stats row ── */
  .stats-row { display: flex; gap: 12px; flex-wrap: wrap; margin: 14px 0; }
  .stat-card {
    flex: 1; min-width: 110px;
    background: #161b22; border: 1px solid #30363d;
    border-radius: 8px; padding: 10px 16px; text-align: center;
  }
  .stat-label { font-size: 10px; color: #8b949e; text-transform: uppercase; letter-spacing: 0.5px; }
  .stat-value { font-size: 22px; font-weight: 700; margin-top: 3px; font-family: 'IBM Plex Mono', monospace; }

  /* ── Color helpers ── */
  .green  { color: #3fb950; } .yellow { color: #d29922; }
  .red    { color: #f85149; } .blue   { color: #58a6ff; }
  .white  { color: #e6edf3; }

  /* ── Segment cards (file tab) ── */
  .seg-card {
    background: #161b22; border: 1px solid #21262d;
    border-radius: 8px; padding: 14px 18px; margin-bottom: 8px;
    direction: rtl; text-align: right;
  }
  .seg-text  { font-size: 17px; color: #e6edf3; line-height: 1.7; margin-bottom: 8px; }
  .seg-meta  {
    font-size: 11px; color: #484f58;
    font-family: 'IBM Plex Mono', monospace;
    display: flex; gap: 16px; flex-wrap: wrap;
    direction: ltr; text-align: left;
  }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════

def _detect_default_url() -> str:
    """
    Resolve the default backend URL in priority order:
      1. BACKEND_URL environment variable  (set by run.py or Streamlit Cloud secrets)
      2. st.secrets["backend"]["url"]      (secrets.toml on Streamlit Cloud)
      3. Fallback to localhost
    """
    env = os.environ.get("BACKEND_URL", "").rstrip("/")
    if env:
        return env
    try:
        return st.secrets["backend"]["url"].rstrip("/")
    except Exception:
        pass
    return "http://localhost:8000"


def _health_check(base_url: str) -> dict:
    """GET /config and return the parsed JSON, or {"ok": False} on failure."""
    try:
        r = requests.get(f"{base_url}/config", timeout=3)
        if r.status_code == 200:
            return {"ok": True, **r.json()}
    except Exception:
        pass
    return {"ok": False}


def _rtf_css(rtf: float) -> str:
    """Return CSS class name based on RTF value."""
    if rtf < 0.5:  return "green"
    if rtf < 1.0:  return "yellow"
    return "red"


def _lat_css(ms: float) -> str:
    """Return CSS class name based on latency in ms."""
    if ms < 500:   return "green"
    if ms < 1500:  return "yellow"
    return "red"


# ══════════════════════════════════════════════════════════
# MIC STREAMING COMPONENT (inline HTML + JS)
# ══════════════════════════════════════════════════════════

# [[WS_URL]] is replaced at runtime with the actual WebSocket URL.
_MIC_HTML = r"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    /* ── Reset & base ── */
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Segoe UI', 'Tajawal', Tahoma, sans-serif;
      background: transparent;
      color: #e6edf3;
      padding: 4px 2px;
    }

    /* ── Control bar ── */
    .controls {
      display: flex; align-items: center;
      gap: 10px; flex-wrap: wrap; margin-bottom: 12px;
    }
    button {
      padding: 9px 20px; border: none; border-radius: 8px;
      font-size: 13px; font-weight: 600; cursor: pointer;
      transition: all 0.15s; letter-spacing: 0.3px;
    }
    #startBtn { background: #238636; color: #fff; }
    #startBtn:not(:disabled):hover { background: #2ea043; transform: translateY(-1px); }
    #stopBtn  { background: #b62324; color: #fff; }
    #stopBtn:not(:disabled):hover  { background: #d1242f; transform: translateY(-1px); }
    #clearBtn { background: #21262d; border: 1px solid #30363d; color: #8b949e; }
    #clearBtn:hover { background: #30363d; color: #e6edf3; }
    button:disabled { opacity: 0.4; cursor: not-allowed; transform: none !important; }

    /* ── Status badge ── */
    .badge {
      padding: 4px 12px; border-radius: 20px;
      font-size: 12px; font-weight: 700; letter-spacing: 0.4px;
    }
    .idle        { background: #21262d; color: #8b949e; border: 1px solid #30363d; }
    .connecting  { background: #7d4e17; color: #ffa657; }
    .recording   { background: #0f2d1f; color: #3fb950; border: 1px solid #238636; }
    .error       { background: #4a1517; color: #f85149; }

    /* ── Waveform canvas ── */
    #wave {
      width: 100%; height: 48px;
      border-radius: 6px; background: #0d1117;
      border: 1px solid #21262d;
      display: block; margin-bottom: 10px;
    }

    /* ── Metric cards ── */
    .metrics { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
    .mc {
      flex: 1; min-width: 88px;
      background: #161b22; border: 1px solid #21262d;
      border-radius: 8px; padding: 7px 12px; text-align: center;
    }
    .ml { font-size: 10px; color: #6e7681; text-transform: uppercase; letter-spacing: 0.5px; }
    .mv {
      font-size: 18px; font-weight: 700; margin-top: 2px;
      font-family: 'Courier New', monospace;
    }
    .g { color: #3fb950; } .y { color: #d29922; }
    .r { color: #f85149; } .b { color: #79c0ff; } .w { color: #e6edf3; }

    /* ── Transcript box ── */
    .t-bar {
      display: flex; justify-content: space-between;
      align-items: center; margin-bottom: 6px;
    }
    .t-lbl { font-size: 11px; color: #6e7681; text-transform: uppercase; letter-spacing: 0.5px; }
    #copyBtn {
      background: #21262d; border: 1px solid #30363d;
      color: #8b949e; padding: 3px 10px;
      font-size: 11px; border-radius: 4px; cursor: pointer;
    }
    #copyBtn:hover { background: #30363d; color: #e6edf3; }

    #tbox {
      background: #0d1117; border: 1px solid #21262d;
      border-radius: 8px; padding: 14px 16px;
      min-height: 160px; max-height: 280px; overflow-y: auto;
      direction: rtl; text-align: right;
      font-size: 18px; line-height: 1.9; color: #e6edf3;
      word-break: break-word;
    }
    #tbox::-webkit-scrollbar { width: 4px; }
    #tbox::-webkit-scrollbar-thumb { background: #30363d; border-radius: 4px; }

    .ph  { color: #484f58; font-size: 14px; }  /* placeholder text */
    .fin { color: #e6edf3; }                    /* final transcript */
    .par { color: #6e7681; }                    /* partial (streaming) */

    /* ── Recording pulse dot ── */
    @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.35} }
    .dot {
      display: inline-block; width: 8px; height: 8px;
      background: #f85149; border-radius: 50%;
      animation: pulse 1s infinite; margin-right: 4px;
    }
  </style>
</head>
<body>

  <!-- Control bar -->
  <div class="controls">
    <button id="startBtn" onclick="startRec()">🎤 بدء التسجيل</button>
    <button id="stopBtn"  onclick="stopRec()" disabled>⏹ إيقاف</button>
    <button id="clearBtn" onclick="clearAll()">🗑️ مسح</button>
    <span   id="badge" class="badge idle">● غير متصل</span>
  </div>

  <div style="margin-top:6px; font-size:12px; color:#6e7681;">
    <span>WS: </span><code id="wsUrlDisplay" style="color:#79c0ff;"></code>
  </div>

  <!-- Waveform visualizer -->
  <canvas id="wave"></canvas>

  <!-- Live metrics -->
  <div class="metrics">
    <div class="mc"><div class="ml">Latency</div><div class="mv b" id="mLat">—</div></div>
    <div class="mc"><div class="ml">RTF</div>    <div class="mv g" id="mRTF">—</div></div>
    <div class="mc"><div class="ml">Avg Lat</div><div class="mv w" id="mAvg">—</div></div>
    <div class="mc"><div class="ml">Min/Max</div><div class="mv w" id="mMM">—</div></div>
    <div class="mc"><div class="ml">Segments</div><div class="mv g" id="mSeg">0</div></div>
  </div>

  <!-- Transcript output -->
  <div class="t-bar">
    <span class="t-lbl">Transcript</span>
    <button id="copyBtn" onclick="copyTxt()">📋 Copy</button>
  </div>
  <div id="tbox"><span class="ph">🎤 Press "بدء التسجيل" to start…</span></div>

<script>
// ── Configuration ───────────────────────────────────────
// `[[WS_URL]]` may contain a full HTTP(s) URL (from Streamlit secrets)
// or be empty. If empty, we must NOT derive a host from the page (Streamlit
// Cloud uses a different host) — instead disable the mic UI and show an
// explicit error so users configure the backend via Secrets.
const WS_URL_RAW  = '[[WS_URL]]';  // injected by Python at render time
let WS_URL = WS_URL_RAW && WS_URL_RAW !== '[[WS_URL]]' ? WS_URL_RAW.trim() : '';

if (!WS_URL) {
  // No configured backend — disable mic controls and show a clear message.
  console.error('[STT] No backend WS URL provided; mic streaming disabled.');
  try { document.getElementById('wsUrlDisplay').textContent = 'No backend configured'; } catch(_) {}
  try {
    const b = document.getElementById('badge');
    b.innerHTML = '❌ No backend';
    b.className = 'badge error';
  } catch(_) {}
  try { document.getElementById('startBtn').disabled = true; } catch(_) {}
} else {
  // Normalize configured URL and ensure the /ws/stream suffix
  if (WS_URL.startsWith('http://')) {
    WS_URL = WS_URL.replace('http://', 'ws://');
  } else if (WS_URL.startsWith('https://')) {
    WS_URL = WS_URL.replace('https://', 'wss://');
  }
  if (!WS_URL.endsWith('/ws/stream')) {
    WS_URL = WS_URL.replace(/\/+$, '') + '/ws/stream';
  }

  // Enforce security: don't attempt an insecure ws:// connection from an https page.
  if (window && window.location && window.location.protocol === 'https:' && WS_URL.startsWith('ws://')) {
    WS_URL = WS_URL.replace('ws://', 'wss://');
  }

  console.log('[STT] Using WS URL:', WS_URL);
  // Show the computed WS URL in the UI for debugging
  try { document.getElementById('wsUrlDisplay').textContent = WS_URL; } catch(_) {}
}
const SAMPLE_RATE = 16000;
const BUFFER_SIZE = 4096;          // ~256 ms per chunk @ 16 kHz

// ── State ────────────────────────────────────────────────
let ws          = null;
let audioCtx    = null;
let processor   = null;
let analyser    = null;
let mediaStream = null;
let recording   = false;
let fullTxt     = '';
let partTxt     = '';
let segCount    = 0;
let latencies   = [];

// ── Canvas setup ─────────────────────────────────────────
const canv = document.getElementById('wave');
const ctx  = canv.getContext('2d');

function resizeCanv() {
  canv.width  = canv.offsetWidth  * (window.devicePixelRatio || 1);
  canv.height = canv.offsetHeight * (window.devicePixelRatio || 1);
  ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);
}
window.addEventListener('resize', resizeCanv);
resizeCanv();

// ── Waveform animation loop ───────────────────────────────
(function drawLoop() {
  requestAnimationFrame(drawLoop);
  const W = canv.offsetWidth, H = canv.offsetHeight;
  ctx.clearRect(0, 0, W, H);

  if (!analyser || !recording) {
    // Flat idle line
    ctx.strokeStyle = '#21262d';
    ctx.lineWidth   = 1;
    ctx.beginPath();
    ctx.moveTo(0, H / 2);
    ctx.lineTo(W, H / 2);
    ctx.stroke();
    return;
  }

  // Live waveform with gradient
  const buf  = new Uint8Array(analyser.frequencyBinCount);
  analyser.getByteTimeDomainData(buf);

  const grad = ctx.createLinearGradient(0, 0, W, 0);
  grad.addColorStop(0,   '#388bfd');
  grad.addColorStop(0.5, '#3fb950');
  grad.addColorStop(1,   '#388bfd');
  ctx.strokeStyle = grad;
  ctx.lineWidth   = 2;
  ctx.beginPath();

  const step = W / buf.length;
  let x = 0;
  for (let i = 0; i < buf.length; i++) {
    const y = (buf[i] / 128) * (H / 2);
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    x += step;
  }
  ctx.stroke();
})();

// ── Status badge helper ───────────────────────────────────
function setStatus(html, cls) {
  const b = document.getElementById('badge');
  b.innerHTML = html;
  b.className = 'badge ' + cls;
}

// ── Metrics update ────────────────────────────────────────
function updateMetrics(latMs, rtf) {
  segCount++;
  latencies.push(latMs);
  const avg = latencies.reduce((a, b) => a + b, 0) / latencies.length;
  const mn  = Math.min(...latencies);
  const mx  = Math.max(...latencies);

  // Latency
  const latEl = document.getElementById('mLat');
  latEl.textContent = latMs.toFixed(0) + ' ms';
  latEl.className   = 'mv ' + (latMs < 500 ? 'g' : latMs < 1500 ? 'y' : 'r');

  // RTF
  const rtfEl = document.getElementById('mRTF');
  rtfEl.textContent = rtf.toFixed(3);
  rtfEl.className   = 'mv ' + (rtf < 0.5 ? 'g' : rtf < 1.0 ? 'y' : 'r');

  document.getElementById('mAvg').textContent = avg.toFixed(0) + ' ms';
  document.getElementById('mMM').textContent  = mn.toFixed(0) + ' / ' + mx.toFixed(0);
  document.getElementById('mSeg').textContent = segCount;
}

// ── Transcript rendering ──────────────────────────────────
function render() {
  const box = document.getElementById('tbox');
  if (!fullTxt && !partTxt) {
    box.innerHTML = '<span class="ph">🎤 Press "بدء التسجيل" to start…</span>';
    return;
  }
  box.innerHTML =
    (fullTxt ? `<span class="fin">${fullTxt}</span>` : '') +
    (partTxt ? `<span class="par"> ${partTxt}</span>` : '');
  box.scrollTop = box.scrollHeight;
}

// ── Start recording ───────────────────────────────────────
async function startRec() {
  if (recording) return;
  setStatus('⟳ Connecting…', 'connecting');

  try {
    // 1. Open WebSocket to backend
    // Helper to attempt a connection and handle security (ws:// from https)
    const attemptConnect = (url) => {
      let connectUrl = url;
      if (window.location.protocol === 'https:' && connectUrl.startsWith('ws://')) {
        console.warn('[STT] Page is HTTPS, upgrading WS connection to WSS');
        connectUrl = connectUrl.replace('ws://', 'wss://');
      }
      
      return new Promise((resolve, reject) => {
        console.log('[STT] Attempting to connect to:', connectUrl);
        const socket = new WebSocket(connectUrl);
        socket.binaryType = 'arraybuffer';

        const timeout = setTimeout(() => {
          socket.close();
          reject(new Error(`Connection timeout to ${connectUrl}`));
        }, 10000);

        socket.onopen = () => {
          clearTimeout(timeout);
          console.log('[STT] Connected to:', connectUrl);
          resolve(socket);
        };

        socket.onerror = (err) => {
          clearTimeout(timeout);
          console.error('[STT] Connection failed for:', connectUrl, err);
          reject(new Error(`WebSocket connection failed for ${connectUrl}`));
        };
      });
    };

    try {
      ws = await attemptConnect(WS_URL);
    } catch (e) {
      console.warn('[STT] Initial connection failed, trying fallback protocol.');
      // Try swapping ws:// for wss:// or vice-versa
      let fallbackUrl = WS_URL.startsWith('ws://') 
        ? WS_URL.replace('ws://', 'wss://')
        : WS_URL.replace('wss://', 'ws://');
      
      try {
        ws = await attemptConnect(fallbackUrl);
        WS_URL = fallbackUrl; // Update global if fallback succeeds
        document.getElementById('wsUrlDisplay').textContent = WS_URL;
      } catch (fallbackError) {
        console.error('[STT] Fallback connection also failed.');
        throw fallbackError; // Propagate the final error
      }
    }

    // 2. Request microphone access
    mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        sampleRate: SAMPLE_RATE,
        channelCount: 1,
        echoCancellation:  true,
        noiseSuppression:  true,
        autoGainControl:   true,
      }
    });

    // 3. Build audio processing graph
    audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: SAMPLE_RATE });
    const src = audioCtx.createMediaStreamSource(mediaStream);

    // Analyser → waveform visualizer
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 2048;
    src.connect(analyser);

    // ScriptProcessor → sends float32 PCM over WebSocket
    processor = audioCtx.createScriptProcessor(BUFFER_SIZE, 1, 1);
    src.connect(processor);
    processor.connect(audioCtx.destination);
    processor.onaudioprocess = (e) => {
      if (!recording || !ws || ws.readyState !== WebSocket.OPEN) return;
      const pcm = e.inputBuffer.getChannelData(0);
      // slice() copies the ArrayBuffer so it's safe to send
      ws.send(pcm.buffer.slice(pcm.byteOffset, pcm.byteOffset + pcm.byteLength));
    };

    // 4. Handle incoming events from backend
    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (msg.type === 'transcript' && msg.text) {
          if (msg.is_final) {
            fullTxt = msg.text;
            partTxt = '';
            updateMetrics(msg.latency_ms, msg.rtf);
            setStatus('<span class="dot"></span> Recording', 'recording');
          } else {
            partTxt = msg.text;  // streaming partial result
          }
          render();
        } else if (msg.type === 'error') {
          setStatus('❌ ' + msg.message, 'error');
        }
        // 'keepalive' messages are silently ignored
      } catch (e) {
        console.error('[STT] Failed to parse WS message:', e, evt.data);
      }
    };

    ws.onerror = (e) => {
      console.error('[STT] WebSocket error:', e);
      setStatus('❌ Connection error', 'error');
    };

    ws.onclose = (ev) => {
      console.warn('[STT] WebSocket closed', ev.code, ev.reason);
      if (recording) stopRec();
      setStatus('● Stopped', 'idle');
    };

    recording = true;
    document.getElementById('startBtn').disabled = true;
    document.getElementById('stopBtn').disabled  = false;
    setStatus('<span class="dot"></span> Recording', 'recording');

    // Clear placeholder on first start
    if (document.getElementById('tbox').querySelector('.ph')) {
      document.getElementById('tbox').innerHTML = '';
    }

  } catch (err) {
    setStatus('❌ ' + err.message, 'error');
    console.error('[STT] startRec error:', err);
    cleanup();
  }
}

// ── Stop recording ────────────────────────────────────────
function stopRec() {
  recording = false;
  cleanup();
  setStatus('● Stopped', 'idle');
  document.getElementById('startBtn').disabled = false;
  document.getElementById('stopBtn').disabled  = true;
}

// ── Release all audio/network resources ──────────────────
function cleanup() {
  try { if (processor)   processor.disconnect();  } catch(_) {}
  try { if (analyser)    analyser.disconnect();   } catch(_) {}
  try { if (audioCtx)    audioCtx.close();        } catch(_) {}
  try { if (mediaStream) mediaStream.getTracks().forEach(t => t.stop()); } catch(_) {}
  try { if (ws && ws.readyState === WebSocket.OPEN) ws.close(); } catch(_) {}
  processor = analyser = audioCtx = mediaStream = ws = null;
}

// ── Clear transcript & metrics ────────────────────────────
function clearAll() {
  fullTxt = ''; partTxt = ''; segCount = 0; latencies = [];
  ['mLat','mRTF','mAvg','mMM'].forEach(id => document.getElementById(id).textContent = '—');
  document.getElementById('mSeg').textContent = '0';
  document.getElementById('mLat').className   = 'mv b';
  document.getElementById('mRTF').className   = 'mv g';
  render();
}

// ── Copy transcript to clipboard ──────────────────────────
function copyTxt() {
  const txt = (fullTxt + ' ' + partTxt).trim();
  if (!txt) return;
  navigator.clipboard.writeText(txt)
    .then(() => {
      const btn = document.getElementById('copyBtn');
      btn.textContent = '✅ Copied';
      setTimeout(() => btn.textContent = '📋 Copy', 2000);
    })
    .catch(() => {
      // Fallback for older / restricted browsers
      const ta = document.createElement('textarea');
      ta.value = txt;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
    });
}
</script>
</body>
</html>
"""


def _mic_html(ws_url: str) -> str:
    """Inject the live WebSocket URL into the HTML template."""
    return _MIC_HTML.replace("[[WS_URL]]", ws_url)


# ══════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("## ⚙️ Settings")

    backend_url = st.text_input(
        "🌐 Backend URL",
        value=_detect_default_url(),
        key="backend_url",
        help="FastAPI backend URL — local or ngrok public URL",
    ).rstrip("/")

    # Derive WebSocket URL from HTTP URL (robustly) and escape for JS injection
    base = backend_url.rstrip('/')
    ws_url = ''
    if base:
        if base.startswith('https://'):
            ws_url = 'wss://' + base[len('https://'):]
        elif base.startswith('http://'):
            ws_url = 'ws://'  + base[len('http://'):]
        else:
            # If no scheme, assume it's a bare hostname and let JS handle protocol
            ws_url = base

        if not ws_url.endswith('/ws/stream'):
            ws_url = ws_url.rstrip('/') + '/ws/stream'

    # Escape single quotes for safe JS injection
    ws_url_js = ws_url.replace("'", "\\'")
    st.caption(f"🔌 `{ws_url}`")

    st.divider()

    # ── Live connection status ────────────────────────────
    col_lbl, col_btn = st.columns([3, 1])
    with col_lbl:
        st.markdown("### 📡 Connection")
    with col_btn:
        if st.button("🔄", help="Refresh status"):
            st.rerun()

    info = _health_check(backend_url)
    if info["ok"]:
        st.success("✅ Connected")
        st.metric("Model",        info.get("model",  "—").split("/")[-1])
        st.metric("Device",       info.get("device", "—").upper())
        st.metric("Decoder",      info.get("decoder", "—"))
        st.metric("CUDA Streams", info.get("streams", "—"))
        st.metric("Batch Size",   info.get("batch_size", "—"))
        st.metric("VAD Threshold",info.get("vad_threshold", "—"))
    else:
        st.error("❌ Cannot reach backend")
        st.caption(
            "Start the backend first:\n"
            "```\npython run.py\n```\n"
            "Then paste the ngrok URL above."
        )

    st.divider()

    # ── Quick-start guide ────────────────────────────────
    with st.expander("📖 Quick Start"):
        st.markdown("""
        **Local:**
        ```bash
        pip install -r requirements_api.txt
        python run.py
        ```

        **Streamlit Cloud:**
        1. Deploy this `app.py` + `requirements.txt`
        2. Add to `secrets.toml`:
        ```toml
        [backend]
        url = "https://xxxx.ngrok-free.app"
        ```
        3. Start backend with `python run.py`

        **Metrics:**
        | Metric | Meaning |
        |--------|---------|
        | Latency | ms from speech end → text |
        | RTF | <1.0 = faster than real-time |
        | Avg | session average latency |
        """)


# ══════════════════════════════════════════════════════════
# MAIN CONTENT
# ══════════════════════════════════════════════════════════

st.markdown(
    '<h1 class="main-title">🎙️ Arabic STT — FastConformer Hybrid</h1>',
    unsafe_allow_html=True,
)
st.caption("nvidia/stt_ar_fastconformer_hybrid_large_pcd_v1.0 · NeMo · Real-Time")
st.divider()

tab_mic, tab_file = st.tabs(["🎤 Live Mic", "📁 File Upload"])


# ══════════════════════════════════════════════════════════
# TAB 1 — LIVE MICROPHONE (WebSocket streaming)
# ══════════════════════════════════════════════════════════

with tab_mic:
    if not info["ok"]:
        st.warning(
            "⚠️ Backend not connected — paste the ngrok URL in the sidebar first.",
            icon="⚠️",
        )
    else:
        st.info(
            "**How it works:** Press **بدء التسجيل** → speak Arabic → "
            "text appears instantly with per-sentence Latency and RTF.",
            icon="ℹ️",
        )

    # Render the self-contained mic HTML component (inject escaped URL)
    st.components.v1.html(_mic_html(ws_url_js), height=530, scrolling=False)

    # Metrics legend
    with st.expander("📊 Metrics explained"):
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown("**Latency (ms)**\nTime from end of sentence to text appearing")
        c2.markdown("**RTF**\nReal-Time Factor — below 1.0 = faster than real-time")
        c3.markdown("**Avg Latency**\nRunning average across the whole session")
        c4.markdown("**Min / Max**\nFastest and slowest segment in the session")


# ══════════════════════════════════════════════════════════
# TAB 2 — FILE UPLOAD (REST POST)
# ══════════════════════════════════════════════════════════

with tab_file:
    if not info["ok"]:
        st.warning(
            "⚠️ Backend not connected — paste the ngrok URL in the sidebar first.",
            icon="⚠️",
        )

    st.markdown("### 📁 Upload an audio file for transcription")

    col_up, col_hint = st.columns([3, 1])
    with col_up:
        uploaded = st.file_uploader(
            "Drop a file here or click to browse",
            type=["wav", "mp3", "flac", "ogg", "m4a"],
            label_visibility="collapsed",
        )
    with col_hint:
        st.markdown("""
        **Supported formats:**
        WAV · MP3 · FLAC · OGG · M4A

        Any sample rate (auto-resampled to 16 kHz)
        """)

    if uploaded:
        # Preview the uploaded audio
        st.audio(uploaded, format=uploaded.type)
        size_mb = len(uploaded.getvalue()) / (1024 * 1024)
        st.caption(f"📄 `{uploaded.name}` — {size_mb:.2f} MB")

        if st.button(
            "▶️ Transcribe",
            type="primary",
            use_container_width=True,
            disabled=not info["ok"],
        ):
            prog = st.progress(0, text="⏳ Uploading file…")
            t0   = time.time()

            try:
                prog.progress(20, text="⏳ Transcribing…")

                resp = requests.post(
                    f"{backend_url}/transcribe/file",
                    files={
                        "file": (
                            uploaded.name,
                            uploaded.getvalue(),
                            uploaded.type or "audio/wav",
                        )
                    },
                    timeout=600,  # allow up to 10 min for large files
                )

                prog.progress(100, text="✅ Done!")
                elapsed_s = time.time() - t0

                if resp.status_code == 200:
                    data  = resp.json()
                    stats = data.get("stats", {})

                    # ── Full transcript ───────────────────
                    st.markdown("### 📝 Full Transcript")
                    transcript = data.get("transcript", "")
                    
                    # Update session state to force the text_area to show the new value
                    st.session_state["file_out"] = transcript
                    
                    st.text_area(
                        "Full Transcript",
                        height=140,
                        label_visibility="collapsed",
                        key="file_out",
                    )
                    if transcript:
                        st.download_button(
                            "💾 Download transcript (.txt)",
                            data=transcript,
                            file_name=uploaded.name.rsplit(".", 1)[0] + "_transcript.txt",
                            mime="text/plain",
                        )

                    st.divider()

                    # ── Summary stats ─────────────────────
                    st.markdown("### 📊 Performance")
                    rtf_avg = stats.get("avg_rtf", 0)
                    lat_avg = stats.get("avg_segment_latency_ms", 0)

                    st.markdown(f"""
                    <div class="stats-row">
                      <div class="stat-card">
                        <div class="stat-label">Total time</div>
                        <div class="stat-value blue">{stats.get("total_latency_ms",0):.0f} ms</div>
                      </div>
                      <div class="stat-card">
                        <div class="stat-label">Avg Latency</div>
                        <div class="stat-value {_lat_css(lat_avg)}">{lat_avg:.0f} ms</div>
                      </div>
                      <div class="stat-card">
                        <div class="stat-label">Avg RTF</div>
                        <div class="stat-value {_rtf_css(rtf_avg)}">{rtf_avg:.4f}</div>
                      </div>
                      <div class="stat-card">
                        <div class="stat-label">Segments</div>
                        <div class="stat-value white">{stats.get("segment_count",0)}</div>
                      </div>
                      <div class="stat-card">
                        <div class="stat-label">File size</div>
                        <div class="stat-value white">{stats.get("file_size_mb",0):.2f} MB</div>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)

                    # ── Per-segment breakdown ─────────────
                    events = data.get("events", [])
                    if events:
                        st.divider()
                        st.markdown("### 📋 Segment breakdown")
                        for i, ev in enumerate(events, 1):
                            if not ev.get("text"):
                                continue
                            lat = ev["latency_ms"]
                            rtf = ev["rtf"]
                            dur = ev["audio_duration"]
                            st.markdown(f"""
                            <div class="seg-card">
                              <div class="seg-text">{ev["text"]}</div>
                              <div class="seg-meta">
                                <span>Seg {i}</span>
                                <span>Latency: <span class="{_lat_css(lat)}">{lat:.0f} ms</span></span>
                                <span>RTF: <span class="{_rtf_css(rtf)}">{rtf:.4f}</span></span>
                                <span>Duration: {dur:.1f} s</span>
                              </div>
                            </div>
                            """, unsafe_allow_html=True)
                else:
                    prog.empty()
                    st.error(f"❌ Backend error ({resp.status_code}): {resp.text}")

            except requests.exceptions.ConnectionError:
                prog.empty()
                st.error("❌ Cannot reach backend. Is it running?")
            except requests.exceptions.Timeout:
                prog.empty()
                st.error("❌ Request timed out. File may be too large.")
            except Exception as exc:
                prog.empty()
                st.error(f"❌ Unexpected error: {exc}")

<userPrompt>
Provide the fully rewritten file, incorporating the suggested code change. You must produce the complete file.
</userPrompt>
