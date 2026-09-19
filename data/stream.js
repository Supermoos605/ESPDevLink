const video = document.getElementById('stream');
const audio = document.createElement('audio');
audio.autoplay = true;
audio.controls = false;
audio.dataset.esplinkAudio = 'true';
audio.muted = false;
audio.volume = 1;
audio.playsInline = true;
document.body.appendChild(audio);
const placeholder = document.getElementById('placeholder');
const gameName = document.getElementById('gameName');
const hint = document.getElementById('gameHint');
const meta = document.getElementById('hostMeta');
const state = document.getElementById('state');
const stage = document.getElementById('stage');
video.autoplay = true; video.muted = true; video.playsInline = true;
// ESPDevLink uses the remote Quick Tunnel path exclusively.
const CONNECTION_MODE = 'REMOTE';
const FORCE_REMOTE = false;
let videoStream=null,audioStream=null;
let lastFailedConnectionRoute='';
let streamStartTime=0;
let hostBase='',hostSession=localStorage.getItem('espLinkHostSession')||'',hostSessionCode='',peerId=null,peer=null,inputChannel=null,signalTimer=null,stopped=false,inputBound=false,connecting=false,connectionToken=0;
let recoveryTimer=null,connectionTimeout=null,iceRecoveryTimer=null,audioStatsTimer=null,lastVideoProgress=0,recoveryInProgress=false;
const pressedKeys=new Set(),pressedButtons=new Set();
const labels={ready:'READY',connecting:'CONNECTING',streaming:'LIVE',error:'ERROR',offline:'OFFLINE'};
function paint({state:nextState,game=''}){
  if(state){} if(typeof nextState!=='string') return;
  if(typeof state!=='undefined' && state) state.textContent=labels[nextState]||nextState.toUpperCase();
  if(gameName) gameName.textContent=game || '';
  if(placeholder) placeholder.style.display=nextState==='streaming'?'none':'';
  if(meta) meta.textContent=nextState==='streaming'?'Connected':'';
}
const diagnostics=[];
function diag(label,value=''){
  const line=`${label}${value!==''?': '+value:''}`;
  diagnostics.push(line); if(diagnostics.length>80) diagnostics.shift();
  diagnosticPanel.textContent=diagnostics.join('\\n'); console.debug('[ESPDevLink]',line);
}
const diagnosticPanel=document.createElement('pre');
diagnosticPanel.id='webrtcDiagnostics';
diagnosticPanel.style.cssText='position:fixed;left:12px;right:12px;bottom:64px;z-index:20;margin:0;padding:10px;border:1px solid #555;border-radius:8px;background:#111;color:#9f9;font:12px/1.35 monospace;white-space:pre-wrap;max-height:34vh;overflow:auto;display:none;';
document.body.appendChild(diagnosticPanel);
function sendInput(type,action,data={}){if(inputChannel&&inputChannel.readyState==='open'){try{inputChannel.send(JSON.stringify({type,action,data}));}catch(error){diag('input send error',error.message);}}}
function pointerData(event){const rect=video.getBoundingClientRect();const sourceWidth=video.videoWidth||16;const sourceHeight=video.videoHeight||9;const scale=Math.min(rect.width/sourceWidth,rect.height/sourceHeight);const renderedWidth=sourceWidth*scale;const renderedHeight=sourceHeight*scale;const offsetX=(rect.width-renderedWidth)/2;const offsetY=(rect.height-renderedHeight)/2;const x=(event.clientX-rect.left-offsetX)/renderedWidth;const y=(event.clientY-rect.top-offsetY)/renderedHeight;return{x:Math.max(0,Math.min(1,x)),y:Math.max(0,Math.min(1,y)),inside:x>=0&&x<=1&&y>=0&&y<=1,button:event.button===2?'right':event.button===1?'middle':'left',pointer_type:event.pointerType||'mouse'};}
function bindInput(){if(inputBound)return;inputBound=true;video.style.touchAction='none';video.addEventListener('contextmenu',e=>e.preventDefault());document.addEventListener('keydown',e=>{if(stopped||['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName))return;if(!pressedKeys.has(e.code)){pressedKeys.add(e.code);sendInput('key','down',{code:e.code,key:e.key,repeat:e.repeat});}e.preventDefault();});document.addEventListener('keyup',e=>{if(stopped)return;pressedKeys.delete(e.code);sendInput('key','up',{code:e.code,key:e.key});e.preventDefault();});video.addEventListener('pointermove',e=>{if(!stopped){const d=pointerData(e);if(d.inside)sendInput('mouse','move',d);}});video.addEventListener('pointerdown',e=>{if(stopped)return;const d=pointerData(e);if(!d.inside)return;video.setPointerCapture?.(e.pointerId);pressedButtons.add(d.button);sendInput('mouse','down',d);e.preventDefault();});video.addEventListener('pointerup',e=>{if(stopped)return;const d=pointerData(e);pressedButtons.delete(d.button);sendInput('mouse','up',d);video.releasePointerCapture?.(e.pointerId);e.preventDefault();});video.addEventListener('pointercancel',e=>{if(stopped)return;const d=pointerData(e);pressedButtons.delete(d.button);sendInput('mouse','up',d);e.preventDefault();});video.addEventListener('pointerleave',e=>{if(stopped)return;const d=pointerData(e);if(d.inside)return;sendInput('mouse','leave',d);});video.addEventListener('wheel',e=>{if(!stopped){sendInput('mouse','wheel',{deltaX:e.deltaX,deltaY:e.deltaY});e.preventDefault();}},{passive:false});window.addEventListener('blur',releaseInput);}
function releaseInput(){for(const code of pressedKeys)sendInput('key','up',{code});for(const button of pressedButtons)sendInput('mouse','up',{button});pressedKeys.clear();pressedButtons.clear();}
async function pollAudioStats(){
if(stopped||!peerId||!peer)return;
try{
const result=await request(hostBase,'/api/webrtc/stats',{headers:{'X-ESPLink-Peer':peerId}});
const a=result?.stats?.audio_capture;
const out=result?.stats?.audio;
if(a){
diag('host audio capture',`device=${a.device||'(unknown)'} frames=${a.capture_frames??0} non-silent=${a.non_silent_frames??0} peak=${a.peak??0} rms=${a.rms??0} drops=${a.queue_drops??0}`);
}
if(out)diag('host audio WebRTC',`packets=${out.packets_sent??0} bytes=${out.bytes_sent??0}`);
const pipeline=result?.stats?.audio_pipeline;
if(pipeline)diag('audio pipeline',`capture=${pipeline.capture} samples=${pipeline.samples} non-silent=${pipeline.non_silent} webrtc=${pipeline.webrtc}`);
const track=audioStream?.getAudioTracks?.()[0];
diag('browser audio',`track=${track?.readyState||'missing'} muted=${audio.muted} paused=${audio.paused} readyState=${audio.readyState} volume=${audio.volume}`);
const browserStats=await peer.getStats();
let inboundAudio=null;
browserStats.forEach(r=>{if(r.type==='inbound-rtp'&&r.kind==='audio')inboundAudio=r;});
if(inboundAudio)diag('browser audio RTP',`packets=${inboundAudio.packetsReceived??0} bytes=${inboundAudio.bytesReceived??0} packetsLost=${inboundAudio.packetsLost??0} jitter=${inboundAudio.jitter??0}`);
}catch(error){diag('audio stats error',error.message);}
}
function clearRecoveryTimers(){clearInterval(recoveryTimer);recoveryTimer=null;clearTimeout(connectionTimeout);connectionTimeout=null;clearTimeout(iceRecoveryTimer);iceRecoveryTimer=null;clearInterval(audioStatsTimer);audioStatsTimer=null;}
function markVideoProgress(){lastVideoProgress=Date.now();if(recoveryInProgress){recoveryInProgress=false;diag('video recovery','restored');}}
function beginRecovery(reason){if(stopped||recoveryInProgress)return;recoveryInProgress=true;diag('recovery requested',reason);hint.textContent=`${reason} Recovering stream…`;window.ESPLinkDashboard?.setError?.(reason);fail(reason);}
function startRecoveryWatchdog(){clearRecoveryTimers();lastVideoProgress=Date.now();recoveryTimer=setInterval(()=>{if(stopped||!peer)return;const connected=peer.connectionState==='connected'||peer.iceConnectionState==='connected'||peer.iceConnectionState==='completed';if(connected&&video.srcObject&&Date.now()-lastVideoProgress>8000)beginRecovery('Video stream stalled.');},2000);connectionTimeout=setTimeout(()=>{if(!stopped&&peer&&peer.connectionState!=='connected')beginRecovery('Connection timed out.');},15000);}
async function createPeer(token){
streamStartTime=performance.now();const selected=localStorage.getItem('espLinkSelectedGame')||'Desktop';const mode=selected==='Test Stream'?'test':'desktop';const session=await request(hostBase,'/api/webrtc/session',{method:'POST',body:JSON.stringify({video_mode:mode,session_id:hostSession,quality:localStorage.getItem('espLinkQuality')||'auto'})});diag('host audio',session.audio?.enabled?'enabled':(session.audio?.error||'unavailable'));diag('host input',session.input?.enabled?'enabled':'disabled');if(token!==connectionToken)throw new Error('Connection attempt superseded.');peerId=session.peer_id;diag('session created',peerId);const iceServers=Array.isArray(session.ice_servers)?session.ice_servers:[];diag('ICE servers configured',String(iceServers.length));peer=new RTCPeerConnection({iceServers});window.ESPLinkPeer=peer;peer.onsignalingstatechange=()=>diag('signalingState',peer.signalingState);peer.onconnectionstatechange=()=>{diag('connectionState',peer.connectionState);if(peer.connectionState==='connected'){reportSelectedIcePair();clearTimeout(connectionTimeout);if(window.ESPLinkReconnect)window.ESPLinkReconnect.reset();paint({state:'streaming',game:selected});}if(peer.connectionState==='disconnected'&&!stopped&&!iceRecoveryTimer){diag('ICE recovery','grace period started');iceRecoveryTimer=setTimeout(()=>beginRecovery('ICE connection lost.'),5000);}if(peer.connectionState==='failed'||peer.connectionState==='closed')beginRecovery('The WebRTC connection failed.');};peer.oniceconnectionstatechange=()=>{diag('iceConnectionState',peer.iceConnectionState);if(peer.iceConnectionState==='disconnected'&&!stopped&&!iceRecoveryTimer)iceRecoveryTimer=setTimeout(()=>beginRecovery('ICE connection lost.'),5000);if(peer.iceConnectionState==='connected'||peer.iceConnectionState==='completed'){clearTimeout(iceRecoveryTimer);iceRecoveryTimer=null;}};peer.onicegatheringstatechange=()=>diag('iceGatheringState',peer.iceGatheringState);peer.onicecandidateerror=e=>diag('iceCandidateError',`${e.errorCode||''} ${e.errorText||''}`);
async function reportSelectedIcePair(){try{const stats=await peer.getStats();let pair;stats.forEach(r=>{if(r.type==='candidate-pair'&&r.state==='succeeded'&&(r.nominated||!pair))pair=r;});if(!pair){diag('selected ICE pair','not reported by browser');return;}const local=stats.get(pair.localCandidateId);const remote=stats.get(pair.remoteCandidateId);const lt=local?.candidateType||'unknown';const rt=remote?.candidateType||'unknown';diag('selected ICE path',lt+' → '+rt+' · '+(pair.protocol||'unknown'));if(lt==='relay'||rt==='relay')diag('ICE transport','RELAY');else if(lt==='srflx'||rt==='srflx')diag('ICE transport','DIRECT via STUN/NAT');else diag('ICE transport','DIRECT host');}catch(error){diag('ICE stats error',error?.message||String(error));}}peer.onicecandidate=e=>{if(e.candidate){const raw=e.candidate.candidate||'candidate';const type=(raw.match(/ typ ([a-z]+)/i)||[])[1]||'unknown';diag('local ICE candidate',type+' — '+raw);sendSignal({type:'ice-candidate',candidate:e.candidate.toJSON()});}else diag('local ICE gathering complete');};inputChannel=peer.createDataChannel('input',{ordered:false,maxRetransmits:0});inputChannel.onopen=()=>{diag('input channel','open');hint.textContent='Keyboard, mouse, and touch input enabled.';window.ESPLinkDashboard?.update?.();};inputChannel.onclose=()=>{diag('input channel','closed');releaseInput();window.ESPLinkDashboard?.update?.();};inputChannel.onerror=e=>diag('input channel error',e.message||'channel error');bindInput();peer.ontrack=async e=>{
const kind=e.track?.kind||'unknown';
diag('track received',kind);
if(kind==='video'){
    if(!videoStream)videoStream=new MediaStream();
    videoStream.addTrack(e.track);
    video.srcObject=videoStream;
    markVideoProgress();
    placeholder.style.display='none';
    try{await video.play();diag('video playback','started');diag('startup latency',`${Math.round(performance.now()-streamStartTime)} ms`);paint({state:'streaming',game:selected});}
    catch(error){diag('video playback blocked',error.message);console.error(error);}
    return;
}
if(kind==='audio'){
    if(!audioStream)audioStream=new MediaStream();
    audioStream.addTrack(e.track);
    e.track.enabled = true;
    audio.srcObject=audioStream;
    diag('audio track','received from host');
    diag('audio state',`muted=${audio.muted} enabled=${e.track.enabled} ready=${audio.readyState}`);
    try{await audio.play();diag('audio playback','started');}
    catch(error){diag('audio playback blocked',error.message);console.error(error);hint.textContent='Press Audio to enable sound.';}
    return;
}
};video.ontimeupdate=markVideoProgress;video.onclick=()=>video.play().catch(error=>diag('video click playback error',error.message));startRecoveryWatchdog();audioStatsTimer=setInterval(pollAudioStats,2000);
// Explicit recvonly transceivers keep the browser SDP media directions defined.
// This is important for Safari/iPadOS receive-only sessions.
// Keep the offer strictly receive-only: Safari can otherwise create a
// second implicit video transceiver when an event handler touches the media.
const videoTransceiver=peer.getTransceivers().find(t=>t.kind==='video');
if(videoTransceiver)videoTransceiver.direction='recvonly';else peer.addTransceiver('video',{direction:'recvonly'});
// Only offer audio when the Windows host actually has a capture track.
if(session.audio?.enabled&&!peer.getTransceivers().some(t=>t.kind==='audio'))peer.addTransceiver('audio',{direction:'recvonly'});
const offer=await peer.createOffer();await peer.setLocalDescription(offer);diag('offer sent');await sendSignal({type:'offer',sdp:offer.sdp});signalTimer=setInterval(receiveSignals,500);}
async function sendSignal(message){const id=peerId;const p=peer;if(stopped||!id||!p)return;if(!p||p!==peer)return;diag('signal sent',message.type);await request(hostBase,'/api/webrtc/message',{method:'POST',headers:{'X-ESPLink-Peer':id},body:JSON.stringify(message)});}
function fail(message){
const failedRoute=window.ESPLinkConnectionMode;
if(CONNECTION_MODE==='AUTOMATIC'&&(failedRoute==='LOCAL'||failedRoute==='REMOTE')){
  lastFailedConnectionRoute=failedRoute;
  diag('automatic fallback',failedRoute==='LOCAL'?'LOCAL failed; next retry will try REMOTE':'REMOTE failed; next retry will try LOCAL');
}
if(failedRoute==='REMOTE'||failedRoute==='FORCED_REMOTE'){
  window.ESPLinkConnectionTransition='REFRESHING REMOTE';
  window.ESPLinkDashboard?.update?.();
  refreshRemoteRoute();
}
diag('failure',message);window.ESPLinkDashboard?.setError?.(message);stopped=true;connecting=false;clearRecoveryTimers();releaseInput();clearInterval(signalTimer);signalTimer=null;if(peer)peer.close();peer=null;window.ESPLinkPeer=null;inputChannel=null;peerId=null;paint({state:'error',game:localStorage.getItem('espLinkSelectedGame')||'Desktop'});hint.textContent=message;console.error(message);if(window.ESPLinkReconnect&&window.ESPLinkReconnect.schedule(async()=>{
  if(failedRoute==='REMOTE'||failedRoute==='FORCED_REMOTE'){
    window.ESPLinkConnectionTransition='REFRESHING REMOTE';
    window.ESPLinkDashboard?.update?.();
    await refreshRemoteRoute();
  }
  await start(false);
},status=>{diag('reconnect',status.message);hint.textContent=status.message;})){stopped=false;}}
async function receiveSignals(){if(stopped||!peerId||!peer)return;const id=peerId;const p=peer;try{const result=await request(hostBase,'/api/webrtc/messages',{headers:{'X-ESPLink-Peer':id}});if(stopped||peerId!==id||peer!==p)return;for(const message of result.messages||[]){if(stopped||peerId!==id||peer!==p)return;diag('signal received',message.type);if(message.type==='answer'&&p.signalingState!=='stable'){await p.setRemoteDescription({type:'answer',sdp:message.sdp});diag('remote description','applied');for(const t of p.getTransceivers())diag('negotiated transceiver',t.kind+' local='+t.direction+' current='+(t.currentDirection||'none'));const audioReceiver=p.getReceivers().find(r=>r.track?.kind==='audio');diag('audio receiver',audioReceiver?'present':'missing');if(audioReceiver)diag('audio receiver track',audioReceiver.track.id||'unknown');}else if(message.type==='ice-candidate'&&message.candidate)await p.addIceCandidate(message.candidate);else if(message.type==='error'){fail(message.message||'The host could not create the requested stream.');return;}}}catch(error){if(!stopped&&peerId===id&&peer===p){diag('signaling error',error.message);console.warn('Signaling:',error.message);}}}
async function refreshRemoteRoute(){
  try{
    const result=await request('', '/api/remote/refresh', {method:'POST'});
    diag('remote refresh',`online=${result.online} url=${result.url||'(empty)'}`);
    return result;
  }catch(error){
    diag('remote refresh failed',error.message);
    return null;
  }
}

async function start(interactive=true){if(connecting)return;connecting=true;const token=++connectionToken;try{stopped=false;recoveryInProgress=false;clearRecoveryTimers();clearInterval(signalTimer);signalTimer=null;window.ESPLinkConnectionTransition='SELECTING';window.ESPLinkDashboard?.update?.();if(peer){try{peer.close();}catch(_){}}peer=null;window.ESPLinkPeer=null;inputChannel=null;peerId=null;if(video.srcObject){video.srcObject.getTracks().forEach(t=>t.stop());video.srcObject=null;}
stopStreamStats();
statsTimer=setInterval(collectStreamStats,5000);
if(audio.srcObject){audio.srcObject.getTracks().forEach(t=>t.stop());audio.srcObject=null;}
videoStream=null;audioStream=null;paint({state:'connecting',game:localStorage.getItem('espLinkSelectedGame')||'Test Stream'});await connectHost();if(token!==connectionToken||stopped)return;await createPeer(token);}catch(error){if(token===connectionToken&&!stopped)fail(error.message);}finally{if(token===connectionToken)connecting=false;}}
async function stop(){connectionToken++;stopped=true;lastFailedConnectionRoute='';window.ESPLinkConnectionTransition='STOPPED';if(window.ESPLinkReconnect)window.ESPLinkReconnect.cancel();clearRecoveryTimers();releaseInput();clearInterval(signalTimer);signalTimer=null;if(peer)peer.close();peer=null;window.ESPLinkPeer=null;inputChannel=null;peerId=null;if(video.srcObject){video.srcObject.getTracks().forEach(t=>t.stop());video.srcObject=null;}if(audio.srcObject){audio.srcObject.getTracks().forEach(t=>t.stop());audio.srcObject=null;}videoStream=null;audioStream=null;connecting=false;paint({state:'ready',game:''});diag('stopped');}
stopStreamStats();
const sendEscape=()=>{sendInput('key','down',{code:'Escape',key:'Escape',repeat:false});setTimeout(()=>sendInput('key','up',{code:'Escape',key:'Escape'}),35);diag('Esc','sent');};document.getElementById('escape').onclick=sendEscape;document.getElementById('escape').onpointerdown=e=>{e.preventDefault();sendEscape()};
document.getElementById('dashboardToggle').onclick=()=>{const panel=document.getElementById('dashboard');const hidden=panel.style.display==='none';panel.style.display=hidden?'grid':'none';document.getElementById('dashboardToggle').textContent=hidden?'⌃':'⌄';};
document.getElementById('settings').onclick=()=>{location.href='/settings.html'};
document.getElementById('games').onclick=async()=>{await stop();location.href='/games.html'};
document.getElementById('retry').onclick=async()=>{await stop();start();};
document.getElementById('disconnect').onclick=()=>{localStorage.removeItem('espLinkHostSession');hostSession='';stop();};
const audioButton=document.getElementById('mute');
const syncAudioUI=()=>{audioButton.textContent=audio.muted?'🔇 Audio':'🔊 Audio';window.ESPLinkDashboard?.update?.();};
audio.addEventListener('volumechange',syncAudioUI);
audio.addEventListener('play',syncAudioUI);
audioButton.onclick=async()=>{
  audio.muted=!audio.muted;
  audio.volume=1;
  localStorage.setItem('espLinkAudioEnabled',audio.muted?'0':'1');
  const track=audioStream?.getAudioTracks?.()[0];
  if(track) track.enabled=true;
  try{
    await audio.play();
    diag('audio playback','enabled by user gesture');
  }catch(error){
    diag('audio playback error',error.message);
    hint.textContent='Audio could not start: '+error.message;
  }
  syncAudioUI();
};
const fullscreenButton=document.getElementById('fullscreen');
const syncFullscreenUI=()=>{
  const active=!!document.fullscreenElement;
  fullscreenButton.textContent=active?'⛶ Exit fullscreen':'⛶ Fullscreen';
  fullscreenButton.setAttribute('aria-label',active?'Exit fullscreen':'Enter fullscreen');
};
fullscreenButton.onclick=async()=>{
  try{
    if(document.fullscreenElement) await document.exitFullscreen();
    else await stage.requestFullscreen();
  }catch(error){
    diag('fullscreen error',error.message);
    hint.textContent='Fullscreen is not available in this browser.';
  }
  syncFullscreenUI();
};
document.addEventListener('fullscreenchange',syncFullscreenUI);
syncFullscreenUI();
document.getElementById('update').onclick=async()=>{
  if(!confirm('Update ESPDevLink from GitHub and restart the host? The current stream will disconnect.'))return;
  const button=document.getElementById('update');
  button.disabled=true;
  button.textContent='Updating…';
  hint.textContent='Updating ESPDevLink and restarting the host…';
  diag('remote update','requested');
  try{
    const result=await request(hostBase,'/api/admin/update',{method:'POST',body:JSON.stringify({session_id:hostSession})});
    diag('remote update',result.message||result.state||'started');
    hint.textContent='Update started. Reconnecting when the host is back online…';
  }catch(error){
    diag('remote update error',error.message);
    hint.textContent='Update could not be started: '+error.message;
    button.disabled=false;
    button.textContent='↻ Update & Restart';
  }
};
document.getElementById('diagnostics').onclick=()=>{diagnosticPanel.style.display=diagnosticPanel.style.display==='none'?'block':'none';};
start();