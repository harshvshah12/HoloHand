/*
 ============================================================================
  PROJECT HOLOHAND — ESP32-CAM HIGH-PERFORMANCE AR STREAMING FIRMWARE
 ============================================================================
  Board Target:    AI-Thinker ESP32-CAM (OV2640 Sensor)
  Architecture:    ESP32 Dual-Core Xtensa LX6 + FreeRTOS + PSRAM
  Transport:       Low-overhead MJPEG-over-HTTP Stream Server
  Endpoints:       /stream   (Live multipart MJPEG video stream)
                   /capture  (Single high-res JPEG snapshot)
                   /status   (JSON diagnostic telemetry & RSSI)
                   /flash    (Hardware illumination control)
 ============================================================================
  WIRING GUIDE FOR USB-TO-TTL PROGRAMMER (FTDI / CH340 / CP2102):
  
    PROGRAMMER PIN   ->   ESP32-CAM PIN
    -----------------------------------
    5V               ->   5V  (MUST provide >= 5V 2A peak current)
    GND              ->   GND (Common Ground)
    TXD              ->   U0R (GPIO 3 - Receive)
    RXD              ->   U0T (GPIO 1 - Transmit)
    
  FLASHING PROCEDURE:
    1. Connect GPIO 0 to GND before powering on (enters bootloader mode).
    2. In Arduino IDE:
       - Board: "AI Thinker ESP32-CAM"
       - CPU Frequency: 240MHz (WiFi/BT)
       - Flash Frequency: 80MHz
       - Flash Mode: QIO
       - Partition Scheme: "Huge APP (3MB No OTA/1MB SPIFFS)"
       - PSRAM: "Enabled"
       - Upload Speed: 115200 or 921600
    3. Click Upload. When "Connecting..." appears, press ESP32-CAM RST button.
    4. After upload finishes, DISCONNECT GPIO 0 FROM GND.
    5. Press RST button once more to boot into operational streaming mode.
    6. Open Serial Monitor at 115200 baud to read the assigned IP address.
 ============================================================================
*/

#include "esp_camera.h"
#include <WiFi.h>
#include "esp_timer.h"
#include "img_converters.h"
#include "fb_gfx.h"
#include "soc/soc.h"             // Brownout detector control
#include "soc/rtc_cntl_reg.h"    // Brownout detector control
#include "esp_http_server.h"

// ============================================================================
// 1. NETWORK & HARDWARE CONFIGURATION
// ============================================================================
const char* WIFI_SSID     = "3245";
const char* WIFI_PASSWORD = "soldering";

// Camera Resolution Options:
//   FRAMESIZE_QVGA (320x240)  - Lowest latency (~30-40 ms, 30+ FPS)
//   FRAMESIZE_HVGA (480x320)  - Excellent balance of speed and fidelity
//   FRAMESIZE_VGA  (640x480)  - Crisp landmark precision, recommended (~20-25 FPS)
#define DEFAULT_FRAME_SIZE  FRAMESIZE_VGA

// JPEG Compression Quality (10 - 63):
// Lower number = higher image quality, larger packet size.
// 12 is optimal for OV2640 with PSRAM.
#define JPEG_QUALITY        12

// Onboard Hardware Pins for AI-Thinker ESP32-CAM
#define FLASH_LED_PIN       4    // High-power White LED (Active HIGH)
#define STATUS_LED_PIN      33   // Small Red Indicator on rear (Active LOW)

// ============================================================================
// 2. CAMERA PIN DEFINITIONS (AI-Thinker Board Pinout)
// ============================================================================
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27

#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// ============================================================================
// 3. GLOBAL CONSTANTS & HTTP BOUNDARIES
// ============================================================================
#define PART_BOUNDARY "123456789000000000000987654321"
static const char* _STREAM_CONTENT_TYPE = "multipart/x-mixed-replace;boundary=" PART_BOUNDARY;
static const char* _STREAM_BOUNDARY = "\r\n--" PART_BOUNDARY "\r\n";
static const char* _STREAM_PART = "Content-Type: image/jpeg\r\nContent-Length: %u\r\nX-Timestamp: %d.%06d\r\n\r\n";

httpd_handle_t stream_httpd = NULL;
bool flash_led_state = false;
unsigned long last_wifi_check = 0;
const unsigned long WIFI_RECONNECT_INTERVAL = 10000; // 10s

// ============================================================================
// 4. HTTP REQUEST HANDLERS
// ============================================================================

/**
 * High-throughput, low-overhead MJPEG video stream handler.
 * Fetches frames from OV2640 FIFO and flushes them as multipart HTTP stream.
 */
static esp_err_t stream_handler(httpd_req_t *req) {
  camera_fb_t * fb = NULL;
  esp_err_t res = ESP_OK;
  size_t _jpg_buf_len = 0;
  uint8_t * _jpg_buf = NULL;
  char * part_buf[128];

  res = httpd_resp_set_type(req, _STREAM_CONTENT_TYPE);
  if (res != ESP_OK) {
    return res;
  }

  // Prevent browser/client proxy caching
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  httpd_resp_set_hdr(req, "Cache-Control", "no-cache, no-store, must-revalidate");
  httpd_resp_set_hdr(req, "Pragma", "no-cache");

  while (true) {
    fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("[HOLOHAND][WARN] Camera frame buffer acquisition failed!");
      res = ESP_FAIL;
    } else {
      _jpg_buf_len = fb->len;
      _jpg_buf = fb->buf;
    }

    if (res == ESP_OK) {
      res = httpd_resp_send_chunk(req, _STREAM_BOUNDARY, strlen(_STREAM_BOUNDARY));
    }
    if (res == ESP_OK) {
      size_t hlen = snprintf((char *)part_buf, 128, _STREAM_PART, _jpg_buf_len, (int)fb->timestamp.tv_sec, (int)fb->timestamp.tv_usec);
      res = httpd_resp_send_chunk(req, (const char *)part_buf, hlen);
    }
    if (res == ESP_OK) {
      res = httpd_resp_send_chunk(req, (const char *)_jpg_buf, _jpg_buf_len);
    }

    if (fb) {
      esp_camera_fb_return(fb);
      fb = NULL;
      _jpg_buf = NULL;
    } else if (res != ESP_OK) {
      break;
    }

    if (res != ESP_OK) {
      // Client disconnected or socket error
      break;
    }

    // Pacing yield to prevent watchdog trigger on dual-core CPU
    taskYIELD();
  }

  return res;
}

/**
 * Capture a single still JPEG frame at current resolution.
 */
static esp_err_t capture_handler(httpd_req_t *req) {
  camera_fb_t * fb = NULL;
  esp_err_t res = ESP_OK;

  fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("[HOLOHAND][ERROR] Camera capture failed");
    httpd_resp_send_500(req);
    return ESP_FAIL;
  }

  httpd_resp_set_type(req, "image/jpeg");
  httpd_resp_set_hdr(req, "Content-Disposition", "inline; filename=capture.jpg");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");

  res = httpd_resp_send(req, (const char *)fb->buf, fb->len);
  esp_camera_fb_return(fb);
  return res;
}

/**
 * Telemetry endpoint providing live board health, RSSI, and memory status in JSON.
 */
static esp_err_t status_handler(httpd_req_t *req) {
  char json_response[256];
  sensor_t * s = esp_camera_sensor_get();
  int resolution = s ? s->status.framesize : -1;
  int quality    = s ? s->status.quality : -1;

  snprintf(json_response, sizeof(json_response),
    "{\"status\":\"online\",\"board\":\"AI-Thinker ESP32-CAM\",\"ip\":\"%s\","
    "\"rssi\":%d,\"psram\":%s,\"free_heap\":%u,\"free_psram\":%u,"
    "\"framesize\":%d,\"quality\":%d,\"flash_led\":%s}",
    WiFi.localIP().toString().c_str(),
    WiFi.RSSI(),
    psramFound() ? "true" : "false",
    ESP.getFreeHeap(),
    psramFound() ? ESP.getFreePsram() : 0,
    resolution,
    quality,
    flash_led_state ? "true" : "false"
  );

  httpd_resp_set_type(req, "application/json");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  return httpd_resp_send(req, json_response, strlen(json_response));
}

/**
 * Hardware flash LED control endpoint (/flash?state=1 or /flash?state=0).
 */
static esp_err_t flash_handler(httpd_req_t *req) {
  char buf[32];
  if (httpd_req_get_url_query_str(req, buf, sizeof(buf)) == ESP_OK) {
    char param[16];
    if (httpd_query_key_value(buf, "state", param, sizeof(param)) == ESP_OK) {
      if (strcmp(param, "1") == 0 || strcmp(param, "true") == 0) {
        flash_led_state = true;
        digitalWrite(FLASH_LED_PIN, HIGH);
        Serial.println("[HOLOHAND] Flash LED turned ON");
      } else {
        flash_led_state = false;
        digitalWrite(FLASH_LED_PIN, LOW);
        Serial.println("[HOLOHAND] Flash LED turned OFF");
      }
    }
  }

  char res_buf[64];
  snprintf(res_buf, sizeof(res_buf), "{\"flash_led\":%s}", flash_led_state ? "true" : "false");
  httpd_resp_set_type(req, "application/json");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  return httpd_resp_send(req, res_buf, strlen(res_buf));
}

// ============================================================================
// 5. HTTP SERVER INITIALIZATION
// ============================================================================
void startCameraServer() {
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.server_port = 80;
  config.ctrl_port = 32768;
  config.max_open_sockets = 7;
  config.lru_purge_enable = true;

  httpd_uri_t stream_uri = {
    .uri       = "/stream",
    .method    = HTTP_GET,
    .handler   = stream_handler,
    .user_ctx  = NULL
  };

  httpd_uri_t root_uri = {
    .uri       = "/",
    .method    = HTTP_GET,
    .handler   = stream_handler, // Fallback root to stream
    .user_ctx  = NULL
  };

  httpd_uri_t capture_uri = {
    .uri       = "/capture",
    .method    = HTTP_GET,
    .handler   = capture_handler,
    .user_ctx  = NULL
  };

  httpd_uri_t status_uri = {
    .uri       = "/status",
    .method    = HTTP_GET,
    .handler   = status_handler,
    .user_ctx  = NULL
  };

  httpd_uri_t flash_uri = {
    .uri       = "/flash",
    .method    = HTTP_GET,
    .handler   = flash_handler,
    .user_ctx  = NULL
  };

  Serial.printf("[HOLOHAND] Launching HTTP Server on port %d...\n", config.server_port);
  if (httpd_start(&stream_httpd, &config) == ESP_OK) {
    httpd_register_uri_handler(stream_httpd, &stream_uri);
    httpd_register_uri_handler(stream_httpd, &root_uri);
    httpd_register_uri_handler(stream_httpd, &capture_uri);
    httpd_register_uri_handler(stream_httpd, &status_uri);
    httpd_register_uri_handler(stream_httpd, &flash_uri);
    Serial.println("[HOLOHAND] All HTTP endpoints registered successfully.");
  } else {
    Serial.println("[HOLOHAND][ERROR] Failed to start HTTP server!");
  }
}

// ============================================================================
// 6. HARDWARE INITIALIZATION (SETUP)
// ============================================================================
void setup() {
  // Disable brownout detector to prevent sudden resets during Wi-Fi transmission bursts
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);

  Serial.begin(115200);
  Serial.setDebugOutput(false);
  delay(500);

  Serial.println("\n\n=======================================================");
  Serial.println("  PROJECT HOLOHAND — ESP32-CAM AR STREAMING FIRMWARE");
  Serial.println("=======================================================");

  // Initialize LEDs
  pinMode(FLASH_LED_PIN, OUTPUT);
  pinMode(STATUS_LED_PIN, OUTPUT);
  digitalWrite(FLASH_LED_PIN, LOW);   // Ensure flash is OFF (prevents sensor saturation)
  digitalWrite(STATUS_LED_PIN, HIGH); // Off (active low)

  // Configure Camera Parameters
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0       = Y2_GPIO_NUM;
  config.pin_d1       = Y3_GPIO_NUM;
  config.pin_d2       = Y4_GPIO_NUM;
  config.pin_d3       = Y5_GPIO_NUM;
  config.pin_d4       = Y6_GPIO_NUM;
  config.pin_d5       = Y7_GPIO_NUM;
  config.pin_d6       = Y8_GPIO_NUM;
  config.pin_d7       = Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk     = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.grab_mode    = CAMERA_GRAB_LATEST; // Always grab latest frame to minimize backlog latency

  // Check PSRAM Availability
  if (psramFound()) {
    Serial.printf("[HOLOHAND] PSRAM Detected! Total: %d KB | Free: %d KB\n",
                  ESP.getPsramSize() / 1024, ESP.getFreePsram() / 1024);
    config.frame_size   = DEFAULT_FRAME_SIZE;
    config.jpeg_quality = JPEG_QUALITY;
    config.fb_count     = 2; // Double buffering with PSRAM
    config.fb_location  = CAMERA_FB_IN_PSRAM;
  } else {
    Serial.println("[HOLOHAND][WARN] No PSRAM detected. Falling back to internal SRAM buffers.");
    config.frame_size   = FRAMESIZE_QVGA;
    config.jpeg_quality = 15;
    config.fb_count     = 1;
    config.fb_location  = CAMERA_FB_IN_DRAM;
  }

  // Camera Initialization
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("[HOLOHAND][CRITICAL] Camera init failed with error 0x%x\n", err);
    // Rapidly blink status LED to signify camera hardware fault
    while (true) {
      digitalWrite(STATUS_LED_PIN, LOW);
      delay(100);
      digitalWrite(STATUS_LED_PIN, HIGH);
      delay(100);
    }
  }
  Serial.println("[HOLOHAND] Camera hardware initialized successfully.");

  // Fine-tune Sensor Parameters for Gesture Tracking
  sensor_t * s = esp_camera_sensor_get();
  if (s) {
    s->set_brightness(s, 1);     // -2 to 2
    s->set_contrast(s, 1);       // -2 to 2
    s->set_saturation(s, 0);     // -2 to 2
    s->set_special_effect(s, 0); // 0 = No effect
    s->set_whitebal(s, 1);       // 1 = Auto white balance
    s->set_awb_gain(s, 1);       // 1 = Enable AWB gain
    s->set_wb_mode(s, 0);        // 0 = Auto
    s->set_exposure_ctrl(s, 1);  // 1 = Auto exposure
    s->set_aec2(s, 0);           // 0 = Auto exposure sensor dsp
    s->set_ae_level(s, 0);       // -2 to 2
    s->set_gain_ctrl(s, 1);      // 1 = Auto gain
    s->set_agc_gain(s, 0);       // 0 to 30
    s->set_gainceiling(s, (gainceiling_t)0); // GAINCEILING_2X
    s->set_bpc(s, 0);            // Black pixel correction
    s->set_wpc(s, 1);            // White pixel correction
    s->set_raw_gma(s, 1);        // Gamma correction
    s->set_lenc(s, 1);           // Lens correction
    s->set_hmirror(s, 0);        // 0 = Normal, 1 = Horizontal mirror
    s->set_vflip(s, 0);          // 0 = Normal, 1 = Vertical flip
    s->set_dcw(s, 1);            // Downsize EN
  }

  // ============================================================================
  // CONNECT TO WI-FI (2.4 GHz ONLY)
  // ============================================================================
  Serial.printf("[HOLOHAND] Connecting to Wi-Fi SSID: '%s'...\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false); // Disable WiFi power save mode for maximum packet throughput
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long start_attempt = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start_attempt < 15000) {
    digitalWrite(STATUS_LED_PIN, LOW); // Blink indicator while searching
    delay(200);
    digitalWrite(STATUS_LED_PIN, HIGH);
    delay(200);
    Serial.print(".");
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[HOLOHAND] >>> WI-FI CONNECTED! <<<");
    Serial.printf("[HOLOHAND] IP Address assigned: http://%s\n", WiFi.localIP().toString().c_str());
    Serial.printf("[HOLOHAND] MJPEG Stream URL:    http://%s/stream\n", WiFi.localIP().toString().c_str());
    Serial.printf("[HOLOHAND] System Status URL:   http://%s/status\n", WiFi.localIP().toString().c_str());
    Serial.printf("[HOLOHAND] Wi-Fi Signal (RSSI): %d dBm\n", WiFi.RSSI());

    // Solid LED indication of ready state
    digitalWrite(STATUS_LED_PIN, LOW);

    // Start HTTP server
    startCameraServer();
  } else {
    Serial.println("\n[HOLOHAND][CRITICAL] Failed to connect to Wi-Fi within timeout!");
    Serial.println("[HOLOHAND] Check that your router/hotspot broadcasts 2.4 GHz and AP client isolation is disabled.");
  }
}

// ============================================================================
// 7. BACKGROUND HEALTH MONITOR & AUTO-RECONNECT (LOOP)
// ============================================================================
void loop() {
  unsigned long now = millis();

  // Monitor Wi-Fi connection and automatically reconnect if dropped
  if (now - last_wifi_check >= WIFI_RECONNECT_INTERVAL) {
    last_wifi_check = now;

    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("[HOLOHAND][WARN] Wi-Fi link lost. Attempting reconnection...");
      digitalWrite(STATUS_LED_PIN, HIGH); // Turn off solid indicator
      WiFi.disconnect();
      WiFi.reconnect();
    } else {
      // Periodic heartbeat pulse
      static int heartbeat = 0;
      if (++heartbeat % 6 == 0) { // Every ~60 seconds
        Serial.printf("[HOLOHAND][HEARTBEAT] Streaming active | IP: http://%s/stream | RSSI: %d dBm | Free Heap: %u\n",
                      WiFi.localIP().toString().c_str(), WiFi.RSSI(), ESP.getFreeHeap());
      }
    }
  }

  // Yield to FreeRTOS background scheduler
  delay(100);
}
