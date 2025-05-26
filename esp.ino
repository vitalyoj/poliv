#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoJson.h>
#include <TimeLib.h>
#include <WiFiUdp.h>

// Настройки WiFi
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// Настройки NTP
const char* ntpServer = "pool.ntp.org";
const long gmtOffset_sec = 0;
const int daylightOffset_sec = 3600;

// Пин подключения насоса
const int pumpPin = 5;
// Пины датчиков (замените на реальные)
const int moisturePin = 34;
const int lightPin = 35;

WebServer server(80);

// Переменные для расписания
String scheduleTime = "";
int scheduleInterval = 0;
bool scheduleActive = false;
time_t nextWatering = 0;
time_t lastWatered = 0;

void setup() {
  Serial.begin(115200);
  pinMode(pumpPin, OUTPUT);
  digitalWrite(pumpPin, LOW);
  
  // Подключение к WiFi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("");
  Serial.println("WiFi connected");
  Serial.println("IP address: ");
  Serial.println(WiFi.localIP());
  
  // Настройка NTP
  configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);
  
  // Настройка маршрутов HTTP сервера
  server.on("/", handleRoot);
  server.on("/moisture", handleMoisture);
  server.on("/light", handleLight);
  server.on("/pump", handlePump);
  server.on("/status", handleStatus);
  server.on("/schedule", handleSchedule);
  
  server.begin();
  Serial.println("HTTP server started");
}

void loop() {
  server.handleClient();
  
  // Проверка расписания
  if (scheduleActive) {
    time_t now;
    time(&now);
    
    if (now >= nextWatering) {
      waterPlant(10); // Полив 10 секунд
      lastWatered = now;
      nextWatering = now + scheduleInterval * 3600;
    }
  }
}

void handleRoot() {
  server.send(200, "text/plain", "Plant Monitoring System");
}

void handleMoisture() {
  int moistureValue = analogRead(moisturePin);
  int moisturePercent = map(moistureValue, 0, 4095, 0, 100);
  
  DynamicJsonDocument doc(128);
  doc["moisture"] = moisturePercent;
  
  String response;
  serializeJson(doc, response);
  server.send(200, "application/json", response);
}

void handleLight() {
  int lightValue = analogRead(lightPin);
  int lux = map(lightValue, 0, 4095, 0, 1000); // Примерное преобразование
  
  DynamicJsonDocument doc(128);
  doc["light"] = lux;
  
  String response;
  serializeJson(doc, response);
  server.send(200, "application/json", response);
}

void handlePump() {
  String state = server.arg("state");
  int pumpTime = server.arg("time").toInt();
  
  DynamicJsonDocument doc(128);
  
  if (state == "on") {
    digitalWrite(pumpPin, HIGH);
    doc["status"] = "pump_on";
  } else if (state == "off") {
    digitalWrite(pumpPin, LOW);
    doc["status"] = "pump_off";
  } else if (state == "time" && pumpTime > 0) {
    waterPlant(pumpTime);
    doc["status"] = "pump_on";
    doc["time"] = pumpTime;
  } else {
    doc["error"] = "Invalid parameters";
  }
  
  String response;
  serializeJson(doc, response);
  server.send(200, "application/json", response);
}

void handleStatus() {
  time_t now;
  time(&now);
  
  char nextWateringStr[20];
  char lastWateredStr[20];
  
  if (nextWatering > 0) {
    struct tm *tm_next = localtime(&nextWatering);
    strftime(nextWateringStr, sizeof(nextWateringStr), "%H:%M %d.%m.%Y", tm_next);
  } else {
    strcpy(nextWateringStr, "N/A");
  }
  
  if (lastWatered > 0) {
    struct tm *tm_last = localtime(&lastWatered);
    strftime(lastWateredStr, sizeof(lastWateringStr), "%H:%M %d.%m.%Y", tm_last);
  } else {
    strcpy(lastWateredStr, "N/A");
  }
  
  DynamicJsonDocument doc(256);
  doc["moisture"] = map(analogRead(moisturePin), 0, 4095, 0, 100);
  doc["light"] = map(analogRead(lightPin), 0, 4095, 0, 1000);
  doc["pump_status"] = digitalRead(pumpPin) == HIGH;
  doc["schedule_active"] = scheduleActive;
  doc["schedule_time"] = scheduleTime;
  doc["next_watering"] = nextWateringStr;
  doc["last_watered"] = lastWateredStr;
  
  String response;
  serializeJson(doc, response);
  server.send(200, "application/json", response);
}

void handleSchedule() {
  String action = server.arg("action");
  
  DynamicJsonDocument doc(128);
  
  if (action == "set") {
    scheduleTime = server.arg("time");
    scheduleInterval = server.arg("interval").toInt();
    
    // Парсим время HH:MM
    int hours = scheduleTime.substring(0, 2).toInt();
    int minutes = scheduleTime.substring(3).toInt();
    
    // Устанавливаем следующее время полива
    time_t now;
    time(&now);
    struct tm *tm = localtime(&now);
    
    tm->tm_hour = hours;
    tm->tm_min = minutes;
    tm->tm_sec = 0;
    
    nextWatering = mktime(tm);
    if (nextWatering < now) {
      nextWatering += 24 * 3600; // Если время уже прошло, переносим на завтра
    }
    
    scheduleActive = true;
    doc["status"] = "schedule_set";
    doc["time"] = scheduleTime;
    doc["interval"] = scheduleInterval;
  } else if (action == "get") {
    doc["active"] = scheduleActive;
    doc["time"] = scheduleTime;
    doc["interval"] = scheduleInterval;
    
    if (scheduleActive) {
      char nextStr[20];
      struct tm *tm_next = localtime(&nextWatering);
      strftime(nextStr, sizeof(nextStr), "%H:%M %d.%m.%Y", tm_next);
      doc["next_watering"] = nextStr;
    }
  } else if (action == "cancel") {
    scheduleActive = false;
    scheduleTime = "";
    scheduleInterval = 0;
    nextWatering = 0;
    doc["status"] = "schedule_canceled";
  } else {
    doc["error"] = "Invalid action";
  }
  
  String response;
  serializeJson(doc, response);
  server.send(200, "application/json", response);
}

void waterPlant(int seconds) {
  digitalWrite(pumpPin, HIGH);
  delay(seconds * 1000);
  digitalWrite(pumpPin, LOW);
  lastWatered = now();
}