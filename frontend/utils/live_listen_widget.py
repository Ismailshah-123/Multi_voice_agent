"""
utils/live_listen_widget.py

WHAT THIS FILE DOES:
Renders a "Listen Live" audio player that connects directly to Vapi's
Call Listen websocket (a raw PCM audio stream) and plays it through the
browser's Web Audio API — this is what lets you actually HEAR an
ongoing call from the dashboard, not just read the transcript.

HONEST NOTE ON AUDIO FORMAT: this uses Vapi's commonly-documented
default (16kHz, 16-bit PCM, mono). Real-world testing may require
adjusting the sample rate below if audio sounds pitched wrong or
crackles — this is a known rough edge of raw audio websocket streaming
in general, not specific to this implementation. If it sounds off,
try changing SAMPLE_RATE to 8000, 44100, or 48000 and reload.

LEGAL NOTE: monitoring live calls has call-recording consent
implications that vary by jurisdiction. Make sure you're compliant
with local law before using this on calls involving real customers.
"""

import streamlit.components.v1 as components


def render_listen_live_widget(listen_url: str, sample_rate: int = 16000, height: int = 90):
    if not listen_url:
        return

    widget_html = f"""
    <style>
        .listen-widget {{ font-family: 'Manrope', sans-serif; }}
        .listen-btn {{
            background: linear-gradient(90deg, #1D4ED8, #1E40AF);
            color: white; border: none; border-radius: 10px;
            padding: 10px 20px; font-weight: 600; cursor: pointer;
            transition: transform 0.2s ease, filter 0.2s ease;
        }}
        .listen-btn:hover {{ transform: translateY(-2px); filter: brightness(1.1); }}
        .listen-status {{ margin-top: 8px; font-size: 12px; color: #5A6B85; }}
    </style>
    <div class="listen-widget">
        <button class="listen-btn" id="listen-btn">🔊 Listen Live</button>
        <div class="listen-status" id="listen-status">Not connected</div>
    </div>
    <script>
        const listenUrl = "{listen_url}";
        const sampleRate = {sample_rate};
        let ws = null;
        let audioCtx = null;
        let isListening = false;

        const btn = document.getElementById('listen-btn');
        const status = document.getElementById('listen-status');

        btn.addEventListener('click', () => {{
            if (!isListening) {{
                startListening();
            }} else {{
                stopListening();
            }}
        }});

        function startListening() {{
            audioCtx = new (window.AudioContext || window.webkitAudioContext)({{ sampleRate: sampleRate }});
            ws = new WebSocket(listenUrl);
            ws.binaryType = 'arraybuffer';

            ws.onopen = () => {{
                isListening = true;
                btn.innerText = '⏹ Stop Listening';
                status.innerText = 'Connected — streaming live audio...';
            }};

            ws.onmessage = (event) => {{
                if (!(event.data instanceof ArrayBuffer)) return;
                const pcm16 = new Int16Array(event.data);
                const float32 = new Float32Array(pcm16.length);
                for (let i = 0; i < pcm16.length; i++) {{
                    float32[i] = pcm16[i] / 32768;
                }}
                const buffer = audioCtx.createBuffer(1, float32.length, sampleRate);
                buffer.copyToChannel(float32, 0);
                const source = audioCtx.createBufferSource();
                source.buffer = buffer;
                source.connect(audioCtx.destination);
                source.start();
            }};

            ws.onerror = () => {{ status.innerText = 'Connection error — the call may have ended.'; }};
            ws.onclose = () => {{
                isListening = false;
                btn.innerText = '🔊 Listen Live';
                status.innerText = 'Disconnected';
            }};
        }}

        function stopListening() {{
            if (ws) ws.close();
            if (audioCtx) audioCtx.close();
            isListening = false;
            btn.innerText = '🔊 Listen Live';
            status.innerText = 'Stopped';
        }}
    </script>
    """
    components.html(widget_html, height=height)
