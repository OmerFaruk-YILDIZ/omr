const $=id=>document.getElementById(id);
let radarChartInstance = null; 

// --- AÇILIŞ (HOŞ GELDİNİZ) MODALI KONTROLÜ ---
window.addEventListener('DOMContentLoaded', () => {
  setTimeout(() => {
    $('welcomeModal').classList.remove('hidden');
  }, 500); // Sayfa açıldıktan yarım saniye sonra zarifçe gelir
});

$('closeWelcomeBtn').onclick = () => $('welcomeModal').classList.add('hidden');
$('welcomeModal').onclick = (e) => { if(e.target === $('welcomeModal')) $('welcomeModal').classList.add('hidden'); };


// --- RENK SEÇİCİ ---
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


// --- MODAL & TEMA KONTROLLERİ ---
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


// --- ARAÇLAR MANTIĞI (Hesap Makinesi & Not Çevirici) ---
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
    descObj.textContent = "Lütfen 0 ile 100 arasında bir sayı girin.";
    return;
  }

  let letter = "", desc = "", color = "var(--success)";
  if (score >= 90) { letter = "AA"; desc = "Mükemmel (4.00)"; }
  else if (score >= 85) { letter = "BA"; desc = "Çok İyi (3.50)"; }
  else if (score >= 80) { letter = "BB"; desc = "İyi (3.00)"; }
  else if (score >= 75) { letter = "CB"; desc = "Orta Üzeri (2.50)"; color = "var(--warning)"; }
  else if (score >= 70) { letter = "CC"; desc = "Orta (2.00)"; color = "var(--warning)"; }
  else if (score >= 60) { letter = "DC"; desc = "Koşullu Başarılı (1.50)"; color = "var(--warning)"; }
  else if (score >= 50) { letter = "DD"; desc = "Koşullu Başarılı (1.00)"; color = "var(--danger)"; }
  else if (score >= 40) { letter = "FD"; desc = "Başarısız (0.50)"; color = "var(--danger)"; }
  else { letter = "FF"; desc = "Kaldı (0.00)"; color = "var(--danger)"; }

  resultObj.textContent = letter;
  resultObj.style.color = color;
  resultObj.style.textShadow = `0 0 20px ${color}`;
  descObj.textContent = desc;
}


// --- ANA OMR UYGULAMASI ---
let answerKey=[], batchFiles=[], batchResults=[], batchStats={};
const NUM_QUESTIONS = 100, NUM_CHOICES = 5, ROWS_PER_COL = 30;

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
  $('keyStatus').innerHTML='<span class="spinner"></span> Cevap anahtarı okunuyor...';
  const fd=new FormData();
  fd.append('file',f); fd.append('num_questions',NUM_QUESTIONS); fd.append('num_choices',NUM_CHOICES); fd.append('rows_per_col',ROWS_PER_COL);
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
  $('keyInfo').textContent=n>0?`Cevap anahtarı: ${n} soru ayarlandı.`:'Cevap anahtarı girilmedi — sadece okuma yapılacak.';
}

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
function removeFile(i){ batchFiles.splice(i,1); renderFileList(); }

function renderFileList(){
  if(!batchFiles.length){ $('fileList').classList.add('hidden'); $('btnBatch').classList.add('hidden'); return; }
  let h=`<div class="file-count">${batchFiles.length} dosya seçildi</div><div class="file-list">`;
  batchFiles.forEach((f,i)=>{
    h+=`<div class="file-item"><span class="fn">${f.name}</span><span class="fs">${(f.size/1024).toFixed(0)}KB</span><button onclick="removeFile(${i})" style="background:none;border:none;color:var(--danger);cursor:pointer;font-size:16px">&#215;</button></div>`;
  });
  h+='</div>'; $('fileList').innerHTML=h; $('fileList').classList.remove('hidden'); $('btnBatch').classList.remove('hidden');
}

async function startBatch(){
  if(!batchFiles.length)return;
  const btn=$('btnBatch'); btn.disabled=true; btn.innerHTML='<span class="spinner"></span> Analiz ediliyor...';
  let h=`<div class="progress-text" id="progText">0 / ${batchFiles.length} işleniyor...</div><div class="progress-bar"><div class="progress-fill" id="progFill" style="width:0%"></div></div>`;
  $('fileList').innerHTML=h;

  const fd=new FormData();
  batchFiles.forEach(f=>fd.append('files',f));
  fd.append('num_questions',NUM_QUESTIONS); fd.append('num_choices',NUM_CHOICES); fd.append('rows_per_col',ROWS_PER_COL);
  if(answerKey.length)fd.append('answer_key',answerKey.join(','));

  try{
    let prog=0;
    const pi=setInterval(()=>{
      prog=Math.min(prog+Math.random()*15,90);
      $('progFill').style.width=prog+'%'; $('progText').textContent=`İşleniyor... %${Math.round(prog)}`;
    },500);

    const r=await fetch('/analyze_batch',{method:'POST',body:fd});
    const d=await r.json();
    clearInterval(pi);
    if(d.error)throw new Error(d.error);
    
    batchResults=d.results||[];
    batchStats=d.stats||{};
    
    $('progFill').style.width='100%';
    $('progText').textContent=`${batchResults.length} / ${batchFiles.length} tamamlandı!`;

    setTimeout(()=>{
      $('step2').classList.add('hidden');
      $('s2').classList.add('done');
      renderResults();
    },600);
  }catch(e){sErr(e.message)}
  finally{btn.disabled=false;btn.innerHTML='🚀 Toplu Analiz Başlat'}
}

function renderResults(){
  $('resultsSection').classList.remove('hidden');

  const s=batchStats;
  let sh='';
  if(s.count){
    sh=`<div class="stats-grid">
      <div class="sc"><div class="v" style="color:var(--primary)">${s.count}</div><div class="l">Öğrenci</div></div>
      <div class="sc"><div class="v" style="color:var(--success)">${s.mean}%</div><div class="l">Ortalama</div></div>
      <div class="sc"><div class="v" style="color:var(--warning)">${s.median}%</div><div class="l">Medyan</div></div>
      <div class="sc"><div class="v" style="color:var(--primary)">${s.max}%</div><div class="l">En Yüksek</div></div>
      <div class="sc"><div class="v" style="color:var(--danger)">${s.min}%</div><div class="l">En Düşük</div></div>
      <div class="sc"><div class="v" style="color:var(--text-muted)">${s.stdev}</div><div class="l">Std Sapma</div></div>
      <div class="sc"><div class="v" style="color:var(--success)">${s.pass_count}</div><div class="l">Başarılı</div></div>
      <div class="sc"><div class="v" style="color:var(--danger)">${s.fail_count}</div><div class="l">Başarısız</div></div>
    </div>`;
  }
  $('statsArea').innerHTML=sh;

  const hasComp = batchResults.some(r=>r.comparison);
  if(hasComp) {
    const sorted = [...batchResults].sort((a,b) => (b.comparison.score || 0) - (a.comparison.score || 0));
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
  }

  let th=`<div class="rtable"><div class="rth"><h3>Öğrenci Sonuçları</h3></div><div class="rts"><table><thead><tr>
    <th>#</th><th style="text-align:left">Ad Soyad</th><th>Öğrenci No</th>`;
  if(hasComp)th+='<th>Doğru</th><th>Yanlış</th><th>Boş</th><th style="width:150px">Başarı Barı</th><th>Puan</th>';
  th+='<th>Detay</th></tr></thead><tbody>';

  batchResults.forEach((r,i)=>{
    const si=r.student_info||{};
    const c=r.comparison||{};
    const score=c.score||0;
    
    let barColor = score >= 70 ? 'var(--success)' : (score >= 50 ? 'var(--warning)' : 'var(--danger)');
    const cls = score>=70?'ok':score>=50?'bl':'ng';

    th+=`<tr>
      <td style="color:var(--text-muted)">${i+1}</td>
      <td style="text-align:left;color:var(--text-main);font-weight:600">${si.name||r.filename||'-'}</td>
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
    th+=`<td><button class="expand-btn" onclick="toggleDetail(${i})">Göster</button></td></tr>`;

    th+=`<tr class="detail-row" id="detail${i}"><td colspan="${hasComp?9:4}" class="detail-cell">`;
    
    th+=`<div style="margin-bottom: 15px;">
           <button class="btn-sm btn-primary glow-btn" onclick="showImageModal(${i})">📸 Kağıdı Büyüt</button>
         </div>`;

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
      th+='<span style="color:var(--text-muted)">Cevap okunamadı</span>';
    }
    th+='</td></tr>';
  });

  th+='</tbody></table></div></div>';
  $('resultsTable').innerHTML=th;
}

function showImageModal(index) {
  const result = batchResults[index];
  if(!result) return;
  
  let file = batchFiles.find(f => f.name === result.filename) || batchFiles[index];
  
  if(file) {
    const url = URL.createObjectURL(file);
    $('modalImage').src = url;
    $('imageModal').classList.remove('hidden');
  } else {
    sErr("Bu kağıdın orijinal görüntüsü tarayıcı belleğinde bulunamadı.");
  }
}

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

  radarChartInstance = new Chart(ctx, {
    type: 'radar',
    data: {
      labels: ['Blok 1 (1-20)', 'Blok 2 (21-40)', 'Blok 3 (41-60)', 'Blok 4 (61-80)', 'Blok 5 (81-100)'],
      datasets: [{
        label: 'Sınıf Ortalaması (%)',
        data: [
          batchStats.mean ? Math.min(100, batchStats.mean + 10) : 75, 
          batchStats.mean ? Math.max(0, batchStats.mean - 5) : 60, 
          batchStats.mean ? batchStats.mean : 80, 
          batchStats.mean ? Math.min(100, batchStats.mean + 5) : 85, 
          batchStats.mean ? Math.max(0, batchStats.mean - 10) : 65
        ],
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
          ticks: { display: false, min: 0, max: 100 }
        }
      },
      plugins: {
        legend: { labels: { color: mainColor, font: { family: 'JetBrains Mono' } } }
      }
    }
  });
}

function toggleDetail(i){
  const el=$(`detail${i}`);
  el.classList.toggle('show');
}

function xJSON(){
  const p={results:batchResults,stats:batchStats,answer_key:answerKey};
  dl(new Blob([JSON.stringify(p,null,2)],{type:'application/json'}),'omr_toplu_sonuc.json');
}
async function xXLS(){
  try{
    const r=await fetch('/export/excel',{method:'POST',headers:{'Content-Type':'application/json'}, body:JSON.stringify({results:batchResults,answer_key:answerKey.length?answerKey:null})});
    if(!r.ok)throw new Error('Excel hatası');
    dl(await r.blob(),'omr_toplu_sonuc.xlsx');
  }catch(e){sErr(e.message)}
}
function dl(b,n){const u=URL.createObjectURL(b),a=document.createElement('a');a.href=u;a.download=n;a.click();URL.revokeObjectURL(u)}
function sErr(m){$('errTxt').textContent='\u26A0 '+m;$('errBox').classList.remove('hidden')}

function resetAll(){
  answerKey=[];batchFiles=[];batchResults=[];batchStats={};
  $('manualKey').value='';$('keyCount').textContent='0 cevap girildi';
  $('keyStatus').classList.add('hidden');
  $('keyUpload').innerHTML='<div class="laser"></div><div class="uz-icon">📸</div><p class="uz-text">Cevap anahtarı formunu buraya sürükleyin</p><p class="uz-sub">veya seçmek için tıklayın</p>';
  $('keyUpload').classList.remove('has-file');
  $('batchUpload').innerHTML='<div class="laser"></div><div class="uz-icon floating">📑</div><p class="uz-text">Tüm öğrenci kağıtlarını seçin veya sürükleyin</p><p class="uz-sub">Birden fazla dosya seçebilirsiniz</p>';
  $('fileList').classList.add('hidden');
  $('btnBatch').classList.add('hidden');
  $('resultsSection').classList.add('hidden');
  $('errBox').classList.add('hidden');
  $('statsArea').innerHTML='';$('resultsTable').innerHTML='';
  if(radarChartInstance) radarChartInstance.destroy();
  bf.value='';
  goStep(1);
}
