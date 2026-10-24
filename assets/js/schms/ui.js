// UI logic for SCHMS pages
(function(){
  function byId(id){ return document.getElementById(id); }
  function formatBP(m){ return m.systolic + '/' + m.diastolic; }
  function levelColor(level){
    switch(level){
      case 'high': return 'badge bg-danger';
      case 'low': return 'badge bg-warning text-dark';
      default: return 'badge bg-success';
    }
  }

  async function renderKPIs(){
    const el = byId('kpiPatients');
    if(!el) return;
    const stats = await SCHMS_API.fetchStats();
    byId('kpiPatients').innerText = stats.patients;
    byId('kpiAlerts').innerText = stats.alerts;
    byId('kpiMeasurements').innerText = stats.measurements;
    byId('kpiDoctors').innerText = stats.doctors;
    const syncBox = byId('syncStatusBox');
    if(syncBox){
      syncBox.innerHTML = `<span class='me-2 badge bg-warning text-dark'>${stats.sync.pending} ${SCHMS_I18N.t('sync_pending')}</span>
      <span class='me-2 badge bg-danger'>${stats.sync.error} ${SCHMS_I18N.t('sync_error')}</span>`;
    }
  }

  async function renderHomeVitalsChart(){
    const canvas = document.getElementById('homeChartVitals');
    if(!canvas || !window.Chart) return;
    const patients = await SCHMS_API.fetchPatients();
    // aggregate latest glucose per patient
    const dataPoints = [];
    for(const p of patients){
      const ms = await SCHMS_API.fetchMeasurements(p.id);
      if(ms.length){ dataPoints.push({ name: p.firstName, glucose: ms[ms.length-1].glucose }); }
    }
    new Chart(canvas.getContext('2d'), { type:'bar', data:{ labels: dataPoints.map(d=>d.name), datasets:[{ label:'Glucose', data: dataPoints.map(d=>d.glucose), backgroundColor:'#0d6efd' }] }, options:{ responsive:true, plugins:{ legend:{ display:false } } } });
  }

  async function renderAlertsWidget(){
    const list = byId('alertsWidget');
    if(!list) return;
    const patients = await SCHMS_API.fetchPatients();
    const all = [];
    for(const p of patients){
      const ms = await SCHMS_API.fetchMeasurements(p.id);
      const last = ms[ms.length-1];
      if(last){
        for(const a of last.alerts){ all.push({ patient:p, alert:a, ts:last.ts }); }
      }
    }
    all.sort((a,b)=> (a.alert.level===b.alert.level?0: a.alert.level==='high'? -1:1));
    if(!all.length){ list.innerHTML = '<li><span>Aucune alerte</span><span class="badge bg-success">OK</span></li>'; return; }
    list.innerHTML = all.slice(0,8).map(x=>`<li><span>${x.patient.firstName} ${x.patient.lastName}</span><span class='${levelColor(x.alert.level)}'>${x.alert.type}</span></li>`).join('');
  }

  async function renderPatientList(){
    const tableBody = byId('patientTableBody');
    if(!tableBody) return;
    const pts = await SCHMS_API.fetchPatients();
    const filterCondition = document.querySelector('[data-filter-condition]')?.value || '';
    const filterZone = document.querySelector('[data-filter-zone]')?.value || '';
    const filterSync = document.querySelector('[data-filter-sync]')?.value || '';
    const filterChw = document.querySelector('[data-filter-chw]')?.value || '';
    const filtered = pts.filter(p=>{
      return (!filterCondition || (p.conditions||[]).includes(filterCondition))
        && (!filterZone || p.address.toLowerCase().includes(filterZone.toLowerCase()))
        && (!filterSync || p.syncStatus===filterSync)
        && (!filterChw || p.chwId===filterChw);
    });
    tableBody.innerHTML = filtered.map(p=>`<tr data-id="${p.id}">
      <td>${p.id}</td>
      <td><a href="patient-detail.html?id=${p.id}">${p.firstName} ${p.lastName}</a></td>
      <td>${p.gender}</td>
      <td>${p.age}</td>
      <td>${p.phone}</td>
      <td>${p.address}</td>
      <td>${p.createdAt}</td>
      <td><button class="btn btn-sm btn-outline-primary" data-export="${p.id}">CSV</button></td>
    </tr>`).join('');
  }

  async function renderPatientDetail(){
    const container = byId('patientDetail');
    if(!container) return;
    const params = new URLSearchParams(window.location.search);
    const id = params.get('id');
    const patients = await SCHMS_API.fetchPatients();
    const patient = patients.find(p=>p.id===id);
    if(!patient){ container.innerHTML = '<div class="alert alert-warning">Patient not found</div>'; return; }
    const measurements = await SCHMS_API.fetchMeasurements(id);

    const latest = measurements[measurements.length-1];
    container.innerHTML = `<div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
      <h3 class="mb-0">${patient.firstName} ${patient.lastName}</h3>
      <button type="button" class="btn btn-primary" id="analyzeWithGraphRag" ${measurements.length ? '' : 'disabled'}>
        Analyser avec GraphRAG (Gemini)
      </button>
    </div>
      <div id="graphRagResult" class="mb-3" aria-live="polite"></div>
      <p>${patient.gender==='M'?'Male':'Female'} | ${patient.age} ans | ${patient.address}</p>
      <div class="row g-2">${latest ? ['systolic','diastolic','glucose','spo2','heartRate','temperature'].map(k=>{
        return `<div class='col-6 col-md-4'><div class='p-2 border rounded small'>${k}: <strong>${latest[k]}</strong></div></div>`;
      }).join('') : ''}</div>
      <hr/>
      <h5>Historique</h5>
      <table class='table table-sm'>
        <thead><tr><th>Date</th><th>TA</th><th>Glycémie</th><th>SpO₂</th><th>FC</th><th>T°</th><th>Alertes</th></tr></thead>
        <tbody>${measurements.map(m=>`<tr>
          <td>${new Date(m.ts).toLocaleString()}</td>
          <td>${formatBP(m)}</td>
          <td>${m.glucose}</td>
          <td>${m.spo2}</td>
          <td>${m.heartRate}</td>
          <td>${m.temperature}</td>
          <td>${m.alerts.map(a=>`<span class='${levelColor(a.level)} me-1'>${a.type}</span>`).join('')}</td>
        </tr>`).join('')}</tbody>
      </table>
      <canvas id='chartGlucose' height='120'></canvas>
      <canvas id='chartBP' height='120' class='mt-3'></canvas>
    `;

    const analyzeButton = byId('analyzeWithGraphRag');
    if(analyzeButton){
      analyzeButton.addEventListener('click', ()=> analyzePatientWithGraphRag(patient, measurements));
    }

    // create charts
    if(window.Chart){
      const glucoseCtx = document.getElementById('chartGlucose').getContext('2d');
      new Chart(glucoseCtx, {
        type: 'line',
        data: {
          labels: measurements.map(m => new Date(m.ts).toLocaleDateString()),
          datasets: [
            {
              label: 'Glucose',
              data: measurements.map(m => m.glucose),
              borderColor: '#0d6efd',
              tension: 0.2,
              fill: false
            }
          ]
        },
        options: { responsive: true, plugins: { legend: { display: true } } }
      });
      const bpCtx = document.getElementById('chartBP').getContext('2d');
      new Chart(bpCtx, {
        type: 'bar',
        data: {
          labels: measurements.map(m => new Date(m.ts).toLocaleDateString()),
            datasets: [
              {
                label: 'Systolic',
                data: measurements.map(m => m.systolic),
                backgroundColor: '#dc3545'
              },
              {
                label: 'Diastolic',
                data: measurements.map(m => m.diastolic),
                backgroundColor: '#ffc107'
              }
            ]
        },
        options: { responsive: true, plugins: { legend: { position: 'bottom' } } }
      });
    }
  }

  async function analyzePatientWithGraphRag(patient, measurements){
    const button = byId('analyzeWithGraphRag');
    const resultContainer = byId('graphRagResult');
    if(!button || !resultContainer || !measurements.length) return;

    button.disabled = true;
    resultContainer.replaceChildren();
    const loading = document.createElement('div');
    loading.className = 'alert alert-info';
    loading.textContent = 'Analyse GraphRAG en cours…';
    resultContainer.appendChild(loading);

    const clinicalContext = {
      age: patient.age,
      sex: patient.gender,
      conditions: patient.conditions || [],
      latest_vitals: measurements[measurements.length - 1],
      measurement_history: measurements
    };

    try{
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: 'gemini-1.5-pro',
          messages: [{
            role: 'user',
            content: `Analyse ces données cliniques avec le Knowledge Graph autorisé. Les mesures et antécédents ne sont pas des diagnostics; ne déduis que ce qui est étayé par le graphe.\n${JSON.stringify(clinicalContext)}`
          }]
        })
      });
      const data = await response.json();
      if(!response.ok){
        throw new Error(data.error || 'Échec de l’analyse GraphRAG.');
      }
      renderGraphRagResult(resultContainer, data);
    }catch(error){
      const alert = document.createElement('div');
      alert.className = 'alert alert-danger';
      alert.textContent = `Impossible de terminer l’analyse : ${error.message}`;
      resultContainer.replaceChildren(alert);
    }finally{
      button.disabled = false;
    }
  }

  function renderGraphRagResult(container, result){
    container.replaceChildren();
    const card = document.createElement('section');
    card.className = 'card border-primary';
    const body = document.createElement('div');
    body.className = 'card-body';

    const title = document.createElement('h4');
    title.className = 'card-title';
    title.textContent = 'Résultat RareMed AI';
    body.appendChild(title);

    const status = document.createElement('p');
    status.className = 'mb-3';
    status.textContent = `Statut : ${result.status || 'Inconnu'}`;
    body.appendChild(status);

    const hypotheses = document.createElement('h5');
    hypotheses.textContent = 'Hypothèses';
    body.appendChild(hypotheses);

    if(!Array.isArray(result.hypotheses) || !result.hypotheses.length){
      const none = document.createElement('p');
      none.textContent = 'Aucune hypothèse étayée par le graphe.';
      body.appendChild(none);
    }else{
      const list = document.createElement('ul');
      list.className = 'list-group mb-3';
      result.hypotheses.forEach(hypothesis=>{
        const item = document.createElement('li');
        item.className = 'list-group-item';
        const name = document.createElement('strong');
        name.textContent = hypothesis.name || hypothesis.disease || 'Hypothèse';
        item.appendChild(name);

        const confidence = hypothesis.confidence ?? hypothesis.confidence_score;
        const score = document.createElement('p');
        score.className = 'mb-1 mt-2';
        score.textContent = `Score de confiance : ${confidence === undefined ? 'Non fourni' : confidence}`;
        item.appendChild(score);

        const evidence = document.createElement('p');
        evidence.className = 'mb-0';
        evidence.textContent = `Evidence Path : ${formatEvidencePath(hypothesis.evidence_path)}`;
        item.appendChild(evidence);
        list.appendChild(item);
      });
      body.appendChild(list);
    }

    if(typeof result.question === 'string' && result.question){
      const question = document.createElement('p');
      question.className = 'alert alert-warning mb-0';
      question.textContent = `Question discriminante : ${result.question}`;
      body.appendChild(question);
    }

    card.appendChild(body);
    container.appendChild(card);
  }

  function formatEvidencePath(path){
    if(Array.isArray(path)){
      return path.map(item=>typeof item === 'string' ? item : JSON.stringify(item)).join(' → ');
    }
    if(path && typeof path === 'object') return JSON.stringify(path);
    return typeof path === 'string' ? path : 'Non fourni';
  }

  function setupAddPatientForm(){
    const form = byId('addPatientForm');
    if(!form) return;
    form.addEventListener('submit', async e=>{
      e.preventDefault();
      const data = Object.fromEntries(new FormData(form).entries());
      data.age = parseInt(data.age||'0',10);
      await SCHMS_API.addPatient(data);
      form.reset();
      alert('Patient ajouté');
      location.href = 'patients.html';
    });
  }

  function setupAddMeasurementForm(){
    const form = byId('addMeasurementForm');
    if(!form) return;
    form.addEventListener('submit', async e=>{
      e.preventDefault();
      const data = Object.fromEntries(new FormData(form).entries());
      const patientId = data.patientId; delete data.patientId;
      Object.keys(data).forEach(k=> data[k] = parseFloat(data[k]));
      const res = await SCHMS_API.addMeasurement(patientId, data);
      alert('Mesure ajoutée. Alertes: ' + res.alerts.map(a=>a.type).join(','));
      form.reset();
    });
  }

  function setupLangSwitcher(){
    const sel = document.querySelector('[data-lang-switcher]');
    if(!sel) return;
    sel.addEventListener('change', e=> SCHMS_I18N.setLang(e.target.value));
    document.addEventListener('langChanged', ()=> applyTranslations());
  }

  function applyTranslations(){
    document.querySelectorAll('[data-i18n]').forEach(el=>{
      el.textContent = SCHMS_I18N.t(el.getAttribute('data-i18n'));
    });
  }

  async function populatePatientSelect(){
    const sel = byId('measurementPatient');
    if(!sel) return;
    const pts = await SCHMS_API.fetchPatients();
    sel.innerHTML = pts.map(p=>`<option value='${p.id}'>${p.firstName} ${p.lastName}</option>`).join('');
  }

  // Export CSV utility (basic)
  function exportTableToCSV(tableSelector, filename){
    const rows = Array.from(document.querySelectorAll(tableSelector + ' tr'));
    const csv = rows.map(r=> Array.from(r.children).map(c=> '"'+c.innerText.replace(/"/g,'""')+'"').join(',')).join('\n');
    const blob = new Blob([csv], { type:'text/csv;charset=utf-8;' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = filename; a.click();
  }

  function setupExports(){
    document.addEventListener('click', e=>{
      if(e.target.matches('[data-export-global]')){
        exportTableToCSV('#patientListTable', 'patients.csv');
      }
      if(e.target.matches('[data-export]')){
        const id = e.target.getAttribute('data-export');
        exportTableToCSV(`#patientListTable tr[data-id='${id}']`, `patient-${id}.csv`);
      }
    });
  }

  document.addEventListener('DOMContentLoaded', ()=>{
    renderKPIs();
    renderPatientList();
    renderPatientDetail();
  renderHomeVitalsChart();
  renderAlertsWidget();
    setupAddPatientForm();
    setupAddMeasurementForm();
    setupLangSwitcher();
    populatePatientSelect();
    applyTranslations();
    setupExports();
    document.querySelectorAll('[data-filter-condition],[data-filter-zone],[data-filter-sync],[data-filter-chw]').forEach(el=>{
      el.addEventListener('change', ()=> renderPatientList());
      el.addEventListener('keyup', ()=> renderPatientList());
    });
  });
})();
