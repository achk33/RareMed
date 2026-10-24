#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// WiFi credentials - Replace with your actual network details
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// Backend API endpoint
const char* serverURL = "https://health-center-lac.vercel.app/api/data";

// Timing variables
unsigned long lastUpdate = 0;
const unsigned long updateInterval = 1500; // 1.5 seconds between updates

// Health monitoring variables
struct HealthData {
  int ecg;
  int bpm;
  int systolic;
  int diastolic;
  float temperature;
};

void setup() {
  // Initialize serial communication
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n=== ESP32 Health Monitor Started ===");
  
  // Initialize random seed
  randomSeed(analogRead(0));
  
  // Connect to WiFi
  connectToWiFi();
  
  Serial.println("Health monitoring system ready!");
  Serial.println("Generating simulated sensor data...\n");
}

void loop() {
  // Check if it's time to update
  if (millis() - lastUpdate >= updateInterval) {
    // Generate health data
    HealthData data = generateHealthData();
    
    // Print to Serial Monitor
    printHealthData(data);
    
    // Send to backend
    if (WiFi.status() == WL_CONNECTED) {
      sendHealthData(data);
    } else {
      Serial.println("WiFi disconnected! Attempting to reconnect...");
      connectToWiFi();
    }
    
    lastUpdate = millis();
  }
  
  // Small delay to prevent excessive CPU usage
  delay(100);
}

void connectToWiFi() {
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);
  
  WiFi.begin(ssid, password);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi connected successfully!");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
    Serial.print("Signal strength: ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
  } else {
    Serial.println("\nFailed to connect to WiFi!");
    Serial.println("Check your credentials and try again.");
  }
}

HealthData generateHealthData() {
  HealthData data;
  
  // Generate ECG signal (300-800 range with some variability)
  data.ecg = random(300, 801);
  
  // Generate heart rate with weighted probability for normal range
  int randValue = random(0, 100);
  if (randValue < 80) {
    // 80% chance of normal range (60-100 BPM)
    data.bpm = random(60, 101);
  } else {
    // 20% chance of extreme values (40-59 or 101-180)
    if (randValue < 90) {
      data.bpm = random(40, 60); // Low heart rate
    } else {
      data.bpm = random(101, 181); // High heart rate
    }
  }
  
  // Generate blood pressure (mostly normal with some variation)
  data.systolic = random(100, 141);
  data.diastolic = random(60, 91);
  
  // Ensure diastolic is always lower than systolic
  if (data.diastolic >= data.systolic) {
    data.diastolic = data.systolic - random(20, 40);
    if (data.diastolic < 60) data.diastolic = 60;
  }
  
  // Generate body temperature (36.0-38.0°C with 0.1°C precision)
  data.temperature = random(360, 381) / 10.0;
  
  return data;
}

void printHealthData(const HealthData& data) {
  Serial.println("=== Health Monitor Reading ===");
  Serial.print("ECG Signal: ");
  Serial.println(data.ecg);
  
  Serial.print("Heart Rate: ");
  Serial.print(data.bpm);
  Serial.print(" BPM");
  
  // Add heart rate status indicator
  if (data.bpm >= 60 && data.bpm <= 100) {
    Serial.println(" (Normal)");
  } else if (data.bpm < 60) {
    Serial.println(" (Low - Bradycardia)");
  } else {
    Serial.println(" (High - Tachycardia)");
  }
  
  Serial.print("Blood Pressure: ");
  Serial.print(data.systolic);
  Serial.print("/");
  Serial.print(data.diastolic);
  Serial.println(" mmHg");
  
  Serial.print("Body Temperature: ");
  Serial.print(data.temperature, 1);
  Serial.print("°C");
  
  // Add temperature status indicator
  if (data.temperature >= 36.0 && data.temperature <= 37.2) {
    Serial.println(" (Normal)");
  } else if (data.temperature > 37.2) {
    Serial.println(" (Fever)");
  } else {
    Serial.println(" (Low)");
  }
  
  Serial.println("-----------------------------\n");
}

void sendHealthData(const HealthData& data) {
  HTTPClient http;
  http.begin(serverURL);
  
  // Set headers
  http.addHeader("Content-Type", "application/json");
  http.addHeader("User-Agent", "ESP32-HealthMonitor/1.0");
  
  // Create JSON payload
  StaticJsonDocument<200> jsonDoc;
  jsonDoc["ecg"] = data.ecg;
  jsonDoc["bpm"] = data.bpm;
  jsonDoc["systolic"] = data.systolic;
  jsonDoc["diastolic"] = data.diastolic;
  jsonDoc["temperature"] = round(data.temperature * 10) / 10.0; // Round to 1 decimal
  
  String jsonString;
  serializeJson(jsonDoc, jsonString);
  
  Serial.print("Sending data: ");
  Serial.println(jsonString);
  
  // Send POST request
  int httpResponseCode = http.POST(jsonString);
  
  // Handle response
  if (httpResponseCode > 0) {
    String response = http.getString();
    Serial.print("HTTP Response Code: ");
    Serial.println(httpResponseCode);
    
    if (httpResponseCode == 200) {
      Serial.println("✅ Data sent successfully!");
    } else {
      Serial.print("⚠️ Server responded with code: ");
      Serial.println(httpResponseCode);
    }
    
    if (response.length() > 0) {
      Serial.print("Server response: ");
      Serial.println(response);
    }
  } else {
    Serial.print("❌ HTTP Error: ");
    Serial.println(httpResponseCode);
    Serial.println("Failed to send data to server");
  }
  
  http.end();
  Serial.println();
}