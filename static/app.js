const $=id=>document.getElementById(id);
let radarChartInstance = null;

// localStorage anahtarlari
const LS_RESULTS = "omr_batch_results";
const LS_STATS = "omr_batch_stats";
const LS_BLOCKS = "omr_batch_blocks";
const LS_KEY = "omr_answer_key";

// --- ACILIS (HOS GELDINIZ) MODALI ---
window.addEventListener('DOMContentLoaded', () => {
  setTimeout(() => {
    $('welcomeModal').classList.remove('hidden');
  }, 500);

  // Onceki oturumdan kayitli sonuclari yukle
  restoreSession();
});

$('closeWelcomeBtn').onclick = () => $('welcomeModal').classList.add('hidden');
$('welcomeModal').onclick = (e) => { if(e.target === $('welcomeModal')) $('welcomeModal').classList.add('hidden'); };


// --- RENK SECICI ---
const colorPicker = $('primaryColorPicker');
const themeColors = { 'cyberpunk': '#00f0ff', 'matrix': '#00ff41', 'light': '#4f46e5' };

colorPicker.addEventListener('input', (e) => {
  const customColor = e.target.value;
  document.body.style.setProperty('--primary', customColor);
  if (radarChartInstance) renderRadarChart();
});

function resetColor() {
  document.body.style.removeProperty('--primary');
  let currentTheme = 'cyberpunk';
  if(document.body.classList.contains('matrix-mode')) currentTheme = 'matrix';
  if(document.body.classList.contains('light-mode')) currentTheme = 'light';
  colorPicker.value = themeColors[currentTheme];
  if (radarChartInstance) renderRadarChart();
}


// --- MODAL & TEMA ---
$('btnSettings').onclick = () => $('settingsModal').classList.remove('hidden');
$('closeSettingsModal').onclick = () => $('settingsModal').classList.add('hidden');
$('settingsModal').onclick = (e) => { if(e.target === $('settingsModal')) $('settingsModal').classList.add('hidden'); };

$('btnOmrInfo').onclick = () => $('omrModal').classList.remove('hidden');
$('closeOmrModal').onclick = () => $('omrModal').classList.add('hidden');
$('omrModal').onclick = (e) => { if(e.target === $('omrModal')) $('omrModal').classList.add('hidden'); };

$('closeImageModal').onclick = () => $('imageModal').classList.add('hidden');
$('imageModal').onclick = (e) => { if(e.target === $('imageModal')) $('imageModal').classList.add('hidden'); };

$('btnTools').onclick = () => $('toolsModal').classList.remove('hidden');
$('closeToolsModal').onclick = () => $('toolsModal').classList.add('hidden');
$('toolsModal').onclick = (e) => { if(e.target === $('toolsModal')) $('toolsModal').classList.add('hidden'); };


function setTheme(theme) {
  const body = document.body;
  body.classList.remove('matrix-mode', 'light-mode');
  if(theme === 'matrix') body.classList.add('matrix-mode');
  else if(theme === 'light') body.classList.add('light-mode');

  document.body.style.removeProperty('--primary');
  colorPicker.value = themeColors[theme];
  $('settingsModal').classList.add('hidden');
  if (radarChartInstance) renderRadarChart();
}


// --- ARACLAR (Hesap Makinesi & Not Cevirici) ---
function switchTool(toolName) {
  $('tabBtnCalc').classList.remove('active');
  $('tabBtnGrade').classList.remove('active');
  $('toolCalc').classList.add('hidden');
  $('toolGrade').classList.add('hidden');

  if(toolName === 'calc') {
    $('tabBtnCalc').classList.add('active');
    $('toolCalc').classList.remove('hidden');
  } else {
    $('tabBtnGrade').classList.add('active');
    $('toolGrade').classList.remove('hidden');
  }
}

let calcStr = "";
function calcAction(val) {
  const display = $('calcDisplay');
  if(val === 'clear') { calcStr = ""; }
  else if(val === 'del') { calcStr = calcStr.slice(0, -1); }
  else if(val === '=') {
    try {
      if(/^[0-9+\-*/.%() ]+$/.test(calcStr)) {
        calcStr = String(eval(calcStr));
        if(calcStr.includes('.')) calcStr = parseFloat(calcStr).toFixed(2).replace(/\.00$/, '');
      } else {
        calcStr = "Hata";
      }
    } catch(e) { calcStr = "Hata"; }
  }
  else { calcStr += val; }

  display.textContent = calcStr === "" ? "0" : calcStr;
}

function calculateGrade() {
  const score = parseFloat($('gradeInput').value);
  const resultObj = $('gradeResult');
  const descObj = $('gradeDesc');

  if (isNaN(score) || score < 0 || score > 100) {
    resultObj.textContent = "HATA";
    resultObj.style.color = "var(--danger)";
    resultObj.style.textShadow = "0 0 20px var(--danger)";
    descObj.textContent = "Lutfen 0 ile 100 arasinda bir sayi girin.";
    return;
  }

  let letter = "", desc = "", color = "var(--success)";
  if (score >= 90) { letter = "AA"; desc = "Mukemmel (4.00)"; }
  else if (score >= 85) { letter = "BA"; desc = "Cok Iyi (3.50)"; }
  else if (score >= 80) { letter = "BB"; desc = "Iyi (3.00)"; }
  else if (score >= 75) { letter = "CB"; desc = "Orta Uzeri (2.50)"; color = "var(--warning)"; }
  else if (score >= 70) { letter = "CC"; desc = "Orta (2.00)"; color = "var(--warning)"; }
  else if (score >= 60) { letter = "DC"; desc = "Kosullu Basarili (1.50)"; color = "var(--warning)"; }
  else if (score >= 50) { letter = "DD"; desc = "Kosullu Basarili (1.00)"; color = "var(--danger)"; }
  else if (score >= 40) { letter = "FD"; desc = "Basarisiz (0.50)"; color = "var(--danger)"; }
  else { letter = "FF"; desc = "Kaldi (0.00)"; color = "var(--danger)"; }

  resultObj.textContent = letter;
  resultObj.style.color = color;
  resultObj.style.textShadow = `0 0 20px ${color}`;
  descObj.textContent = desc;
}


// --- ANA OMR UYGULAMASI ---
let answerKey=[], batchFiles=[], batchResults=[], batchStats={}, batchBlocks=[];

// NOT: Soru sayisi artik backend'de otomatik tespit ediliyor.
// Frontend bos gonderirse motor form yapisina bakip karar verir.

function goStep(n){
  [1,2].forEach(i=>{
    $(`step${i}`).classList.toggle('hidden',i!==n);
    $(`s${i}`).classList.toggle('active',i===n);
    $(`s${i}`).classList.toggle('done',i<n);
  });
  $('resultsSection').classList.add('hidden');
  if(n===2) updateKeyInfo();
}

function switchTab(t){
  document.querySelectorAll('#step1 .tab').forEach((el,i)=>el.classList.toggle('active',i===(t==='manual'?0:1)));
  $('tabManual').classList.toggle('hidden',t!=='manual');
  $('tabScan').classList.toggle('hidden',t!=='scan');
}

$('manualKey').oninput=()=>{
  const v=$('manualKey').value.trim();
  const keys=v?v.split(',').map(k=>k.trim()).filter(k=>k):[];
  answerKey=keys;
  $('keyCount').textContent=`${keys.length} cevap girildi`;
};

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
  // Soru sayisi parametresi gonderilmiyor -> backend otomatik tespit eder

  try{
    const r=await fetch('/analyze_key',{method:'POST',body:fd});
    const d=await r.json();
    if(d.error)throw new Error(d.error);
    answerKey=d.answer_key||[];
    const preview=answerKey.slice(0,20).join(', ')+(answerKey.length>20?'...':'');
    $('keyStatus').innerHTML=`<div class="key-ok" style="color:var(--success);">&#10003; ${answerKey.length} cevap okundu<div class="key-preview" style="color:var(--text-muted); font-size:12px; margin-top:5px;">${preview}</div></div>`;
    ku.classList.add('has-file');
    ku.innerHTML=`<div style="display:flex;align-items:center;gap:10px"><span style="font-size:24px">&#128273;</span><div><div style="font-size:13px;color:var(--success)">${f.name}</div><div style="font-size:11px;color:var(--text-muted)">${answerKey.length} cevap okundu</div></div></div>`;
  }catch(e){
    $('keyStatus').innerHTML=`<div class="err" style="color:var(--danger);"><p>&#9888; ${e.message}</p></div>`;
  }
}

function updateKeyInfo(){
  const n=answerKey.length;
  $('keyInfo').textContent=n>0?`Cevap anahtari: ${n} soru ayarlandi.`:'Cevap anahtari girilmedi — sadece okuma yapilacak.';
}

const bu=$('batchUpload'), bf=$('batchFiles');
bu.ondragover=e=>{e.preventDefault();bu.classList.add('dragover')};
bu.ondragleave=()=>bu.classList.remove('dragover');
bu.ondrop=e=>{e.preventDefault();bu.classList.remove('dragover');addFiles(e.dataTransfer.files)};
bf.onchange=e=>addFiles(e.target.files);

// DUZELTME: PDF de dahil dosya kontrolu
function isAcceptableFile(f) {
  if (f.type.startsWith('image/')) return true;
  if (f.type === 'application/pdf') return true;
  // MIME hatali gelirse uzantiya bak
  const name = (f.name || '').toLowerCase();
  return name.endsWith('.pdf') || name.endsWith('.jpg') ||
         name.endsWith('.jpeg') || name.endsWith('.png') ||
         name.endsWith('.webp') || name.endsWith('.bmp');
}

function addFiles(files){
  let skipped = 0;
  for(const f of files){
    if(isAcceptableFile(f)) {
      batchFiles.push(f);
    } else {
      skipped++;
    }
  }
  if (skipped > 0) {
    sErr(`${skipped} dosya desteklenmeyen format oldugu icin atlandi (sadece JPG/PNG/PDF kabul edilir).`);
  }
  renderFileList();
}
function removeFile(i){ batchFiles.splice(i,1); renderFileList(); }

function renderFileList(){
  if(!batchFiles.length){ $('fileList').classList.add('hidden'); $('btnBatch').classList.add('hidden'); return; }
  let h=`<div class="file-count">${batchFiles.length} dosya secildi</div><div class="file-list">`;
  batchFiles.forEach((f,i)=>{
    const isPdf = (f.name || '').toLowerCase().endsWith('.pdf');
    const icon = isPdf ? '📄' : '🖼️';
    h+=`<div class="file-item"><span class="fn">${icon} ${f.name}</span><span class="fs">${(f.size/1024).toFixed(0)}KB</span><button onclick="removeFile(${i})" style="background:none;border:none;color:var(--danger);cursor:pointer;font-size:16px">&#215;</button></div>`;
  });
  h+='</div>'; $('fileList').innerHTML=h; $('fileList').classList.remove('hidden'); $('btnBatch').classList.remove('hidden');
}

async function startBatch(){
  if(!batchFiles.length)return;
  const btn=$('btnBatch'); btn.disabled=true; btn.innerHTML='<span class="spinner"></span> Analiz ediliyor...';

  // DUZELTME: fake progress yerine gercek "calistiriyor" gostergesi
  let h=`<div class="progress-text" id="progText"><span class="spinner"></span> ${batchFiles.length} dosya isleniyor, lutfen bekleyin...</div><div class="progress-bar"><div class="progress-fill" id="progFill" style="width:50%;animation:pulse-bar 1.5s ease-in-out infinite"></div></div>`;
  $('fileList').innerHTML=h;

  // CSS animasyonu dinamik ekle
  if(!$('progPulseStyle')){
    const s=document.createElement('style'); s.id='progPulseStyle';
    s.textContent='@keyframes pulse-bar{0%,100%{opacity:.5}50%{opacity:1}}';
    document.head.appendChild(s);
  }

  const fd=new FormData();
  batchFiles.forEach(f=>fd.append('files',f));
  // Soru sayisi / secenek parametreleri gonderilmiyor -> backend otomatik tespit eder
  if(answerKey.length)fd.append('answer_key',answerKey.join(','));

  try{
    const r=await fetch('/analyze_batch',{method:'POST',body:fd});
    const d=await r.json();
    if(d.error)throw new Error(d.error);

    batchResults=d.results||[];
    batchStats=d.stats||{};
    batchBlocks=d.blocks||[];

    $('progFill').style.width='100%';
    $('progText').innerHTML=`✓ ${batchResults.length} form islendi.`;

    // Oturumu kaydet
    saveSession();

    setTimeout(()=>{
      $('step2').classList.add('hidden');
      $('s2').classList.add('done');
      renderResults();
    },400);
  }catch(e){sErr(e.message)}
  finally{btn.disabled=false;btn.innerHTML='🚀 Toplu Analiz Baslat'}
}

function renderResults(){
  $('resultsSection').classList.remove('hidden');

  const s=batchStats;
  let sh='';
  if(s.count){
    sh=`<div class="stats-grid">
      <div class="sc"><div class="v" style="color:var(--primary)">${s.count}</div><div class="l">Ogrenci</div></div>
      <div class="sc"><div class="v" style="color:var(--success)">${s.mean}%</div><div class="l">Ortalama</div></div>
      <div class="sc"><div class="v" style="color:var(--warning)">${s.median}%</div><div class="l">Medyan</div></div>
      <div class="sc"><div class="v" style="color:var(--primary)">${s.max}%</div><div class="l">En Yuksek</div></div>
      <div class="sc"><div class="v" style="color:var(--danger)">${s.min}%</div><div class="l">En Dusuk</div></div>
      <div class="sc"><div class="v" style="color:var(--text-muted)">${s.stdev}</div><div class="l">Std Sapma</div></div>
      <div class="sc"><div class="v" style="color:var(--success)">${s.pass_count}</div><div class="l">Basarili</div></div>
      <div class="sc"><div class="v" style="color:var(--danger)">${s.fail_count}</div><div class="l">Basarisiz</div></div>
    </div>`;
  }
  $('statsArea').innerHTML=sh;

  const hasComp = batchResults.some(r=>r.comparison);
  if(hasComp) {
    const sorted = [...batchResults].sort((a,b) => (b.comparison?.score || 0) - (a.comparison?.score || 0));
    const top3 = sorted.slice(0,3);
    const medals = ['🥇', '🥈', '🥉'];
    let lbHTML = '';
    top3.forEach((r, idx) => {
      lbHTML += `
        <div class="leaderboard-item">
          <div class="lb-rank">${medals[idx]}</div>
          <div class="lb-name">${r.student_info?.name || r.filename || 'Bilinmiyor'}</div>
          <div class="lb-score">%${r.comparison.score}</div>
        </div>`;
    });
    $('leaderboardArea').innerHTML = lbHTML || '<div style="color:var(--text-muted)">Yeterli veri yok.</div>';
    renderRadarChart();
  } else {
    $('leaderboardArea').innerHTML = '<div style="color:var(--text-muted); text-align:center; padding:20px">Cevap anahtari olmadigi icin puanlama yapilmadi.</div>';
    if(radarChartInstance) radarChartInstance.destroy();
  }

  let th=`<div class="rtable"><div class="rth"><h3>Ogrenci Sonuclari</h3></div><div class="rts"><table><thead><tr>
    <th>#</th><th style="text-align:left">Ad Soyad</th><th>Ogrenci No</th>`;
  if(hasComp)th+='<th>Dogru</th><th>Yanlis</th><th>Bos</th><th style="width:150px">Basari Bari</th><th>Puan</th>';
  th+='<th>Detay</th></tr></thead><tbody>';

  batchResults.forEach((r,i)=>{
    const si=r.student_info||{};
    const c=r.comparison||{};
    const score=c.score||0;
    const hasError = !!r.error;

    let barColor = score >= 70 ? 'var(--success)' : (score >= 50 ? 'var(--warning)' : 'var(--danger)');
    const cls = score>=70?'ok':score>=50?'bl':'ng';

    // Hata satirini goze carpan sekilde isaretle
    const rowStyle = hasError ? 'style="background:rgba(255,0,60,0.05)"' : '';
    const errorBadge = hasError ? ' <span style="color:var(--danger);font-size:10px;background:rgba(255,0,60,0.1);padding:2px 6px;border-radius:3px;border:1px solid var(--danger)">⚠ HATA</span>' : '';

    th+=`<tr ${rowStyle}>
      <td style="color:var(--text-muted)">${i+1}</td>
      <td style="text-align:left;color:var(--text-main);font-weight:600">${si.name||r.filename||'-'}${errorBadge}</td>
      <td style="color:var(--text-muted)">${si.number||'-'}</td>`;

    if(hasComp){
      th+=`<td class="ok">${c.correct||0}</td>
        <td class="ng">${c.wrong||0}</td>
        <td class="bl">${c.blank||0}</td>
        <td>
          <div class="health-bar-container">
            <div class="health-bar-fill" style="width: ${score}%; background: ${barColor}; box-shadow: 0 0 10px ${barColor}"></div>
          </div>
        </td>
        <td class="${cls}" style="font-weight:700">${score}%</td>`;
    }
    th+=`<td><button class="expand-btn" onclick="toggleDetail(${i})">Goster</button></td></tr>`;

    th+=`<tr class="detail-row" id="detail${i}"><td colspan="${hasComp?9:4}" class="detail-cell">`;

    if(hasError) {
      th+=`<div style="color:var(--danger);padding:15px;background:rgba(255,0,60,0.08);border-radius:4px;border:1px solid var(--danger)">
        <strong>⚠ Okuma Hatasi:</strong> ${r.error}
        <div style="margin-top:10px;color:var(--text-muted);font-size:12px">Bu ogrenci icin form okunamadi. Lutfen orjinal goruntuyu kontrol edin veya cevaplari elle girin.</div>
      </div>`;
    } else {
      // Overlay ve orijinal goruntu butonlari
      th+=`<div style="margin-bottom: 15px; display: flex; gap: 10px; flex-wrap: wrap;">`;
      if(r.overlay_b64) {
        th+=`<button class="btn-sm btn-primary glow-btn" onclick="showOverlayModal(${i})">🎯 Isaretlemeleri Goster</button>`;
      }
      th+=`<button class="btn-sm btn-secondary" onclick="showOriginalModal(${i})">📸 Orijinal Kagit</button>`;
      if(answerKey.length) {
        th+=`<button class="btn-sm btn-warning glow-btn" onclick="toggleEditMode(${i})" id="editBtn${i}">✏️ Manuel Duzelt</button>`;
      }
      th+=`</div>`;

      const ans=r.answers||[];
      const det=c.details||[];
      if(ans.length){
        // DUZELTME: Cevaplari 7 sutunlu grid halinde goster (form yapisi gibi)
        th+='<div class="answer-grid-7col">';
        const rowsPerCol = 30;
        const cols = Math.ceil(ans.length / rowsPerCol);
        for(let row = 0; row < rowsPerCol; row++) {
          th += '<div class="ans-row">';
          for(let col = 0; col < cols; col++) {
            const qi = col * rowsPerCol + row;
            if(qi < ans.length) {
              const a = ans[qi];
              const d = det[qi];
              const st = d ? d.status : '';
              const cls2 = st==='correct'?'ok':st==='wrong'?'ng':'bl';
              const expected = d?.expected || '';
              const expectedTxt = (expected && expected !== a.answer && st === 'wrong') ? ` (→${expected})` : '';
              th += `<span class="ans-chip ${cls2}" data-qi="${qi}" data-student="${i}" onclick="editAnswer(${i},${qi})" title="${expectedTxt ? 'Beklenen: ' + expected : ''}">${a.question}:<span class="chip-ans">${a.answer}</span>${expectedTxt}</span>`;
            }
          }
          th += '</div>';
        }
        th+='</div>';
      } else {
        th+='<span style="color:var(--text-muted)">Cevap okunamadi</span>';
      }
    }
    th+='</td></tr>';
  });

  th+='</tbody></table></div></div>';
  $('resultsTable').innerHTML=th;
}

// --- YENI: Overlay ve Orijinal gorsel modalleri ---
function showOverlayModal(index) {
  const result = batchResults[index];
  if(!result || !result.overlay_b64) {
    sErr("Overlay goruntusu bulunamadi.");
    return;
  }
  $('modalImage').src = 'data:image/jpeg;base64,' + result.overlay_b64;
  $('imageModal').classList.remove('hidden');
}

function showOriginalModal(index) {
  const result = batchResults[index];
  if(!result) return;

  // Once dosyada ara (sayfa icin file_id kullan)
  const fname = (result.filename || '').replace(/ \(sayfa \d+\)$/, '');
  const file = batchFiles.find(f => f.name === fname);

  if(file && !fname.endsWith('.pdf')) {
    const url = URL.createObjectURL(file);
    $('modalImage').src = url;
    $('imageModal').classList.remove('hidden');
  } else if(result.overlay_b64) {
    // PDF sayfasi ise veya dosya bulunmaziyorsa overlay'i goster
    $('modalImage').src = 'data:image/jpeg;base64,' + result.overlay_b64;
    $('imageModal').classList.remove('hidden');
  } else {
    sErr("Bu kagidin orijinal goruntusu tarayici belleginde bulunamadi (PDF'ten gelmis veya oturum yenilenmis olabilir). Overlay'i deneyin.");
  }
}

// --- YENI: Manuel cevap duzeltme ---
let editMode = {};  // { studentIndex: true/false }

function toggleEditMode(studentIndex) {
  editMode[studentIndex] = !editMode[studentIndex];
  const btn = $(`editBtn${studentIndex}`);
  if(editMode[studentIndex]) {
    btn.innerHTML = '✓ Duzeltmeyi Bitir';
    btn.classList.add('btn-primary');
    btn.classList.remove('btn-warning');
    // Tum chip'lere "editable" ekle
    document.querySelectorAll(`[data-student="${studentIndex}"]`).forEach(chip => {
      chip.classList.add('editable');
    });
  } else {
    btn.innerHTML = '✏️ Manuel Duzelt';
    btn.classList.remove('btn-primary');
    btn.classList.add('btn-warning');
    document.querySelectorAll(`[data-student="${studentIndex}"]`).forEach(chip => {
      chip.classList.remove('editable');
    });
    // Puani yeniden hesapla
    recomputeScore(studentIndex);
  }
}

function editAnswer(studentIndex, qi) {
  if(!editMode[studentIndex]) return;

  const r = batchResults[studentIndex];
  const currentAnswer = r.answers[qi].answer;

  // Secenekleri olustur (A, B, C, D, E, BLANK)
  const choices = ['A', 'B', 'C', 'D', 'E', 'BLANK'];
  const currentIdx = choices.indexOf(currentAnswer);
  const nextIdx = (currentIdx + 1) % choices.length;
  const newAnswer = choices[nextIdx];

  r.answers[qi].answer = newAnswer;

  // Chip'i guncelle
  const chip = document.querySelector(`[data-qi="${qi}"][data-student="${studentIndex}"]`);
  if(chip) {
    const expected = (r.comparison?.details?.[qi]?.expected) || '';
    let newStatus = 'bl';
    if(newAnswer === 'BLANK') newStatus = 'bl';
    else if(expected && newAnswer === expected) newStatus = 'ok';
    else newStatus = 'ng';

    chip.classList.remove('ok', 'ng', 'bl');
    chip.classList.add(newStatus);
    const ansSpan = chip.querySelector('.chip-ans');
    if(ansSpan) ansSpan.textContent = newAnswer;
  }
}

async function recomputeScore(studentIndex) {
  const r = batchResults[studentIndex];
  if(!answerKey.length) return;
  try {
    const resp = await fetch('/recompute', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({result: r, answer_key: answerKey})
    });
    const d = await resp.json();
    if(d.comparison) {
      r.comparison = d.comparison;
      saveSession();
      // Yeniden render
      renderResults();
    }
  } catch(e) {
    sErr("Puan yeniden hesaplanamadi: " + e.message);
  }
}

// --- Oturum korunmasi ---
function saveSession() {
  try {
    // Overlay'ler cok buyuk oldugu icin onlari saklamaya calismayalim (5MB limit)
    const lightResults = batchResults.map(r => {
      const copy = {...r};
      delete copy.overlay_b64;  // overlay'i storage'a kaydetme
      return copy;
    });
    localStorage.setItem(LS_RESULTS, JSON.stringify(lightResults));
    localStorage.setItem(LS_STATS, JSON.stringify(batchStats));
    localStorage.setItem(LS_BLOCKS, JSON.stringify(batchBlocks));
    localStorage.setItem(LS_KEY, JSON.stringify(answerKey));
  } catch(e) {
    console.warn("Oturum kaydedilemedi:", e);
  }
}

function restoreSession() {
  try {
    const savedResults = localStorage.getItem(LS_RESULTS);
    const savedStats = localStorage.getItem(LS_STATS);
    const savedBlocks = localStorage.getItem(LS_BLOCKS);
    const savedKey = localStorage.getItem(LS_KEY);
    if(savedResults && savedStats) {
      batchResults = JSON.parse(savedResults);
      batchStats = JSON.parse(savedStats);
      batchBlocks = savedBlocks ? JSON.parse(savedBlocks) : [];
      answerKey = savedKey ? JSON.parse(savedKey) : [];
      if(batchResults.length) {
        // "Kayitli oturum yuklensin mi?" bildirim gosterme yerine sessizce goster
        const s1=$('step1'), s2=$('step2');
        if(s1) s1.classList.add('hidden');
        if(s2) s2.classList.add('hidden');
        if($('s1')) $('s1').classList.add('done');
        if($('s2')) $('s2').classList.add('done');
        renderResults();

        // Kullaniciya bilgi ver
        setTimeout(()=>{
          const banner = document.createElement('div');
          banner.id = 'sessionBanner';
          banner.style.cssText = 'position:fixed;bottom:20px;right:20px;background:var(--glass-bg);backdrop-filter:blur(20px);border:1px solid var(--primary);border-radius:8px;padding:15px 20px;z-index:500;box-shadow:0 0 20px rgba(0,240,255,0.3);font-family:var(--font-mono);font-size:13px;max-width:300px;animation:slideUp 0.4s';
          banner.innerHTML = `<strong style="color:var(--primary)">💾 Kayitli Oturum</strong><br><span style="color:var(--text-muted);font-size:11px">${batchResults.length} form yuklendi</span><br><button onclick="this.parentElement.remove()" style="margin-top:8px;background:transparent;border:1px solid var(--glass-border);color:var(--text-muted);padding:4px 10px;border-radius:3px;font-size:11px;cursor:pointer">Tamam</button>`;
          document.body.appendChild(banner);
          setTimeout(()=>banner.remove(), 8000);
        }, 600);
      }
    }
  } catch(e) {
    console.warn("Oturum yuklenemedi:", e);
  }
}

function clearSession() {
  localStorage.removeItem(LS_RESULTS);
  localStorage.removeItem(LS_STATS);
  localStorage.removeItem(LS_BLOCKS);
  localStorage.removeItem(LS_KEY);
}

// --- Radar Chart (gercek veri ile) ---
function renderRadarChart() {
  const ctx = document.getElementById('radarChart').getContext('2d');
  if(radarChartInstance) radarChartInstance.destroy();

  let isLight = document.body.classList.contains('light-mode');
  let mainColor = getComputedStyle(document.body).getPropertyValue('--primary').trim() || '#00f0ff';

  let gridColor = 'rgba(255, 255, 255, 0.1)';
  let labelColor = 'rgba(255, 255, 255, 0.7)';

  if(isLight) {
    gridColor = 'rgba(0, 0, 0, 0.1)';
    labelColor = '#64748b';
  }

  // DUZELTME: Gercek blok verileri kullan (fake data yok)
  let labels, data;
  if(batchBlocks && batchBlocks.length > 0) {
    labels = batchBlocks.map(b => b.label);
    data = batchBlocks.map(b => b.avg);
  } else {
    // Hicbir sey gelmediyse 5 esit bloga bol (anahtar yoksa vs)
    labels = ['Blok 1', 'Blok 2', 'Blok 3', 'Blok 4', 'Blok 5'];
    data = [0,0,0,0,0];
  }

  radarChartInstance = new Chart(ctx, {
    type: 'radar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Sinif Ortalamasi (%)',
        data: data,
        backgroundColor: `${mainColor}33`,
        borderColor: mainColor,
        pointBackgroundColor: '#fff',
        pointBorderColor: mainColor,
        borderWidth: 2,
        pointHoverRadius: 6
      }]
    },
    options: {
      responsive: true,
      scales: {
        r: {
          angleLines: { color: gridColor },
          grid: { color: gridColor },
          pointLabels: { color: labelColor, font: { family: 'JetBrains Mono', size: 10 } },
          ticks: { display: false, min: 0, max: 100 },
          suggestedMax: 100,
          suggestedMin: 0
        }
      },
      plugins: {
        legend: { labels: { color: mainColor, font: { family: 'JetBrains Mono' } } },
        tooltip: {
          callbacks: {
            label: function(ctx) { return `${ctx.dataset.label}: %${ctx.parsed.r}`; }
          }
        }
      }
    }
  });
}

function toggleDetail(i){
  const el=$(`detail${i}`);
  el.classList.toggle('show');
}

function xJSON(){
  const p={results:batchResults,stats:batchStats,blocks:batchBlocks,answer_key:answerKey};
  // Export'tan overlay'leri cikar (cok buyuk)
  const lightP = {...p, results: p.results.map(r => { const c={...r}; delete c.overlay_b64; return c; })};
  dl(new Blob([JSON.stringify(lightP,null,2)],{type:'application/json'}),'omr_toplu_sonuc.json');
}
async function xXLS(){
  try{
    // Excel'e overlay gondermeye gerek yok, kucult
    const lightResults = batchResults.map(r => { const c={...r}; delete c.overlay_b64; return c; });
    const r=await fetch('/export/excel',{method:'POST',headers:{'Content-Type':'application/json'}, body:JSON.stringify({results:lightResults,answer_key:answerKey.length?answerKey:null})});
    if(!r.ok)throw new Error('Excel hatasi');
    dl(await r.blob(),'omr_toplu_sonuc.xlsx');
  }catch(e){sErr(e.message)}
}
function dl(b,n){const u=URL.createObjectURL(b),a=document.createElement('a');a.href=u;a.download=n;a.click();URL.revokeObjectURL(u)}
function sErr(m){$('errTxt').textContent='\u26A0 '+m;$('errBox').classList.remove('hidden'); setTimeout(()=>$('errBox').classList.add('hidden'), 8000);}

function resetAll(){
  if(batchResults.length && !confirm('Tum kayitli sonuclar silinecek. Devam edilsin mi?')) return;

  answerKey=[];batchFiles=[];batchResults=[];batchStats={};batchBlocks=[];editMode={};
  clearSession();

  $('manualKey').value='';$('keyCount').textContent='0 cevap girildi';
  $('keyStatus').classList.add('hidden');
  $('keyUpload').innerHTML='<div class="laser"></div><div class="uz-icon">📸</div><p class="uz-text">Cevap anahtari formunu buraya surukleyin</p><p class="uz-sub">veya secmek icin tiklayin</p>';
  $('keyUpload').classList.remove('has-file');
  $('batchUpload').innerHTML='<div class="laser"></div><div class="uz-icon floating">📑</div><p class="uz-text">Tum ogrenci kagitlarini secin veya surukleyin</p><p class="uz-sub">JPG, PNG veya PDF kabul edilir</p>';
  $('fileList').classList.add('hidden');
  $('btnBatch').classList.add('hidden');
  $('resultsSection').classList.add('hidden');
  $('errBox').classList.add('hidden');
  $('statsArea').innerHTML='';$('resultsTable').innerHTML='';
  if(radarChartInstance) radarChartInstance.destroy();
  bf.value='';
  goStep(1);
}
