# frontend/app.py
# =============================================================
# Streamlit Frontend (v2 — Browser Mic Edition)
# =============================================================

import os
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Streaming STT",
    page_icon="🎙️",
    layout="wide",
)

# ── Sidebar ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ الإعدادات")

    default_ws = os.environ.get("WS_URL", "ws://localhost:8000/ws/stream")
    ws_url = st.text_input(
        "WebSocket URL",
        value=default_ws,
        help="wss://xxxx.ngrok.io/ws/stream",
    )

    language = st.selectbox("اللغة", ["ar", "en", "fr", "de", "auto"], index=0)

    chunk_ms = st.slider(
        "حجم الـ Chunk (ms)",
        min_value=100, max_value=1000, value=500, step=100,
        help="أصغر = latency أقل | أكبر = دقة أعلى",
    )

    st.markdown("---")
    st.markdown("### 💡 طريقة الاستخدام")
    st.markdown("""
1. شغّل الـ API server
2. الصق الـ WebSocket URL
3. اضغط **ابدأ الاستماع**
4. اسمح للمتصفح بالمايك
5. اتكلم!
    """)
    st.markdown("---")
    st.markdown("### 🚀 تشغيل الـ API")
    st.code("python api/ngrok_tunnel.py --token TOKEN", language="bash")


# ── Title ────────────────────────────────────────────────────
st.markdown("# 🎙️ Streaming Speech-to-Text")
st.markdown(
    "الصوت بيتاخد من **متصفحك مباشرة** عبر JS → AudioWorklet → "
    "WebSocket → Whisper — بدون ما يعدي على Streamlit server"
)
st.markdown("---")

# ── Build the HTML+JS component ──────────────────────────────
# escape braces for f-string: {{ }} → { }
html = f"""
<link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;700&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<h2 style="position:absolute;opacity:0;pointer-events:none;">مكون تحويل الكلام إلى نص في الوقت الفعلي</h2>

<style>
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:transparent;font-family:'Tajawal','Segoe UI',sans-serif;}}
.wrap{{max-width:860px;padding:4px 0 20px;}}

.row{{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:16px;}}

.btn{{padding:10px 26px;border-radius:8px;border:1.5px solid;font-size:14px;font-weight:700;cursor:pointer;transition:all 0.15s;}}
.btn-go{{background:#0f2744;border-color:#3b82f6;color:#93c5fd;}}
.btn-go:hover{{background:#1d4ed8;color:#fff;}}
.btn-go:disabled{{opacity:0.35;cursor:not-allowed;}}
.btn-stop{{background:#2a0f0f;border-color:#ef4444;color:#fca5a5;}}
.btn-stop:hover{{background:#dc2626;color:#fff;}}
.btn-stop:disabled{{opacity:0.35;cursor:not-allowed;}}
.btn-clr{{background:transparent;border-color:#334155;color:#64748b;padding:10px 16px;font-size:13px;}}
.btn-clr:hover{{background:#1e293b;color:#94a3b8;}}

.sbar{{display:flex;align-items:center;gap:9px;padding:9px 14px;border-radius:7px;background:#0a0f1a;border:1px solid #1e293b;font-family:'JetBrains Mono',monospace;font-size:12px;color:#475569;margin-bottom:14px;}}
.dot{{width:9px;height:9px;border-radius:50%;flex-shrink:0;}}
.idle{{background:#334155;}}
.live{{background:#22c55e;animation:blink 1.3s infinite;}}
.err{{background:#ef4444;}}
.conn{{background:#eab308;animation:blink 0.6s infinite;}}
@keyframes blink{{0%,100%{{opacity:1;}}50%{{opacity:0.25;}}}}

.vu{{height:5px;background:#0f172a;border-radius:3px;overflow:hidden;margin-bottom:14px;}}
.vuf{{height:100%;width:0%;background:linear-gradient(90deg,#22c55e 60%,#eab308 82%,#ef4444 100%);border-radius:3px;transition:width 0.07s;}}

.tbox{{background:#080e1a;border:1px solid #1e293b;border-radius:11px;padding:22px;min-height:130px;margin-bottom:16px;direction:rtl;text-align:right;font-family:'Tajawal',sans-serif;font-size:19px;line-height:1.9;word-break:break-word;}}
.tf{{color:#e2e8f0;}}
.tp{{color:#38bdf8;font-style:italic;opacity:0.85;}}
.ph{{color:#1e293b;font-size:15px;}}

.metrics{{display:grid;grid-template-columns:repeat(5,1fr);gap:9px;margin-bottom:14px;}}
.mc{{background:#080e1a;border:1px solid #1e293b;border-radius:7px;padding:11px;text-align:center;}}
.mv{{font-family:'JetBrains Mono',monospace;font-size:19px;font-weight:700;color:#38bdf8;}}
.ml{{font-size:10px;color:#334155;text-transform:uppercase;letter-spacing:.8px;margin-top:2px;}}

.expbtn{{background:transparent;border:1px solid #1e293b;color:#334155;font-size:11px;padding:5px 11px;border-radius:5px;cursor:pointer;margin-bottom:6px;font-family:'JetBrains Mono',monospace;}}
.expbtn:hover{{color:#64748b;}}
.log{{font-family:'JetBrains Mono',monospace;font-size:11px;background:#04070d;border:1px solid #1e293b;border-radius:7px;padding:9px 11px;max-height:120px;overflow-y:auto;display:none;}}
.log.open{{display:block;}}
.lf{{color:#22c55e;}}.lp{{color:#38bdf8;}}.li{{color:#ca8a04;}}.le{{color:#ef4444;}}

.exrow{{display:flex;gap:10px;align-items:center;margin-top:12px;}}
.btnex{{background:#0f1e38;border:1px solid #3b82f6;color:#93c5fd;padding:7px 16px;border-radius:6px;font-size:12px;cursor:pointer;}}
.btnex:hover{{background:#1d4ed8;color:#fff;}}

@media(max-width:540px){{.metrics{{grid-template-columns:repeat(3,1fr);}}}}
</style>

<div class="wrap">
  <div class="row">
    <button class="btn btn-go"   id="bStart" onclick="go()">▶ ابدأ الاستماع</button>
    <button class="btn btn-stop" id="bStop"  onclick="halt()" disabled>⏹ إيقاف</button>
    <button class="btn btn-clr"  onclick="clr()">🗑 مسح</button>
  </div>

  <div class="sbar"><div class="dot idle" id="dot"></div><span id="stxt">جاهز — اضغط ابدأ</span></div>
  <div class="vu"><div class="vuf" id="vu"></div></div>

  <div class="tbox" id="tbox"><span class="ph" id="ph">ستظهر هنا نتائج التحويل...</span></div>

  <div class="metrics">
    <div class="mc"><div class="mv" id="mRTT">—</div><div class="ml">Net RTT</div></div>
    <div class="mc"><div class="mv" id="mRTF">—</div><div class="ml">RTF</div></div>
    <div class="mc"><div class="mv" id="mLat">—</div><div class="ml">Proc Lat</div></div>
    <div class="mc"><div class="mv" id="mSeg">0</div><div class="ml">Segments</div></div>
    <div class="mc"><div class="mv" id="mCnf">—</div><div class="ml">VAD Conf</div></div>
  </div>

  <div class="exrow">
    <button class="btnex" onclick="dl()">💾 تحميل النص</button>
    <span id="cc" style="font-size:11px;color:#1e293b;">0 حرف</span>
  </div>

  <div style="margin-top:14px;">
    <button class="expbtn" onclick="document.getElementById('log').classList.toggle('open')">📋 سجل الأحداث</button>
    <div class="log" id="log"></div>
  </div>
</div>

<script>
const WS_URL   = {repr(ws_url)};
const LANG     = {repr(language)};
const CHUNK_MS = {chunk_ms};
const SR       = 16000;

let ws=null, stream=null, ctx=null, wlet=null, analyser=null, vuTick=null;
let fin='', part='', segs=0;
let lastPing=0, pingInt=null;

const workletSrc = `
registerProcessor('pcm-proc', class extends AudioWorkletProcessor {{
  constructor(){{ super(); this.buf=[]; this.tgt=Math.round(sampleRate*${{CHUNK_MS}}/1000); }}
  process(ins){{
    const ch=ins[0][0]; if(!ch) return true;
    for(let i=0;i<ch.length;i++) this.buf.push(ch[i]);
    while(this.buf.length>=this.tgt){{
      const c=new Float32Array(this.buf.splice(0,this.tgt));
      this.port.postMessage(c,[c.buffer]);
    }}
    return true;
  }}
}});
`.replace(/\$\{{CHUNK_MS\}}/g, CHUNK_MS);

function st2(state,txt){{
  const d=document.getElementById('dot'), s=document.getElementById('stxt');
  d.className='dot '+state; s.textContent=txt;
}}

function addLog(cls,txt){{
  const b=document.getElementById('log');
  const t=new Date().toLocaleTimeString('ar',{{hour:'2-digit',minute:'2-digit',second:'2-digit'}});
  const d=document.createElement('div');
  d.className=cls; d.textContent=`[${{t}}] ${{txt.substring(0,100)}}`;
  b.prepend(d);
  if(b.children.length>60) b.removeChild(b.lastChild);
}}

function render() {{
  const box = document.getElementById('tbox');
  if (!fin && !part) {{
    box.innerHTML = '<span class="ph" id="ph">ستظهر هنا نتائج التحويل...</span>';
    document.getElementById('cc').textContent = '0 حرف';
    return;
  }}
  let h = '';
  if (fin) h += `<span class="tf">${{fin}} </span>`;
  if (part) h += `<span class="tp">${{part}}</span>`;
  box.innerHTML = h;
  box.scrollTop = box.scrollHeight;
  document.getElementById('cc').textContent = (fin + part).length + ' حرف';
}}

function startVU(){{
  if(!analyser) return;
  const d=new Uint8Array(analyser.fftSize);
  vuTick=setInterval(()=>{{
    analyser.getByteTimeDomainData(d);
    let s=0; for(let i=0;i<d.length;i++){{ const v=(d[i]-128)/128; s+=v*v; }}
    const p=Math.min(Math.sqrt(s/d.length)*420,100).toFixed(1);
    document.getElementById('vu').style.width=p+'%';
  }},55);
}}

async function go(){{
  if(ws) return;
  document.getElementById('bStart').disabled=true;
  st2('conn','جاري الاتصال...');

  try{{
    ws=new WebSocket(WS_URL);
    ws.binaryType='arraybuffer';

    ws.onopen=()=>{{
      st2('live','متصل — يستمع...');
      addLog('li','متصل: '+WS_URL);
      document.getElementById('bStop').disabled=false;
      
      pingInt = setInterval(()=>{{
        if(ws && ws.readyState===1){{
          lastPing = performance.now();
          ws.send(JSON.stringify({{type: 'ping'}}));
        }}
      }}, 2000);
    }};

    ws.onmessage=(e)=>{{
      try{{
        const d=JSON.parse(e.data);
        if(d.type==='pong'){{
          const rtt = performance.now() - lastPing;
          document.getElementById('mRTT').textContent = Math.round(rtt) + 'ms';
        }}
        else if(d.type==='partial' && d.text){{
          part=d.text;
          document.getElementById('mRTF').textContent=d.rtf!=null?d.rtf.toFixed(2):'—';
          document.getElementById('mLat').textContent=d.latency_ms!=null?d.latency_ms.toFixed(0)+'ms':'—';
          document.getElementById('mCnf').textContent=d.confidence!=null?d.confidence.toFixed(2):'—';
          render(); addLog('lp',d.text);
        }}
        else if(d.type==='final' && d.text){{
          fin+=(fin?' ':'')+d.text; part=''; segs++;
          document.getElementById('mSeg').textContent=segs;
          document.getElementById('mRTF').textContent=d.rtf!=null?d.rtf.toFixed(2):'—';
          document.getElementById('mLat').textContent=d.latency_ms!=null?d.latency_ms.toFixed(0)+'ms':'—';
          render(); addLog('lf',d.text);
        }}
        else if(d.type==='info')  addLog('li',d.message||'');
        else if(d.type==='error') {{ addLog('le',d.message||''); st2('err','خطأ: '+(d.message||'')); }}
      }}catch(ex){{ addLog('le','parse: '+ex); }}
    }};

    ws.onerror=()=>{{
      st2('err','خطأ اتصال — تحقق من الـ URL والـ server');
      addLog('le','WebSocket error'); halt();
    }};

    ws.onclose=()=>{{
      if(!document.getElementById('bStop').disabled){{
        st2('idle','انقطع الاتصال'); addLog('li','مغلق'); halt();
      }}
    }};

    // Mic
    stream=await navigator.mediaDevices.getUserMedia({{
      audio:{{sampleRate:SR,channelCount:1,echoCancellation:true,noiseSuppression:true}}
    }});

    ctx=new AudioContext({{sampleRate:SR}});
    const blob=new Blob([workletSrc],{{type:'application/javascript'}});
    const burl=URL.createObjectURL(blob);
    await ctx.audioWorklet.addModule(burl);
    URL.revokeObjectURL(burl);

    const src=ctx.createMediaStreamSource(stream);
    analyser=ctx.createAnalyser(); analyser.fftSize=256;
    wlet=new AudioWorkletNode(ctx,'pcm-proc');

    wlet.port.onmessage=(e)=>{{
      if(ws && ws.readyState===1) ws.send(e.data.buffer);
    }};

    src.connect(analyser); analyser.connect(wlet);
    startVU();
    addLog('li',`Mic OK — SR=${{SR}}, chunk=${{CHUNK_MS}}ms`);

  }}catch(ex){{
    st2('err',ex.message); addLog('le',ex.message);
    document.getElementById('bStart').disabled=false;
    document.getElementById('bStop').disabled=true;
    if(ws){{ ws.close(); ws=null; }}
  }}
}}

function halt(){{
  clearInterval(vuTick); document.getElementById('vu').style.width='0%';
  if(pingInt) clearInterval(pingInt);
  if(wlet){{ wlet.disconnect(); wlet=null; }}
  if(analyser){{ analyser.disconnect(); analyser=null; }}
  if(ctx){{ ctx.close(); ctx=null; }}
  if(stream){{ stream.getTracks().forEach(t=>t.stop()); stream=null; }}
  if(ws){{
    try{{ if(ws.readyState===1) ws.send(JSON.stringify({{type:'stop'}})); ws.close(); }}catch(e){{}}
    ws=null;
  }}
  st2('idle','متوقف'); addLog('li','تم الإيقاف');
  document.getElementById('bStart').disabled=false;
  document.getElementById('bStop').disabled=true;
}}

function clr(){{
  fin=''; part=''; segs=0;
  ['mRTT','mRTF','mLat','mCnf'].forEach(id=>document.getElementById(id).textContent='—');
  document.getElementById('mSeg').textContent='0';
  document.getElementById('log').innerHTML='';
  document.getElementById('cc').textContent='0 حرف';
  render();
}}

function dl(){{
  const t=(fin+' '+part).trim(); if(!t) return;
  const a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([t],{{type:'text/plain;charset=utf-8'}}));
  a.download='transcript_'+new Date().toISOString().slice(0,19).replace(/:/g,'-')+'.txt';
  a.click();
}}

render();
</script>
"""

components.html(html, height=620, scrolling=False)

# ── File upload via REST ─────────────────────────────────────
st.markdown("---")
st.markdown("### 📁 تحويل ملف صوتي")

api_url = (
    ws_url
    .replace("wss://", "https://")
    .replace("ws://", "http://")
    .replace("/ws/stream", "")
)

uploaded = st.file_uploader("WAV / MP3 / FLAC / OGG", type=["wav", "mp3", "flac", "ogg", "m4a"])
lang_f = st.selectbox("اللغة", ["ar", "en", "fr", "auto"], key="lf")

if st.button("🎯 حوّل الملف", use_container_width=True):
    if uploaded:
        import requests
        import json
        
        st.info("🧠 جاري التحويل وعرض النتائج مباشرة...")
        
        # Placeholders for streaming output
        text_box = st.empty()
        metrics_box = st.empty()
        
        try:
            r = requests.post(
                f"{api_url}/transcribe",
                files={"file": (uploaded.name, uploaded.getvalue(), uploaded.type)},
                params={"language": lang_f},
                timeout=300,
                stream=True
            )
            r.raise_for_status()
            
            full_text = ""
            final_res = {}
            
            for line in r.iter_lines(decode_unicode=True):
                if line and line.strip():
                    try:
                        data = json.loads(line)
                        
                        if data.get("type") == "partial":
                            partial_text = data.get("text", "")
                            display_html = f"""<div dir="rtl" style="background:#080e1a;padding:16px;border-radius:10px;font-size:17px;line-height:1.8;color:#e2e8f0;border:1px solid #1e293b">{full_text} <span style="color:#38bdf8;font-style:italic;">{partial_text}</span></div>"""
                            text_box.markdown(display_html, unsafe_allow_html=True)
                            
                            m_col1, m_col2 = metrics_box.columns(2)
                            m_col1.metric("Latency (ms)", f"{data.get('latency_ms', 0):.0f}ms")
                            m_col2.metric("RTF", f"{data.get('rtf', 0):.3f}")
                            
                        elif data.get("type") == "final":
                            new_text = data.get("text", "")
                            if new_text:
                                full_text += (" " if full_text else "") + new_text
                            
                            display_html = f"""<div dir="rtl" style="background:#080e1a;padding:16px;border-radius:10px;font-size:17px;line-height:1.8;color:#e2e8f0;border:1px solid #1e293b">{full_text}</div>"""
                            text_box.markdown(display_html, unsafe_allow_html=True)
                            
                            m_col1, m_col2 = metrics_box.columns(2)
                            m_col1.metric("Latency (ms)", f"{data.get('latency_ms', 0):.0f}ms")
                            m_col2.metric("RTF", f"{data.get('rtf', 0):.3f}")
                            
                        elif data.get("type") == "summary":
                            final_res = data
                            
                            m_col1, m_col2 = metrics_box.columns(2)
                            m_col1.metric("Latency (ms)", f"{data.get('latency_ms', 0):.0f}ms")
                            m_col2.metric("RTF", f"{data.get('rtf', 0):.3f}")
                            
                    except json.JSONDecodeError:
                        continue # Ignore chunks that fail to parse
                        
            if final_res:
                st.success("✅ تم!")
                st.download_button("💾 تحميل النص", final_res.get("text", full_text), file_name="transcript.txt")
                
        except Exception as e:
            st.error(f"خطأ أثناء التحويل: {e}")
    else:
        st.warning("ارفع ملف أولاً")
