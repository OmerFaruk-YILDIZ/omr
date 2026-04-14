const $=id=>document.getElementById(id);
let answerKey=[], batchFiles=[], batchResults=[], batchStats={};

// ═══════════ STEP NAVIGATION ═══════════
function goStep(n){
  [1,2,3].forEach(i=>{
    $(`step${i}`).classList.toggle('hidden',i!==n);
    $(`s${i}`).classList.toggle('active',i===n);
    $(`s${i}`).classList.toggle('done',i<n);
  });
  $('resultsSection').classList.add('hidden');
  if(n===3) updateKeyInfo();
}

// ═══════════ STEP 2: CEVAP ANAHTARI ═══════════
function switchTab(t){
  document.querySelectorAll('.tab').forEach((el,i)=>el.classList.toggle('active',i===(t==='manual'?0:1)));
  $('tabManual').classList.toggle('hidden',t!=='manual');
  $('tabScan').classList.toggle('hidden',t!=='scan');
}

// Manuel giris
$('manualKey').oninput=()=>{
  const v=$('manualKey').value.trim();
  const keys=v?v.split(',').map(k=>k.trim()).filter(k=>k):[];
  answerKey=keys;
  $('keyCount').textContent=`${keys.length} cevap girildi`;
};

// Formdan okuma
const ku=$('keyUpload'), kf=$('keyFile');
ku.ondragover=e=>{e.preventDefault();ku.classList.add('dragover')};
ku.ondragleave=()=>ku.classList.remove('dragover');
ku.ondrop=e=>{e.preventDefault();ku.classList.remove('dragover');scanKey(e.dataTransfer.files[0])};
kf.onchange=e=>scanKey(e.target.files[0]);

async function scanKey(f){
  if(!f)return;
  $('keyStatus').classList.remove('hidden');
  $('keyStatus').innerHTML='<span class="spinner"></span> Cevap anahtari okunuyor...';
  const fd=new FormData();
  fd.append('file',f);
  fd.append('num_questions',$('numQ').value);
  fd.append('num_choices',$('numC').value);
  fd.append('rows_per_col',$('rowsPerCol').value);
  try{
    const r=await fetch('/analyze_key',{method:'POST',body:fd});
    const d=await r.json();
    if(d.error)throw new Error(d.error);
    answerKey=d.answer_key||[];
    const preview=answerKey.slice(0,20).join(', ')+(answerKey.length>20?'...':'');
    $('keyStatus').innerHTML=`<div class="key-ok">&#10003; ${answerKey.length} cevap okundu<div class="key-preview">${preview}</div></div>`;
    ku.classList.add('has-file');
    ku.innerHTML=`<div style="display:flex;align-items:center;gap:10px"><span style="font-size:24px">&#128273;</span><div><div style="font-size:13px;color:#34d399">${f.name}</div><div style="font-size:11px;color:#64748b">${answerKey.length} cevap okundu</div></div></div>`;
  }catch(e){
    $('keyStatus').innerHTML=`<div class="err"><p>&#9888; ${e.message}</p></div>`;
  }
}

function updateKeyInfo(){
  const n=answerKey.length;
  $('keyInfo').textContent=n>0?`Cevap anahtari: ${n} soru ayarlandi.`:'Cevap anahtari girilmedi — sadece cevaplar okunacak.';
}

// ═══════════ STEP 3: TOPLU YUKLEME ═══════════
const bu=$('batchUpload'), bf=$('batchFiles');
bu.ondragover=e=>{e.preventDefault();bu.classList.add('dragover')};
bu.ondragleave=()=>bu.classList.remove('dragover');
bu.ondrop=e=>{e.preventDefault();bu.classList.remove('dragover');addFiles(e.dataTransfer.files)};
bf.onchange=e=>addFiles(e.target.files);

function addFiles(files){
  for(const f of files){
    if(f.type.startsWith('image/'))batchFiles.push(f);
  }
  renderFileList();
}

function removeFile(i){
  batchFiles.splice(i,1);
  renderFileList();
}

function renderFileList(){
  if(!batchFiles.length){
    $('fileList').classList.add('hidden');
    $('btnBatch').classList.add('hidden');
    return;
  }
  let h=`<div class="file-count">${batchFiles.length} dosya secildi</div><div class="file-list">`;
  batchFiles.forEach((f,i)=>{
    h+=`<div class="file-item"><span class="fn">${f.name}</span><span class="fs">${(f.size/1024).toFixed(0)}KB</span><button onclick="removeFile(${i})" style="background:none;border:none;color:#64748b;cursor:pointer;font-size:14px">&#215;</button></div>`;
  });
  h+='</div>';
  $('fileList').innerHTML=h;
  $('fileList').classList.remove('hidden');
  $('btnBatch').classList.remove('hidden');
}

// ═══════════ BATCH ANALYSIS ═══════════
async function startBatch(){
  if(!batchFiles.length)return;
  const btn=$('btnBatch');
  btn.disabled=true;
  btn.innerHTML='<span class="spinner"></span> Analiz ediliyor...';

  // Progress
  const total=batchFiles.length;
  let h=`<div class="progress-text" id="progText">0 / ${total} isleniyor...</div><div class="progress-bar"><div class="progress-fill" id="progFill" style="width:0%"></div></div>`;
  $('fileList').innerHTML=h;

  const fd=new FormData();
  batchFiles.forEach(f=>fd.append('files',f));
  fd.append('num_questions',$('numQ').value);
  fd.append('num_choices',$('numC').value);
  fd.append('rows_per_col',$('rowsPerCol').value);
  if(answerKey.length)fd.append('answer_key',answerKey.join(','));

  try{
    // Start fake progress
    let prog=0;
    const pi=setInterval(()=>{
      prog=Math.min(prog+Math.random()*15,90);
      $('progFill').style.width=prog+'%';
      $('progText').textContent=`Isleniyor... %${Math.round(prog)}`;
    },500);

    const r=await fetch('/analyze_batch',{method:'POST',body:fd});
    const d=await r.json();
    clearInterval(pi);

    if(d.error)throw new Error(d.error);
    batchResults=d.results||[];
    batchStats=d.stats||{};
    
    $('progFill').style.width='100%';
    $('progText').textContent=`${batchResults.length} / ${total} tamamlandi!`;

    setTimeout(()=>{
      $('step3').classList.add('hidden');
      $('s3').classList.add('done');
      renderResults();
    },600);
  }catch(e){sErr(e.message)}
  finally{btn.disabled=false;btn.innerHTML='&#8857; Toplu Analiz Baslat'}
}

// ═══════════ RENDER RESULTS ═══════════
function renderResults(){
  $('resultsSection').classList.remove('hidden');

  // Stats
  const s=batchStats;
  let sh='';
  if(s.count){
    sh=`<div class="stats-grid">
      <div class="sc"><div class="v" style="color:#a5b4fc">${s.count}</div><div class="l">Ogrenci</div></div>
      <div class="sc"><div class="v" style="color:#34d399">${s.mean}%</div><div class="l">Ortalama</div></div>
      <div class="sc"><div class="v" style="color:#fbbf24">${s.median}%</div><div class="l">Medyan</div></div>
      <div class="sc"><div class="v" style="color:#38bdf8">${s.max}%</div><div class="l">En Yuksek</div></div>
      <div class="sc"><div class="v" style="color:#f87171">${s.min}%</div><div class="l">En Dusuk</div></div>
      <div class="sc"><div class="v" style="color:#94a3b8">${s.stdev}</div><div class="l">Std Sapma</div></div>
      <div class="sc"><div class="v" style="color:#34d399">${s.pass_count}</div><div class="l">Basarili</div></div>
      <div class="sc"><div class="v" style="color:#f87171">${s.fail_count}</div><div class="l">Basarisiz</div></div>
    </div>`;
  }
  $('statsArea').innerHTML=sh;

  // Table
  const hasComp=batchResults.some(r=>r.comparison);
  let th=`<div class="rtable"><div class="rth"><h3>Ogrenci Sonuclari</h3></div><div class="rts"><table><thead><tr>
    <th>#</th><th style="text-align:left">Ad Soyad</th><th>Ogrenci No</th>`;
  if(hasComp)th+='<th>Dogru</th><th>Yanlis</th><th>Bos</th><th>Puan</th>';
  th+='<th>Detay</th></tr></thead><tbody>';

  batchResults.forEach((r,i)=>{
    const si=r.student_info||{};
    const c=r.comparison||{};
    const score=c.score||0;
    const cls=score>=70?'ok':score>=50?'':'ng';
    th+=`<tr>
      <td style="color:#64748b">${i+1}</td>
      <td style="text-align:left;color:#e2e8f0;font-weight:600">${si.name||r.filename||'-'}</td>
      <td style="color:#94a3b8">${si.number||'-'}</td>`;
    if(hasComp){
      th+=`<td class="ok">${c.correct||0}</td>
        <td class="ng">${c.wrong||0}</td>
        <td class="bl">${c.blank||0}</td>
        <td class="${cls}" style="font-weight:700">${score}%</td>`;
    }
    th+=`<td><button class="expand-btn" onclick="toggleDetail(${i})">Goster</button></td></tr>`;

    // Detail row
    th+=`<tr class="detail-row" id="detail${i}"><td colspan="${hasComp?8:4}" class="detail-cell">`;
    const ans=r.answers||[];
    const det=c.details||[];
    if(ans.length){
      th+='<div class="ans-grid">';
      ans.forEach((a,qi)=>{
        const d=det[qi];
        const st=d?d.status:'';
        const cls2=st==='correct'?'ok':st==='wrong'?'ng':'bl';
        th+=`<span class="ans-chip ${cls2}">${a.question}:${a.answer}</span>`;
      });
      th+='</div>';
    }else{
      th+='<span style="color:#64748b">Cevap okunamadi</span>';
    }
    th+='</td></tr>';
  });

  th+='</tbody></table></div></div>';
  $('resultsTable').innerHTML=th;
}

function toggleDetail(i){
  const el=$(`detail${i}`);
  el.classList.toggle('show');
}

// ═══════════ EXPORT ═══════════
function xJSON(){
  const p={results:batchResults,stats:batchStats,answer_key:answerKey};
  dl(new Blob([JSON.stringify(p,null,2)],{type:'application/json'}),'omr_toplu_sonuc.json');
}
async function xXLS(){
  try{
    const r=await fetch('/export/excel',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({results:batchResults,answer_key:answerKey.length?answerKey:null})});
    if(!r.ok)throw new Error('Excel hatasi');
    dl(await r.blob(),'omr_toplu_sonuc.xlsx');
  }catch(e){sErr(e.message)}
}
function dl(b,n){const u=URL.createObjectURL(b),a=document.createElement('a');a.href=u;a.download=n;a.click();URL.revokeObjectURL(u)}

function sErr(m){$('errTxt').textContent='\u26A0 '+m;$('errBox').classList.remove('hidden')}

function resetAll(){
  answerKey=[];batchFiles=[];batchResults=[];batchStats={};
  $('manualKey').value='';$('keyCount').textContent='0 cevap girildi';
  $('keyStatus').classList.add('hidden');
  $('keyUpload').innerHTML='<div class="uz-icon">&#128273;</div><p class="uz-text">Cevap anahtari formunu yukleyin</p><p class="uz-sub">Isaretlenmis optik form goruntusu</p>';
  $('keyUpload').classList.remove('has-file');
  $('batchUpload').innerHTML='<div class="uz-icon">&#128218;</div><p class="uz-text">Tum ogrenci kagitlarini secin veya surukleyin</p><p class="uz-sub">Birden fazla dosya secebilirsiniz</p>';
  $('fileList').classList.add('hidden');
  $('btnBatch').classList.add('hidden');
  $('resultsSection').classList.add('hidden');
  $('errBox').classList.add('hidden');
  $('statsArea').innerHTML='';$('resultsTable').innerHTML='';
  bf.value='';
  goStep(1);
}
