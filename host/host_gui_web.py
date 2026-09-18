"""Browser-rendered ESPDevLink Windows control center."""
from __future__ import annotations
import json, os, socket, subprocess, sys, urllib.request, webbrowser
from pathlib import Path
import webview

HOST_URL="http://127.0.0.1:8765"
ROOT=Path(__file__).resolve().parents[1]
HTML=Path(__file__).with_name("host_gui_web.html")

class HostControlAPI:
    def __init__(self): self.processes=[]
    def _python(self):
        p=ROOT/".venv"/"Scripts"/"python.exe"
        return str(p) if p.exists() else sys.executable
    def _start(self,args,label):
        try:
            p=subprocess.Popen(args,cwd=ROOT,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            self.processes.append(p); return f"{label} started (PID {p.pid})."
        except Exception as exc: return f"{label} failed: {exc}"
    def _run(self,args,label):
        try:
            r=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,timeout=120)
            out=(r.stdout+r.stderr).strip()
            return f"{label}: exit {r.returncode}\n{out[-7000:]}"
        except Exception as exc: return f"{label} failed: {exc}"
    def action(self,name):
        py=self._python()
        if name=="start": return self._start([py,"-m","host.host_server"],"Host server")
        if name=="stop":
            n=0
            for p in self.processes:
                if p.poll() is None: p.terminate(); n+=1
            return f"Stopped {n} tracked process(es)."
        if name=="heartbeat": return self._start([py,"-m","host.network.heartbeat"],"Network heartbeat")
        if name=="simulator": return self._start([py,"simulator/esp_link_simulator.py"],"Simulator")
        if name=="tests": return self._run([py,"-m","pytest"],"Tests")
        if name=="deps": return self._run([py,"-m","pip","install","-r","host/requirements.txt"],"Dependency install")
        if name=="venv": return self._run([sys.executable,"-m","venv",str(ROOT/".venv")],"Virtual environment")
        if name=="diagnostics": return self._run([py,"-m","host.run_host"],"Diagnostics")
        if name=="streamStart": return self._post("/api/host/stream/start","Start stream")
        if name=="streamStop": return self._post("/api/host/stream/stop","Stop stream")
        return f"Unknown action: {name}"
    def _post(self,path,label):
        try:
            req=urllib.request.Request(HOST_URL+path,data=b"{}",headers={"Content-Type":"application/json"},method="POST")
            with urllib.request.urlopen(req,timeout=3) as r: return f"{label}: {r.read().decode('utf-8')}"
        except Exception as exc: return f"{label} failed: {exc}"
    def status(self):
        data={"host_online":False,"computer":socket.gethostname(),"ip":self._local_ip(),"mdns":socket.gethostname()+".local","mode":os.environ.get("ESPLINK_CONNECTION_MODE","AUTOMATIC"),"stream":{}}
        try:
            with urllib.request.urlopen(HOST_URL+"/api/host/status",timeout=1.5) as r: h=json.loads(r.read().decode("utf-8"))
            data["host_online"]=True; data["host"]=h
            data["stream"]={"state":h.get("stream_state"),"game":h.get("game"),"quality":h.get("stream_quality"),"health":h.get("stream_health")}
        except Exception: pass
        return data
    @staticmethod
    def _local_ip():
        try:
            s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.connect(("1.1.1.1",80)); ip=s.getsockname()[0]; s.close(); return ip
        except OSError: return "127.0.0.1"
    def open_web(self): webbrowser.open(HOST_URL+"/"); return "Opened web interface."
    def open_esp32(self): webbrowser.open("http://steamlink.local/"); return "Opened ESP32 interface."
    def set_mode(self,mode):
        mode=mode.strip().upper()
        if mode not in {"AUTOMATIC","REMOTE","FORCE_REMOTE"}: return "Invalid connection mode."
        os.environ["ESPLINK_CONNECTION_MODE"]=mode; self.action("stop"); return self.action("start")+f" Mode set to {mode}."
    def schedule(self,value):
        import re
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d",value.strip()): return "Invalid time. Use HH:MM."
        bat=ROOT/"host"/"run_esp_link_host.bat"
        r=subprocess.run(["schtasks","/Create","/TN","ESPDevLink Host Daily Start","/TR",f'"{bat}"',"/SC","DAILY","/ST",value.strip(),"/F"],capture_output=True,text=True)
        return (r.stdout+r.stderr).strip()
    def cancel_schedule(self):
        r=subprocess.run(["schtasks","/Delete","/TN","ESPDevLink Host Daily Start","/F"],capture_output=True,text=True); return (r.stdout+r.stderr).strip()
    def show_schedule(self):
        r=subprocess.run(["schtasks","/Query","/TN","ESPDevLink Host Daily Start","/V","/FO","LIST"],capture_output=True,text=True); return (r.stdout+r.stderr).strip() or "No schedule found."

def main():
    api=HostControlAPI()
    webview.create_window("ESPDevLink Host Control Center",str(HTML),width=1200,height=800,min_size=(900,650),resizable=True,js_api=api,background_color="#080a0f")
    webview.start(gui="edgechromium")

if __name__=="__main__": main()
