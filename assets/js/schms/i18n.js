// Simple multilingual dictionary (en, fr, ar)
(function(){
  const dict = {
    en: {
      app_title: 'RareMed AI - Clinical Co-Pilot',
      patients: 'Patients',
      alerts: 'Alerts',
      measurements: 'Measurements',
      doctors: 'Doctors',
      add_patient: 'Add Patient',
      add_measurement: 'Add Measurement',
      export_csv: 'Export CSV',
      export_pdf: 'Export PDF',
      vitals: 'Vitals',
      blood_pressure: 'Blood Pressure',
      glucose: 'Glucose',
      spo2: 'SpO₂',
      heart_rate: 'Heart Rate',
      temperature: 'Temperature',
      sync_status: 'Sync Status (offline demo)',
      language: 'Language'
    },
    fr: {
      app_title: 'RareMed AI - Clinical Co-Pilot',
      patients: 'Patients',
      alerts: 'Alertes',
      measurements: 'Mesures',
      doctors: 'Médecins',
      add_patient: 'Ajouter Patient',
      add_measurement: 'Ajouter Mesure',
      export_csv: 'Exporter CSV',
      export_pdf: 'Exporter PDF',
      vitals: 'Signes vitaux',
      blood_pressure: 'Pression Artérielle',
      glucose: 'Glycémie',
      spo2: 'SpO₂',
      heart_rate: 'Fréquence Cardiaque',
      temperature: 'Température',
      sync_status: 'Statut de synchronisation (démo hors-ligne)',
  language: 'Langue',
  condition: 'Maladie',
  zone: 'Zone',
  chw: 'Agent de santé',
  sync_status: 'Statut de synchronisation',
  sync_pending: 'À synchroniser',
  sync_error: 'Erreur',
  sync_synced: 'Synchronisé',
  filter: 'Filtrer',
  export_data: 'Exporter les données',
  chw_dashboard: 'Agent de santé communautaire',
  add_vital: 'Ajouter mesure vitale'
    },
    ar: {
      app_title: 'RareMed AI - Clinical Co-Pilot',
      patients: 'المرضى',
      alerts: 'التنبيهات',
      measurements: 'القياسات',
      doctors: 'الأطباء',
      add_patient: 'إضافة مريض',
      add_measurement: 'إضافة قياس',
      export_csv: 'تصدير CSV',
      export_pdf: 'تصدير PDF',
      vitals: 'المؤشرات الحيوية',
      blood_pressure: 'ضغط الدم',
      glucose: 'السكر',
      spo2: 'الأكسجين',
      heart_rate: 'نبض القلب',
      temperature: 'الحرارة',
      sync_status: 'حالة المزامنة (عرض فقط)',
  language: 'اللغة',
  condition: 'المرض',
  zone: 'المنطقة',
  chw: 'العامل الصحي',
  sync_status: 'حالة المزامنة',
  sync_pending: 'بانتظار المزامنة',
  sync_error: 'خطأ',
  sync_synced: 'متزامن',
  filter: 'تصفية',
  export_data: 'تصدير البيانات',
  chw_dashboard: 'العامل الصحي المجتمعي',
  add_vital: 'إضافة قياس'
    }
  };

  let current = 'fr';

  function t(key){ return (dict[current]&&dict[current][key]) || key; }
  function setLang(l){ if(dict[l]) { current = l; document.dispatchEvent(new CustomEvent('langChanged', { detail: l })); } }

  window.SCHMS_I18N = { t, setLang, get current(){ return current; }, dict };
})();
