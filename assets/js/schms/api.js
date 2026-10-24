// SCHMS mock API layer - replace later with real fetch calls
(function(){
  const delay = (ms) => new Promise(r => setTimeout(r, ms));
  const clone = (o) => JSON.parse(JSON.stringify(o));

  function evaluateAlerts(m){
    const alerts = [];
    if(m.systolic >= 140 || m.diastolic >= 90) alerts.push({ type: 'blood_pressure', level: 'high', message: 'Hypertension suspectée' });
    if(m.glucose >= 160) alerts.push({ type: 'glucose', level: 'high', message: 'Glycémie élevée' });
    if(m.spo2 < 94) alerts.push({ type: 'spo2', level: 'low', message: 'SpO₂ basse' });
    if(m.heartRate > 100) alerts.push({ type: 'heart_rate', level: 'high', message: 'Tachycardie' });
    if(m.temperature >= 38) alerts.push({ type: 'temperature', level: 'high', message: 'Fièvre' });
    return alerts;
  }

  async function fetchPatients(){
    await delay(120);
    return clone(SCHMS_DATA.patients);
  }

  async function fetchMeasurements(patientId){
    await delay(120);
    return clone(SCHMS_DATA.measurements.filter(m=>m.patientId===patientId)).map(m=>({ ...m, alerts: evaluateAlerts(m) }));
  }

  async function fetchAllMeasurements(){
    await delay(100);
    return clone(SCHMS_DATA.measurements).map(m=>({ ...m, alerts: evaluateAlerts(m) }));
  }

  async function addPatient(payload){
    const id = SCHMS_DATA.generateId('P');
    const patient = { id, createdAt: new Date().toISOString().substring(0,10), ...payload };
    SCHMS_DATA.patients.push(patient);
    return clone(patient);
  }

  async function addMeasurement(patientId, payload){
    const record = { patientId, ts: new Date().toISOString(), ...payload };
    SCHMS_DATA.measurements.push(record);
    return { ...record, alerts: evaluateAlerts(record) };
  }

  async function fetchStats(){
    const pts = SCHMS_DATA.patients.length;
    const m = SCHMS_DATA.measurements.length;
    let alerts = 0;
    for(const x of SCHMS_DATA.measurements){ alerts += evaluateAlerts(x).length; }
    const doctorsActive = SCHMS_DATA.doctors.filter(d=>d.active).length;
    const syncPending = SCHMS_DATA.patients.filter(p=>p.syncStatus==='pending').length;
    const syncError = SCHMS_DATA.patients.filter(p=>p.syncStatus==='error').length;
    return { patients: pts, measurements: m, alerts, doctors: doctorsActive, sync: { pending: syncPending, error: syncError } };
  }

  window.SCHMS_API = { fetchPatients, fetchMeasurements, fetchAllMeasurements, addPatient, addMeasurement, fetchStats };
})();
