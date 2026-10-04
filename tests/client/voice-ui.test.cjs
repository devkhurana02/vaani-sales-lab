const test=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const source=fs.readFileSync('vaani/static/voice-ui.js','utf8');
function harness({ready=true,denyMic=false,connectGate=null}={}){
 const nodes=new Map();
 const $=id=>{if(!nodes.has(id))nodes.set(id,{value:id==='voice-planner'?'rules':'hi',checked:false,disabled:false,hidden:false,textContent:'',children:[],listeners:{},classList:{toggle(){}},append(...items){this.children.push(...items);},replaceChildren(){this.children=[];},addEventListener(name,fn){this.listeners[name]=fn;}});return nodes.get(id);};
 const rooms=[];
 class Room{
  constructor(){rooms.push(this);this.events={};this.remoteParticipants=new Map();this.mic=[];this.disconnections=0;this.canPlaybackAudio=true;this.localParticipant={setMicrophoneEnabled:async enabled=>{if(denyMic){const e=new Error('denied');e.name='NotAllowedError';throw e;}this.mic.push(enabled);}};}
  on(name,fn){this.events[name]=fn;return this;}
  async connect(){if(connectGate)await connectGate;}
  async startAudio(){}
  async disconnect(){this.disconnections++;this.events.Disconnected?.();}
 }
 const events=Object.fromEntries(['TrackSubscribed','TrackUnsubscribed','ParticipantConnected','ParticipantAttributesChanged','TranscriptionReceived','AudioPlaybackStatusChanged','Reconnecting','Reconnected','Disconnected'].map(x=>[x,x]));
 const calls=[];
 const api=async(path,data)=>{calls.push({path,data});if(path==='/api/voice/status')return {ready,gemini_ready:false,checks:{SDK:true,Credentials:ready}};if(path==='/api/evaluations')return [];if(path==='/api/voice/connect')return {session_id:'sid',url:'wss://test.example',token:'fake'};if(path==='/api/sessions/sid')return {turns:[],voice_events:[],voice_metrics:{sample_size:0,p50_ms:null,p95_ms:null,interrupted_replies:0},state:{stage:'consent'}};throw new Error(path);};
 const sandbox={$,api,el:(tag,text)=>({tag,text,append(){},replaceChildren(){}}),notice:()=>{},refresh:async()=>{},renderEvaluation:()=>{},document:{querySelector:()=>$('eval-nav')},window:{LivekitClient:{Room,RoomEvent:events,Track:{Kind:{Audio:'audio'}}},addEventListener(){}},setInterval:()=>1,clearInterval(){},setTimeout:()=>1,clearTimeout(){},console};
 vm.createContext(sandbox);vm.runInContext(source,sandbox);
 return {$,rooms,calls,settle:()=>new Promise(resolve=>setImmediate(resolve)),click:id=>$(id).listeners.click()};
}
test('missing configuration disables calls without issuing a token',async()=>{const h=harness({ready:false});await h.settle();assert.equal(h.$('voice-start').disabled,true);assert.equal(h.calls.some(c=>c.path==='/api/voice/connect'),false);});
test('connect enables mic and end disconnects the room',async()=>{const h=harness();await h.settle();await h.click('voice-start');assert.deepEqual(h.rooms[0].mic,[true]);assert.equal(h.$('voice-stop').disabled,false);await h.click('voice-stop');assert.equal(h.rooms[0].disconnections,1);assert.equal(h.$('voice-start').disabled,false);});
test('mute and unmute update actual microphone publication',async()=>{const h=harness();await h.settle();await h.click('voice-start');await h.click('voice-mute');await h.click('voice-mute');assert.deepEqual(h.rooms[0].mic,[true,false,true]);});
test('microphone denial disconnects and shows a recoverable error',async()=>{const h=harness({denyMic:true});await h.settle();await h.click('voice-start');assert.match(h.$('voice-error').textContent,/permission was denied/);assert.equal(h.rooms[0].disconnections,1);assert.equal(h.$('voice-start').disabled,false);});
test('ending a pending connection prevents microphone activation',async()=>{let release;const gate=new Promise(r=>release=r);const h=harness({connectGate:gate});await h.settle();const pending=h.click('voice-start');await h.settle();await h.click('voice-stop');release();await pending;assert.deepEqual(h.rooms[0].mic,[]);assert.equal(h.$('voice-start').disabled,false);});
