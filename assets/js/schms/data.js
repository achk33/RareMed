// SCHMS mock data module
// Patients and measurements (dummy data) simulating backend API responses
// Each measurement entry keeps vitals and timestamp plus derived alerts

const SCHMS_DATA = (function(){
  const patients = [
    {
      id: 'P001',
      nationalId: 'AA123456',
      firstName: 'Fatima',
      lastName: 'El Amrani',
      gender: 'F',
      age: 42,
      phone: '+212600000001',
      address: 'Rabat, Morocco',
  createdAt: '2025-01-12',
  chwId: 'CHW01',
  conditions: ['hypertension'],
  syncStatus: 'synced'
    },
    {
      id: 'P002',
      nationalId: 'BB654321',
      firstName: 'Youssef',
      lastName: 'Benali',
      gender: 'M',
      age: 55,
      phone: '+212600000002',
      address: 'Casablanca, Morocco',
  createdAt: '2025-02-03',
  chwId: 'CHW02',
  conditions: ['diabete'],
  syncStatus: 'pending'
    },
    {
      id: 'P003',
      nationalId: 'CC998877',
      firstName: 'Amina',
      lastName: 'Khadiri',
      gender: 'F',
      age: 33,
      phone: '+212600000003',
      address: 'Marrakesh, Morocco',
  createdAt: '2025-03-22',
  chwId: 'CHW01',
  conditions: ['diabete','hypertension'],
  syncStatus: 'error'
    }
  ];

  const measurements = [
    // patient P001
    { patientId: 'P001', ts: '2025-09-05T08:00:00Z', systolic: 128, diastolic: 82, glucose: 112, spo2: 97, heartRate: 77, temperature: 36.9 },
    { patientId: 'P001', ts: '2025-09-06T08:00:00Z', systolic: 135, diastolic: 89, glucose: 140, spo2: 95, heartRate: 84, temperature: 37.4 },
    { patientId: 'P001', ts: '2025-09-07T08:00:00Z', systolic: 150, diastolic: 95, glucose: 168, spo2: 92, heartRate: 90, temperature: 37.9 },
    // patient P002
    { patientId: 'P002', ts: '2025-09-05T09:00:00Z', systolic: 118, diastolic: 76, glucose: 92, spo2: 98, heartRate: 71, temperature: 36.6 },
    { patientId: 'P002', ts: '2025-09-06T09:00:00Z', systolic: 119, diastolic: 75, glucose: 95, spo2: 97, heartRate: 72, temperature: 36.5 },
    { patientId: 'P002', ts: '2025-09-07T09:00:00Z', systolic: 121, diastolic: 78, glucose: 101, spo2: 97, heartRate: 74, temperature: 36.7 },
    // patient P003
    { patientId: 'P003', ts: '2025-09-05T10:00:00Z', systolic: 140, diastolic: 92, glucose: 180, spo2: 93, heartRate: 88, temperature: 37.2 },
    { patientId: 'P003', ts: '2025-09-06T10:00:00Z', systolic: 142, diastolic: 94, glucose: 190, spo2: 92, heartRate: 90, temperature: 37.5 }
  ];

  // Doctors (dummy)
  const doctors = [
    { id:'D001', name:'Dr. Karim Haddad', specialty:'Cardiologie', active:true },
    { id:'D002', name:'Dr. Salma Idrissi', specialty:'Endocrinologie', active:true }
  ];

  // Community Health Workers (dummy)
  const chws = [
    { id:'CHW01', name:'Latifa Mouline', zone:'Rabat' },
    { id:'CHW02', name:'Hicham Fadili', zone:'Casablanca' }
  ];

  function generateId(prefix){
    return prefix + Math.random().toString(36).substring(2,8).toUpperCase();
  }

  return { patients, measurements, doctors, chws, generateId };
})();

window.SCHMS_DATA = SCHMS_DATA;
