"""Simulated Alexa+ experience — the demo surface for Crew Memory.

A single-page web app that plays the role of the Alexa+ host: the user
types (or taps) a request, the page shows an Alexa+-style conversation,
and — this is the point — every response is produced by a REAL MCP call
(Streamable HTTP, official SDK client) to the Crew Memory MCP server.
The panel under the conversation shows the actual tool call, the protocol
version negotiated, and the evidence path behind each answer, so what is
demoed is the protocol working, not a mock of it.

The intent routing below is deliberately simple keyword matching. It is a
*simulation* of a voice host's NLU, and it is labeled as such: in
production the host's own models do intent resolution and call the same
tools. Nothing in this file stores memory itself — all state lives behind
the MCP server.

Run (server first):  MCP_URL=http://127.0.0.1:8000/mcp python alexa_sim.py
"""
from __future__ import annotations

import os
import re

from flask import Flask, jsonify, render_template_string, request

import mcp_client

app = Flask(__name__)


def mcp_url() -> str:
    return os.environ.get("MCP_URL", "http://127.0.0.1:8000/mcp")


# -- simulated intent routing (keyword rules, honestly labeled) -----------
def route(message: str) -> tuple[str, dict]:
    msg = message.strip()
    low = msg.lower()
    if low.startswith("remember"):
        text = re.sub(r"^remember( that)?\s+", "", msg, flags=re.I)
        about = [w for w in re.findall(r"\b[A-Z][a-z]+\b", text)][0:3]
        return "remember", {"text": text, "kind": "fact",
                            "about": about, "agent": "researcher"}
    if "hand off" in low or "handoff" in low or "tell the executor" in low:
        return "handoff", {"from_agent": "planner", "to_agent": "executor",
                           "summary": msg}
    if "pending" in low or "open handoffs" in low:
        return "open_handoffs", {"agent": "executor"}
    if "what do you remember" in low or low.startswith("recall"):
        q = low.split("about", 1)[1].strip(" ?") if "about" in low else msg
        return "recall", {"query": q}
    return "crew_ask", {"question": msg}


def compose_reply(tool: str, result: dict) -> str:
    if tool == "remember":
        return ("Got it — stored in crew memory "
                f"({result.get('layer', 'semantic')} layer). It will persist "
                "across sessions.")
    if tool == "recall":
        if result.get("count"):
            return " ".join(r["text"] for r in result["results"])
        return ("I don't have anything stored about that yet. "
                "Tell me to remember it and it will be there next time.")
    if tool == "crew_ask":
        return result.get("answer", "")
    if tool == "handoff":
        return (f"Handed to the {result.get('to', 'executor')} with the "
                "memory context attached "
                f"({result.get('neighborhood_nodes', 0)} related memory "
                "nodes). They can pick it up from any session.")
    if tool == "open_handoffs":
        if result.get("count"):
            items = "; ".join(h["summary"] for h in result["handoffs"])
            return f"{result['count']} open: {items}"
        return "Nothing pending right now."
    return str(result)


@app.post("/api/chat")
def chat():
    data = request.get_json(force=True)
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "empty message"}), 400
    tool, args = route(message)
    try:
        payload = mcp_client.call_tool(mcp_url(), tool, args)
    except Exception as e:  # server unreachable — say so, don't fake it
        return jsonify({
            "reply": "I can't reach the Crew Memory server right now. "
                     "Is mcp_server.py running?",
            "tool": tool, "args": args, "error": f"{type(e).__name__}: {e}",
        }), 502
    result = payload.get("result", {})
    evidence = result.get("evidence", []) if isinstance(result, dict) else []
    return jsonify({
        "reply": compose_reply(tool, result),
        "tool": tool, "args": args, "result": result,
        "protocol_version": payload.get("protocol_version"),
        "server": payload.get("server"),
        "evidence": evidence,
    })


@app.get("/api/tools")
def tools():
    try:
        return jsonify(mcp_client.list_tools(mcp_url()))
    except Exception as e:
        return jsonify({"error": f"{type(e).__name__}: {e}"}), 502


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Crew Memory for Alexa+ — simulated experience</title>
<style>
 body{margin:0;font-family:system-ui,-apple-system,'Segoe UI',sans-serif;
      background:#0b1020;color:#e8ecf8}
 header{padding:18px 22px;display:flex;align-items:center;gap:14px}
 .orb{width:44px;height:44px;border-radius:50%;flex:none;
      background:radial-gradient(circle at 35% 35%,#7dd3fc,#2563eb 60%,#1e3a8a);
      box-shadow:0 0 24px #2563eb88}
 h1{font-size:19px;margin:0} .sub{color:#93a4c8;font-size:13px}
 main{display:grid;grid-template-columns:1.2fr .8fr;gap:16px;padding:0 22px 22px}
 @media(max-width:860px){main{grid-template-columns:1fr}}
 .card{background:#131a30;border:1px solid #263157;border-radius:14px;padding:16px}
 #log{display:flex;flex-direction:column;gap:10px;min-height:280px}
 .msg{max-width:85%;padding:10px 13px;border-radius:12px;line-height:1.45}
 .user{align-self:flex-end;background:#2563eb;color:#fff}
 .bot{align-self:flex-start;background:#1c2745}
 form{display:flex;gap:8px;margin-top:12px}
 input{flex:1;padding:11px;border-radius:10px;border:1px solid #33457a;
       background:#0e1530;color:#e8ecf8;font-size:15px}
 button{padding:11px 16px;border:0;border-radius:10px;background:#38bdf8;
        color:#06283d;font-weight:600;cursor:pointer}
 .chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
 .chip{font-size:12.5px;padding:6px 10px;border-radius:999px;cursor:pointer;
       border:1px solid #33457a;background:#182242;color:#c7d3f2}
 pre{white-space:pre-wrap;word-break:break-word;font-size:12px;color:#a9bce0}
 .ev{font-size:12.5px;color:#8fd0a8;margin:4px 0}
 .lbl{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#7286ad}
</style></head><body>
<header><div class="orb"></div><div>
 <h1>Crew Memory for Alexa+</h1>
 <div class="sub">Simulated Alexa+ experience — every answer below is a live
 MCP call to the Crew Memory server (Streamable HTTP).</div></div></header>
<main>
 <section class="card">
  <div id="log"></div>
  <form id="f"><input id="in" autocomplete="off"
    placeholder="Try: What food allergies do I need to remember?">
  <button>Ask</button></form>
  <div class="chips" id="chips"></div>
 </section>
 <aside class="card">
  <div class="lbl">Under the hood — the live MCP call</div>
  <div id="proto" class="ev">protocol: —</div>
  <pre id="call">Ask something to see the tool call.</pre>
  <div class="lbl">Evidence path</div>
  <div id="evidence"><div class="ev">—</div></div>
 </aside>
</main>
<script>
const log=document.getElementById('log'), inp=document.getElementById('in');
const SUGGEST=["Remember that Leo is lactose intolerant",
 "What food allergies do I need to remember?",
 "What do we do on school mornings?",
 "Hand off to the executor: plan Sunday's groceries around Rosa's visit",
 "What's pending for the executor?"];
const chips=document.getElementById('chips');
SUGGEST.forEach(s=>{const c=document.createElement('span');c.className='chip';
 c.textContent=s;c.onclick=()=>{inp.value=s;document.getElementById('f').requestSubmit()};
 chips.appendChild(c)});
function add(txt,cls){const d=document.createElement('div');d.className='msg '+cls;
 d.textContent=txt;log.appendChild(d);d.scrollIntoView()}
add("Hi — I'm your crew assistant. My memory is shared by my planner, researcher, and executor, and it persists between sessions. Ask me what I remember.",'bot');
document.getElementById('f').onsubmit=async e=>{e.preventDefault();
 const m=inp.value.trim(); if(!m) return; inp.value=''; add(m,'user');
 const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({message:m})});
 const j=await r.json(); add(j.reply||j.error||'…','bot');
 document.getElementById('proto').textContent='protocol: '+(j.protocol_version||'—')+
   ' · server: '+(j.server||'—');
 document.getElementById('call').textContent=j.tool?('tools/call → '+j.tool+'\\n'+
   JSON.stringify(j.args,null,1)):'—';
 const ev=document.getElementById('evidence'); ev.innerHTML='';
 (j.evidence||[]).slice(0,4).forEach(p=>{const d=document.createElement('div');
  d.className='ev'; let s=p.nodes[0].name||p.nodes[0].uid;
  p.rels.forEach((r,i)=>{s+=' —'+r+'→ '+(p.nodes[i+1].name||p.nodes[i+1].uid)});
  d.textContent=s; ev.appendChild(d)});
 if(!(j.evidence||[]).length) ev.innerHTML='<div class="ev">—</div>';};
</script></body></html>"""


@app.get("/")
def index():
    return render_template_string(PAGE)


def main() -> None:
    app.run(host=os.environ.get("HOST", "127.0.0.1"),
            port=int(os.environ.get("SIM_PORT", "5000")))


if __name__ == "__main__":
    main()
