/* =================================================================
   POKÉMON AGENT — Field Log client
   Vanilla JS, no framework. Binds to the pokemon-agent server's
   REST /state + WebSocket /ws contract:
     - WS event {type:"action", actions:[...], state_after:{...}}
     - WS event {type:"screenshot", data:{image:b64}}
     - WS event {type:"state_update", state:{...}}
     - WS event {type:"reasoning"|"decision"|"key_moment"|"alert", ...}
       (pushed by the agent via POST /event)
   ================================================================= */
(function () {
    'use strict';

    var BADGE_NAMES = ['Boulder','Cascade','Thunder','Rainbow','Soul','Marsh','Volcano','Earth'];
    var BADGE_INIT  = ['BLD','CSC','THD','RBW','SOU','MSH','VOL','ERT'];
    var TYPE_COLORS = {
        Normal:'#9a9577', Fire:'#d9482f', Water:'#4f7bd6', Grass:'#6f9b1e',
        Electric:'#c9a227', Ice:'#7fb6b6', Fighting:'#a33725', Poison:'#7e4a86',
        Ground:'#b89a4e', Flying:'#8779c4', Psychic:'#c25478', Bug:'#869520',
        Rock:'#8a7a38', Ghost:'#5a4878', Dragon:'#5838c4', Dark:'#4a3c34', Steel:'#8a8aa0'
    };
    var POLL_MS = 2500, WS_BASE = 1000, WS_MAX = 20000;

    // --- state ---
    var ws=null, wsLive=false, wsDelay=WS_BASE, wsTimer=null, pollTimer=null;
    var autoScroll=true, turnCount=0, actionCount=0, lastStateJSON='', hasFrame=false;
    var sessionStart=Date.now();
    var blackouts=0, caught=0, prevPartyAlive=null;
    var llmErrors=0, llmTotal=0, seenMoments={}, baseURL=loc(), replaying=false;

    // --- console (live tokens) ---
    var consoleStreamAgent = "";  // current agent type being streamed
    var consoleStreamBuf = "";    // accumulated token text
    var consoleStreamEl = null;   // cached ref
    var consoleStatusEl = null;

    var $ = function(id){ return document.getElementById(id); };
    function loc(){ return window.location.protocol+'//'+window.location.host; }
    function wsurl(){ return (location.protocol==='https:'?'wss:':'ws:')+'//'+location.host+'/ws'; }
    function pad(n){ return n<10?'0'+n:''+n; }
    function clock(){ var d=new Date(); return pad(d.getHours())+':'+pad(d.getMinutes())+':'+pad(d.getSeconds()); }

    // ---- session timer ----
    setInterval(function(){
        var s=Math.floor((Date.now()-sessionStart)/1000);
        var h=Math.floor(s/3600), m=Math.floor((s%3600)/60), ss=s%60;
        $('metaSession').textContent = h+':'+pad(m)+':'+pad(ss);
    }, 1000);

    // ---- LLM health ----
    function updateLLMIndicator(){
        var el=$('metaLLM');
        if(!el) return;
        if(llmErrors===0){
            el.textContent='✓ 0 err';
            el.className='meta-v';
        } else {
            var pct = llmTotal > 0 ? Math.round((llmErrors/llmTotal)*100) : 0;
            el.textContent='⚠ '+llmErrors+' err ('+pct+'%)';
            el.className='meta-v warn';
        }
    }

    // ---- status ----
    function setStatus(live, text){
        var dot=$('statusDot');
        dot.className='status-dot '+(live?'live':'dead');
        $('statusText').textContent=text||(live?'live':'offline');
    }

    // ---- agent state ----
    var AGENT_STATE_COLORS = {
        observe:      '#6a6757',  // faint — default/idle
        guide:        '#306230',  // dmg-mid — planning
        navigate:     '#8bac0f',  // dmg-bright — moving
        battle:       '#d9482f',  // signal — combat
        dialog:       '#c9a227',  // gold — talking
        'dialog-vision': '#b8922e',  // slightly dimmer gold — reading screen
        scripted:     '#7e4a86',  // purple — waiting on script
        critique:     '#4f7bd6',  // blue — verifying
        paused:       '#6a6757',  // faint
    };
    function updateAgentState(state){
        var el = $('agentState');
        if (!el) return;
        el.textContent = state;
        el.className = 'meta-v agent-state-' + state;
        // Also colorize via CSS custom property for the cell
        var cell = $('agentStateCell');
        if (cell) {
            var color = AGENT_STATE_COLORS[state] || '#6a6757';
            cell.style.setProperty('--agent-state-color', color);
        }
    }

    // ---- stream (the protagonist) ----
    function entry(kind, label, body){
        var box=$('logContainer');
        var e=document.createElement('div');
        e.className='entry e-'+kind;
        var t=document.createElement('span'); t.className='e-time'; t.textContent=clock();
        var b=document.createElement('span'); b.className='e-body';
        if(label){ var l=document.createElement('span'); l.className='e-label'; l.textContent=label; b.appendChild(l); }
        b.appendChild(document.createTextNode(body));
        e.appendChild(t); e.appendChild(b); box.appendChild(e);
        while(box.children.length>400) box.removeChild(box.firstChild);
        if(autoScroll) box.scrollTop=box.scrollHeight;
    }

    function renderEvent(msg){
        var type=msg.type||msg.event||'status';
        var d=msg.data||msg;
        switch(type){
            case 'action': {
                var acts=msg.actions||d.actions||[];
                var txt=Array.isArray(acts)&&acts.length?acts.join(' · '):(d.action||'(idle)');
                entry('act','ACT', txt);
                turnCount++; actionCount+=Array.isArray(acts)?acts.length:1;
                $('metaTurn').textContent=turnCount; $('ctrActions').textContent=actionCount;
                break;
            }
            case 'reasoning': case 'thought':
                entry('think','THINK', d.text||msg.text||''); break;
            case 'decision':
                entry('decide','DECIDE', d.text||msg.text||''); break;
            case 'critique':
                entry('critique','CRITIQUE', d.text||msg.text||''); break;
            case 'key_moment': case 'moment':
                addMoment(d.description||msg.description||'', d.category||'milestone'); break;
            case 'alert': entry('alert','ALERT', d.message||d.text||msg.message||'');
                // Track LLM errors from alert messages
                var alertText = d.message||d.text||msg.message||'';
                if(alertText.indexOf('LLM')!==-1 || alertText.indexOf('llm')!==-1){
                    llmErrors++;
                    updateLLMIndicator();
                }
                break;
            case 'battle':
                entry('alert','BATTLE', 'vs '+(d.opponent||'???')+(d.result?' — '+d.result:'')); break;
            case 'token':
                appendToken(d.text||'', d.agent||''); break;
            case 'state':
                updateAgentState(d.text||d.state||''); break;
            case 'state_update': case 'screenshot': break; /* silent */
            default:
                if(d.message||d.text||msg.message) entry('sys','', d.message||d.text||msg.message);
        }
    }

    // ---- screenshot ----
    function renderScreen(b64){
        if(!b64) return;
        if(!hasFrame){ hasFrame=true; $('screenOverlay').classList.add('hidden'); }
        $('gameScreen').src='data:image/png;base64,'+b64;
    }

    // ---- collision map ----
    function renderCollision(state) {
        if (!state || !state.collision) return;
        var col = state.collision;
        var grid = col.ascii || '';
        var playerCell = col.player_cell || '';
        var mapName = (state.map || {}).map_name || '';

        // Update coords display
        var coordsEl = $('collisionCoords');
        if (coordsEl) {
            coordsEl.textContent = mapName + (playerCell ? ' ' + playerCell : '');
        }

        // Render the ASCII grid with color spans
        var gridEl = $('collisionGrid');
        if (!gridEl || !grid) return;

        // Render the ASCII grid with color spans.
        // Safe innerHTML: we build HTML from server-provided ASCII grid with
        // a strict character-to-span mapping. No user-controlled input.
        // Legend lines (plain text like "@ you   . walkable") are kept as-is
        // and rendered below the color-coded grid.
        var html = '';
        var lines = grid.split('\n');
        var pastGrid = false;
        for (var li = 0; li < lines.length; li++) {
            var line = lines[li];
            // Detect legend lines: these contain letters/words, not grid chars
            var isLegend = line.trim() === '' ||
                line.trim().startsWith('@ you') ||
                line.trim().startsWith('S stairs') ||
                line.trim().startsWith('W warp') ||
                line.trim().startsWith('● item') ||
                line.trim().startsWith('Legend:');
            if (isLegend) {
                pastGrid = true;
                // Render legend line character-by-character to match pre-commit
                // behavior: grid symbols (@.#SDW●☻) get color spans, text chars
                // (letters/spaces) get dim — producing a color-coded key.
                if (line.trim() !== '') {
                    for (var fi = 0; fi < line.length; fi++) {
                        var fh = line[fi];
                        if (fh === '#' || fh === '▦') {
                            html += '<span class="cg-wall">' + fh + '</span>';
                        } else if (fh === '.' || fh === ' ') {
                            html += '<span class="cg-walk">' + fh + '</span>';
                        } else if (fh === '@') {
                            html += '<span class="cg-player">' + fh + '</span>';
                        } else if (fh === '☻') {
                            html += '<span class="cg-npc">' + fh + '</span>';
                        } else if (fh === '●') {
                            html += '<span class="cg-item">' + fh + '</span>';
                        } else if (fh === 'D') {
                            html += '<span class="cg-door">' + fh + '</span>';
                        } else if (fh === 'S') {
                            html += '<span class="cg-stairs">' + fh + '</span>';
                        } else if (fh === 'W') {
                            html += '<span class="cg-warp">' + fh + '</span>';
                        } else {
                            html += '<span style="color:var(--paper-faint)">' + fh + '</span>';
                        }
                    }
                    html += '\n';
                }
                continue;
            }
            pastGrid = false;
            for (var i = 0; i < line.length; i++) {
                var ch = line[i];
                if (ch === '#' || ch === '▦') {
                    html += '<span class="cg-wall">' + ch + '</span>';
                } else if (ch === '.' || ch === ' ') {
                    html += '<span class="cg-walk">' + ch + '</span>';
                } else if (ch === '@') {
                    html += '<span class="cg-player">' + ch + '</span>';
                } else if (ch === '☻') {
                    html += '<span class="cg-npc">' + ch + '</span>';
                } else if (ch === '●') {
                    html += '<span class="cg-item">' + ch + '</span>';
                } else if (ch === 'D') {
                    html += '<span class="cg-door">' + ch + '</span>';
                } else if (ch === 'S') {
                    html += '<span class="cg-stairs">' + ch + '</span>';
                } else if (ch === 'W') {
                    html += '<span class="cg-warp">' + ch + '</span>';
                } else {
                    // Coordinate numbers and other chars — dim
                    html += '<span style="color:var(--paper-faint)">' + ch + '</span>';
                }
            }
            html += '\n';
        }
        gridEl.innerHTML = html;
    }

    // ---- stats / readout ----
    function renderStats(state){
        if(!state) return;
        var p=state.player||{}, map=state.map||{};
        $('statMap').textContent = map.map_name||'—';
        var pos=p.position||{};
        $('statPosition').textContent='('+(pos.x!=null?pos.x:'—')+', '+(pos.y!=null?pos.y:'—')+')';
        $('statMoney').textContent='₽'+(p.money!=null?Number(p.money).toLocaleString():'—');
        var pt=p.play_time;
        $('statPlayTime').textContent=(typeof pt==='string')?pt:'0:00:00';
        if(state.collision&&state.collision.player_cell) $('statCell').textContent=state.collision.player_cell;
        renderBadges(p.badge_count||0, p.badges||[]);
        renderTeam(state.party||[]);
        renderCollision(state);

        // dialog
        var dlg=state.dialog;
        if(dlg&&dlg.active&&dlg.text){ $('dialogOverlay').classList.remove('hidden'); $('dialogText').textContent=dlg.text; }
        else $('dialogOverlay').classList.add('hidden');

        // battle
        var bt=state.battle;
        if(bt&&bt.in_battle){
            $('battleInfo').classList.remove('hidden');
            var en=bt.enemy||{};
            $('battleContent').textContent=(bt.type||'wild')+' · vs '+(en.species||'???')+' Lv.'+(en.level||'?');
        } else $('battleInfo').classList.add('hidden');

        updateTension(state);
    }

    // ---- objectives (dynamic) ----
    var TIER_LABEL = { primary:'P', secondary:'S', tertiary:'T' };
    function renderObjectives(list){
        var ul=$('objectivesList'); ul.innerHTML='';
        if(!list.length){ var li=document.createElement('li'); li.className='obj-loading'; li.textContent='no objectives set'; ul.appendChild(li); return; }
        list.forEach(function(o){
            var li=document.createElement('li');
            li.className='obj obj-'+(o.tier||'tertiary')+(o.done?' done':'');
            var t=document.createElement('span'); t.className='obj-tier'; t.textContent=TIER_LABEL[o.tier]||'•';
            var x=document.createElement('span'); x.className='obj-text'; x.textContent=o.text||'';
            li.appendChild(t); li.appendChild(x); ul.appendChild(li);
        });
    }

    // ---- control (run state) ----
    function renderControl(state){
        $('ctrlState').textContent=state;
        $('btnStart').classList.toggle('active', state==='running');
        $('btnPause').classList.toggle('active', state==='paused');
        $('btnStop').classList.toggle('active', state==='stopped');
        $('btnStart').disabled = (state==='running');
        $('btnPause').disabled = (state!=='running');
        $('btnStop').disabled  = (state==='stopped');
    }
    function setControl(state){
        fetch(baseURL+'/control', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({state:state})})
            .then(function(r){ return r.json(); })
            .then(function(d){ if(d&&d.state) renderControl(d.state); })
            .catch(function(){});
    }

    // ---- game session ----
    function renderGame(active){
        var el=$('activeGame');
        if(!active){ el.textContent='no game loaded'; $('metaRun').textContent='—'; return; }
        var st=active.stats||{};
        el.innerHTML='';
        var name=document.createElement('span'); name.textContent=active.name||active.id;
        var sub=document.createElement('span'); sub.className='ag-sub';
        sub.textContent=(active.game||'red')+' · '+(st.turns||0)+' turns · brain '+(active.agent_session_id?'linked':'pending');
        el.appendChild(name); el.appendChild(sub);
        $('metaRun').textContent='#'+(active.id||'').slice(-6);
    }
    function newGame(){
        var name=prompt('Name this run (optional):','');
        if(name===null) return; // cancelled
        fetch(baseURL+'/games/new',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:name||null})})
            .then(function(r){return r.json();})
            .then(function(){ $('gameList').classList.add('hidden'); })
            .catch(function(){});
    }
    function toggleGameList(){
        var ul=$('gameList');
        if(!ul.classList.contains('hidden')){ ul.classList.add('hidden'); return; }
        fetch(baseURL+'/games').then(function(r){return r.json();}).then(function(d){
            ul.innerHTML='';
            (d.games||[]).forEach(function(g){
                var li=document.createElement('li');
                li.className='gl-item'+(g.id===d.active?' active':'');
                var n=document.createElement('span'); n.className='gl-name'; n.textContent=g.name||g.id;
                var m=document.createElement('span'); m.className='gl-meta';
                m.textContent=(g.turns||0)+' turns · '+(g.save_count||0)+' saves · '+(g.milestones||0)+' milestones'+(g.latest_save?(' · '+g.latest_save):'');
                li.appendChild(n); li.appendChild(m);
                li.addEventListener('click', function(){ loadGame(g.id); ul.classList.add('hidden'); });
                ul.appendChild(li);
            });
            if(!(d.games||[]).length){ var e=document.createElement('li'); e.className='gl-meta'; e.textContent='no saved games yet'; ul.appendChild(e); }
            ul.classList.remove('hidden');
        }).catch(function(){});
    }
    function loadGame(id){
        fetch(baseURL+'/games/'+id+'/load',{method:'POST'}).then(function(r){return r.json();})
            .then(function(){ poll(); }).catch(function(){});
    }

    function renderBadges(count, list){
        var row=$('badgesRow'); row.innerHTML='';
        for(var i=0;i<8;i++){
            var has = (typeof count==='number'&&i<count) || (list&&list.indexOf(BADGE_NAMES[i])!==-1);
            var b=document.createElement('div');
            b.className='badge'+(has?' earned':''); b.title=BADGE_NAMES[i]+(has?' ✓':'');
            b.textContent=BADGE_INIT[i];
            row.appendChild(b);
        }
    }

    function renderTeam(party){
        var c=$('teamContainer'); c.innerHTML='';
        for(var i=0;i<6;i++){
            if(i<party.length) c.appendChild(pcard(party[i]));
            else { var e=document.createElement('div'); e.className='pcard empty';
                   var s=document.createElement('span'); s.className='pc-empty'; s.textContent='○';
                   e.appendChild(s); c.appendChild(e); }
        }
    }
    function pcard(m){
        var card=document.createElement('div'); card.className='pcard';
        var top=document.createElement('div'); top.className='pc-top';
        var nm=document.createElement('span'); nm.className='pc-name'; nm.textContent=m.nickname||m.species||'???';
        var lv=document.createElement('span'); lv.className='pc-lv'; lv.textContent='Lv'+(m.level||'?');
        top.appendChild(nm); top.appendChild(lv); card.appendChild(top);

        if(m.types&&m.types.length){
            var tw=document.createElement('div'); tw.className='pc-types';
            m.types.forEach(function(t){ var c2=document.createElement('span'); c2.className='type-chip';
                c2.textContent=t; c2.style.background=TYPE_COLORS[t]||'#777'; tw.appendChild(c2); });
            card.appendChild(tw);
        }
        var hp=m.hp!=null?m.hp:0, mx=m.max_hp||1, pct=Math.max(0,Math.round(hp/mx*100));
        var hw=document.createElement('div'); hw.className='pc-hp';
        var bar=document.createElement('div'); bar.className='hpbar';
        var fill=document.createElement('div'); fill.className='hpfill'+(pct<=20?' low':pct<=50?' mid':'');
        fill.style.width=pct+'%'; bar.appendChild(fill);
        var txt=document.createElement('span'); txt.className='hp-text'; txt.textContent=hp+'/'+mx;
        hw.appendChild(bar); hw.appendChild(txt); card.appendChild(hw);

        if(m.status&&m.status!=='OK'){ var st=document.createElement('span'); st.className='pc-status'; st.textContent=m.status; card.appendChild(st); }
        if(m.moves&&m.moves.length){
            var mv=document.createElement('div'); mv.className='pc-moves';
            mv.textContent=m.moves.map(function(x){return (x&&typeof x==='object')?(x.name||'?'):x;}).join(' · ');
            card.appendChild(mv);
        }
        return card;
    }

    // ---- telemetry: blackouts, caught ----
    function updateTension(state){
        // blackout detection: whole party fainted while previously alive.
        // Guard against transient/partial reads: require valid max_hp data and
        // a prior confirmed alive>0 reading before ever counting a blackout.
        var party=state.party||[];
        var validHp = party.length>0 && party.every(function(m){ return (m.max_hp||0)>0; });
        if(validHp){
            var alive=party.filter(function(m){ return (m.hp||0)>0; }).length;
            if(prevPartyAlive!==null && prevPartyAlive>0 && alive===0){
                blackouts++; $('ctrBlackouts').textContent=blackouts;
                $('ctrBlackouts').parentNode.classList.add('alert');
                entry('alert','BLACKOUT','Party wiped out — blackout #'+blackouts+'.');
                addMoment('Blacked out (#'+blackouts+')','alert');
            }
            prevPartyAlive=alive;
        }

        caught = party.length; // simple proxy; refined by key_moment catches
        $('ctrCaught').textContent=Math.max(caught, Number($('ctrCaught').textContent)||0);
    }

    // ---- milestones ----
    function addMoment(desc, category){
        if(!desc) return;
        var sig=category+'|'+desc;
        if(seenMoments[sig]) return;  // dedupe
        seenMoments[sig]=true;
        var tl=$('timeline');
        var empty=tl.querySelector('.tl-empty'); if(empty) empty.remove();
        var li=document.createElement('li'); li.className='tl-item';
        var dot=document.createElement('span'); dot.className='tl-dot '+(category||'milestone');
        var body=document.createElement('div'); body.className='tl-body';
        body.appendChild(document.createTextNode(desc));
        var turn=document.createElement('span'); turn.className='tl-turn'; turn.textContent=' · turn '+turnCount;
        body.appendChild(turn);
        li.appendChild(dot); li.appendChild(body);
        tl.insertBefore(li, tl.firstChild);
        var kind = category==='badge'?'moment':category==='alert'?'alert':'moment';
        entry(kind, category==='alert'?'ALERT':'MILESTONE', desc);
        if(category==='catch'){ caught=Math.max(caught,1)+0; }
        if(category==='badge'){ flashBadges(); }
    }
    function flashBadges(){
        var bs=$('badgesRow').querySelectorAll('.badge.earned');
        if(bs.length){ var last=bs[bs.length-1]; last.classList.add('flash'); setTimeout(function(){last.classList.remove('flash');},600); }
    }

    // ---- WebSocket ----
    function connect(){
        if(ws&&(ws.readyState===0||ws.readyState===1)) return;
        try{ ws=new WebSocket(wsurl()); }catch(e){ reconnect(); return; }
        ws.onopen=function(){ wsLive=true; wsDelay=WS_BASE; setStatus(true,'live (ws)'); entry('sys','','Connected to game server.'); };
        ws.onmessage=function(ev){ try{ handle(JSON.parse(ev.data)); }catch(e){} };
        ws.onclose=function(){ wsLive=false; setStatus(false,'reconnecting'); reconnect(); };
        ws.onerror=function(){};
    }
    function reconnect(){ if(wsTimer) return; wsTimer=setTimeout(function(){ wsTimer=null; connect(); }, wsDelay); wsDelay=Math.min(wsDelay*2, WS_MAX); }
    function handle(msg){
        var type=msg.type||msg.event;
        var payload=msg.data||msg.state||msg.state_after||null;
        if(type==='replay'&&Array.isArray(msg.events)){
            // Backfill the Field Log from the server's event buffer.
            replaying=true;
            msg.events.forEach(function(ev){ renderEvent(ev); });
            replaying=false;
            return;
        }
        if(type==='objectives'){ renderObjectives(msg.objectives||[]); return; }
        if(type==='control'){ renderControl(msg.state||'stopped'); return; }
        if(type==='game'){ renderGame(msg.active||null); return; }
        if(type==='action'){
            renderEvent(msg);
            if(msg.state_after){ var j=JSON.stringify(msg.state_after); if(j!==lastStateJSON){ lastStateJSON=j; renderStats(msg.state_after); } }
        } else if(type==='state_update'&&payload){
            var j2=JSON.stringify(payload); if(j2!==lastStateJSON){ lastStateJSON=j2; renderStats(payload); }
        } else if(type==='screenshot'&&msg.data&&msg.data.image){
            renderScreen(msg.data.image);
        } else if(type==='connected'){
            entry('sys','','Server online · v'+(msg.version||'?'));
        } else renderEvent(msg);
    }

    // ---- polling fallback ----
    function poll(){
        fetch(baseURL+'/state').then(function(r){ if(!r.ok) throw 0; return r.json(); })
        .then(function(s){ if(!wsLive) setStatus(true,'live (poll)');
            var j=JSON.stringify(s); if(j!==lastStateJSON){ lastStateJSON=j; renderStats(s); } })
        .catch(function(){ if(!wsLive) setStatus(false,'no signal'); });
    }
    function pollScreenshot(){
        $('gameScreen').src=baseURL+'/screenshot?_t='+Date.now();
        if(!hasFrame){ hasFrame=true; $('screenOverlay').classList.add('hidden'); }
    }

    // ---- console: live token stream ----
    // Single continuous text buffer — all agent text persists, scrollable.
    var consoleStreamMaxChars = 8000;  // total chars to keep (oldest trimmed)

    function appendToken(text, agent) {
        if (!consoleStreamEl) consoleStreamEl = $('consoleStream');
        if (!consoleStatusEl) consoleStatusEl = $('consoleStatus');
        // Remove idle placeholder on first token
        var idle = consoleStreamEl.querySelector('.cs-idle');
        if (idle) idle.remove();
        // If agent changed, insert an inline label into the text stream
        if (agent && agent !== consoleStreamAgent) {
            consoleStreamAgent = agent;
            consoleStreamBuf += '\n[' + agent.toUpperCase() + ']\n';
        }
        consoleStreamBuf += text;
        // Trim from the front if too long
        if (consoleStreamBuf.length > consoleStreamMaxChars) {
            // Cut at a newline boundary near the trim point
            var cutAt = consoleStreamBuf.length - consoleStreamMaxChars;
            var nl = consoleStreamBuf.indexOf('\n', cutAt);
            consoleStreamBuf = nl !== -1 ? consoleStreamBuf.slice(nl + 1) : consoleStreamBuf.slice(-consoleStreamMaxChars);
        }
        // Render entire buffer into the single pre element
        if (!consoleStreamEl.querySelector('.cs-pre')) {
            var pre = document.createElement('pre');
            pre.className = 'cs-pre';
            consoleStreamEl.appendChild(pre);
        }
        var pre = consoleStreamEl.querySelector('.cs-pre');
        pre.textContent = consoleStreamBuf;
        // Auto-scroll
        consoleStreamEl.scrollTop = consoleStreamEl.scrollHeight;
        if (consoleStatusEl) {
            consoleStatusEl.textContent = (consoleStreamAgent || 'streaming') + ' ●';
            consoleStatusEl.className = 'console-tag active';
        }
    }

    // ---- toggles / init ----
    function initToggles(){
        $('btnClearLog').addEventListener('click', function(){ $('logContainer').innerHTML=''; });
        $('btnStart').addEventListener('click', function(){
            setControl('running');
            fetch(baseURL+'/agent/start', {method:'POST'})
                .then(function(r){ return r.json(); })
                .then(function(d){
                    if(d && d.pid) entry('sys','','Agent started (pid '+d.pid+')');
                    else if(d && d.note) entry('sys','',d.note);
                })
                .catch(function(){});
        });
        $('btnPause').addEventListener('click', function(){ setControl('paused'); });
        $('btnStop').addEventListener('click', function(){ setControl('stopped'); });
        $('btnClearConsole').addEventListener('click', function(){
            if(consoleStreamEl) consoleStreamEl.innerHTML = '';
            consoleStreamBuf = '';
            consoleStreamAgent = '';
            if(consoleStatusEl) {
                consoleStatusEl.textContent = 'idle';
                consoleStatusEl.className = 'console-tag';
            }
        });

        // Model selector — value format is "provider:model"
        $('modelSelect').addEventListener('change', function(){
            var val = this.value;
            var statusEl = $('modelStatus');
            statusEl.textContent = 'switching…';
            statusEl.className = 'model-status';
            var parts = val.split(':');
            var provider = parts[0];
            var model = parts.slice(1).join(':'); // model strings can contain colons
            fetch(baseURL+'/agent/config', {
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body:JSON.stringify({provider: provider, model: model}),
            })
            .then(function(r){ return r.json(); })
            .then(function(d){
                if(d && d.success){
                    var cfg = d.config || {};
                    var display = cfg.provider === 'local'
                        ? 'local / ' + (cfg.model||'?')
                        : cfg.model || val;
                    statusEl.textContent = display;
                    statusEl.className = 'model-status ok';
                    entry('sys','','Model → ' + display);
                } else {
                    statusEl.textContent = 'error: '+(d && d.detail || 'unknown');
                    statusEl.className = 'model-status err';
                }
            })
            .catch(function(e){
                statusEl.textContent = 'error: '+e;
                statusEl.className = 'model-status err';
            });
        });
        $('btnNewGame').addEventListener('click', newGame);
        $('btnGames').addEventListener('click', toggleGameList);
        var box=$('logContainer');
        box.addEventListener('scroll', function(){ autoScroll = box.scrollTop+box.clientHeight >= box.scrollHeight-30; });
    }

    function init(){
        // game name from server info
        fetch(baseURL+'/').then(function(r){return r.json();}).then(function(d){
            if(d.game) $('gameName').textContent=(d.game==='red'?'Red':d.game)+' / Field Log';
        }).catch(function(){});
        // initial objectives + control state (WS also pushes these on connect)
        fetch(baseURL+'/objectives').then(function(r){return r.json();}).then(function(d){ renderObjectives((d&&d.objectives)||[]); }).catch(function(){});
        fetch(baseURL+'/control').then(function(r){return r.json();}).then(function(d){ renderControl((d&&d.state)||'stopped'); }).catch(function(){});
        fetch(baseURL+'/games/current').then(function(r){return r.json();}).then(function(d){ renderGame((d&&d.active)||null); }).catch(function(){});
        initToggles();
        // Load models from config.yaml and build the selector
        fetch(baseURL+'/agent/models').then(function(r){return r.json();}).then(function(d){
            if(!d || !d.providers) return;
            var sel = $('modelSelect');
            sel.innerHTML = '';
            var providers = d.providers;
            var defaultProv = d.default_provider || 'local';
            var defaultModel = (providers[defaultProv] || {}).model || '';
            var opts = [];
            for(var provName in providers){
                if(!providers.hasOwnProperty(provName)) continue;
                var prov = providers[provName];
                var models = prov.models || [];
                var label = provName === 'local' ? 'LM Studio' : 'OpenRouter';
                for(var i=0;i<models.length;i++){
                    var value = provName + ':' + models[i];
                    var text = label + ': ' + models[i];
                    opts.push({value: value, text: text, selected: (provName === defaultProv && models[i])});
                }
            }
            // Sort: local first
            opts.sort(function(a,b){
                var pa = a.value.split(':')[0];
                var pb = b.value.split(':')[0];
                return pa === 'local' ? -1 : pb === 'local' ? 1 : 0;
            });
            for(var k=0;k<opts.length;k++){
                var o = document.createElement('option');
                o.value = opts[k].value;
                o.textContent = opts[k].text;
                if(opts[k].value === defaultProv + ':' + defaultModel) o.selected = true;
                sel.appendChild(o);
            }
            $('modelStatus').textContent = defaultProv + ' / ' + defaultModel;
            $('modelStatus').className = 'model-status ok';
        }).catch(function(){});
        connect();
        poll(); pollTimer=setInterval(poll, POLL_MS);
        setInterval(pollScreenshot, 1500);
        setStatus(false,'connecting');
    }
    if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
