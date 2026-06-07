# MCP Server dla OpenBK — Todo

> **Projekt**: `local-home-devices-mcp` (ghcr.io/paulomac1000/local-home-devices-mcp)
> **Wersja**: v1.5.0
> **Cel**: Usprawnić obsługę urządzeń OpenBK7231N/T przez MCP server

---

## Dlaczego to jest potrzebne?

Podczas konfiguracji dwóch urządzeń OpenBK (włącznik sypialnia i listwa LED salon) okazało się, że obecny MCP server (`tasmota-openbk-mcp`) jest **bardzo prymitywny** – potrafi tylko:
- Odkryć urządzenia w sieci
- Włączać/wyłączać przekaźniki (`iot_set_power`)
- Sprawdzać podstawowe info (`iot_get_device_info` – ale bez wersji, MAC-a, flag)

**Do pełnej konfiguracji urządzenia trzeba było używać bezpośrednich zapytań HTTP/GET do API OpenBK**, bo MCP nie potrafi:
- Ustawić flag (flags)
- Ustawić nazw (shortName, fullName)
- Skonfigurować MQTT (host, port, client, group)
- Wywołać HA Discovery
- Skonfigurować pinów (role, channels)

---

## Co trzeba dodać

### 1. 🔧 Device Configuration Tools (KRYTYCZNE)

#### 1.1 `iot_set_flags(ip, flags)`
Ustawia flagi urządzenia OpenBK.

- **API OpenBK**: `GET /cfg_generic?flagN=1&...&setFlags=1`
- **Format flag**: bitfield, np. 134218820 = flagi 2,6,10,27,34
- **Weryfikacja**: `GET /api/info` → `.flags`
- **Przykład**: `iot_set_flags(ip="192.168.0.115", flags=134218820)`

#### 1.2 `iot_set_name(ip, shortName, fullName)`
Ustawia nazwy urządzenia.

- **API OpenBK**: `GET /cfg_name?shortName=X&name=Y`
- **Ograniczenia**: tylko `[a-zA-Z0-9_-]+`, brak spacji
- **Weryfikacja**: `GET /api/info` → `.shortName`
- **Przykład**: `iot_set_name(ip="192.168.0.115", shortName="Light_Bedroom", fullName="Light_Bedroom")`

#### 1.3 `iot_configure_mqtt(ip, host, port, client, group)`
Konfiguruje MQTT.

- **API OpenBK**: `GET /cfg_mqtt_set?host=X&port=Y&client=Z&group=W`
- **Weryfikacja**: `GET /cm?cmnd=status` → `StatusMQT.MqttHost`
- **Przykład**: `iot_configure_mqtt(ip="192.168.0.115", host="192.168.0.101", port=1883, client="BK7231N_XXXXX", group="bekens")`

#### 1.4 `iot_set_gpio(ip, pin, role, channel)`
Ustawia rolę pinu na urządzeniu OpenBK.

- **API OpenBK**: `GET /cfg_pins?pinN_role=X&pinN_channel=Y`
- **Role**: 1=Rel, 3=Btn, 8=WifiLED, 9=WifiLED_n, itd.
- **Weryfikacja**: `GET /api/pins` → `.roles[pin]`
- **Bezpieczeństwo**: ⚠️ Nie zgadywać – wymaga znajomości fizycznego podłączenia
- **Przykład**: `iot_set_gpio(ip="192.168.0.115", pin=6, role=1, channel=1)` (P6 → Rel, kanał 1)

#### 1.5 `iot_start_ha_discovery(ip, prefix)`
Wywołuje Home Assistant Discovery na urządzeniu.

- **API OpenBK**: `GET /ha_discovery?prefix=homeassistant`
- **Wymaga**: Flag 27 ustawionej, MQTT skonfigurowanego
- **Weryfikacja**: `ha_get_state("light.nazwa_urzadzenia_1")` w HA
- **Przykład**: `iot_start_ha_discovery(ip="192.168.0.115", prefix="homeassistant")`

#### 1.6 `iot_reboot(ip)`
Restart urządzenia.

- **API OpenBK**: `GET /reboot`
- **Uwaga**: Już istnieje jako `iot_restart_device` – sprawdzić czy działa z OpenBK

---

### 2. 📋 Enhanced Device Info

#### 2.1 Rozszerzyć `iot_get_device_info` o:
- **Firmware version** (zamiast "Unknown"): `GET /api/info` → `.build`
- **MAC address**: `GET /api/info` → `.mac`
- **Chipset**: `GET /api/info` → `.chipset`
- **Flagi**: `GET /api/info` → `.flags` (LICZBA, nie string)
- **Wszystkie pola z /api/info** w jednym wywołaniu

#### 2.2 `iot_detect_device_type(ip)`
Wykrywa typ firmware'u: Tasmota vs OpenBK vs ESPHome.

- **Metoda**: Sprawdzić endpoint `/api/info` (tylko OpenBK go ma) vs `/cm?cmnd=status` (oba mają)
- **OpenBK**: ma `/api/info`, `/api/pins`
- **Tasmota**: ma status, brak `/api/info`
- **ESPHome**: ma specyficzne endpointy

---

### 3. 🖥️ Web UI Automation (przez Playwright)

Dla złożonych operacji których nie da się zrobić przez REST API:

- `iot_open_webapp(ip)` – otwiera web UI urządzenia
- `iot_run_gpio_finder(ip)` – uruchamia GPIO finder (Web Application)
- `iot_get_screenshot(ip)` – zrzut ekranu web UI (do debugowania)

---

### 4. 🔬 Device Discovery

#### 4.1 Rozszerzyć `iot_discover_devices` o:
- MAC address (obecnie zwraca `null`)
- Firmware version
- Device type (OpenBK vs Tasmota)
- Online status (ping/connection test)

#### 4.2 `iot_scan_network_range(start_ip, end_ip)` - szybsze skanowanie

---

### 5. 📊 Maintainability

- Dodać testy jednostkowe dla OpenBK API calls
- Dodać mocki dla urządzeń OpenBK
- Udokumentować API endpoints w README

---

## REST API Endpoints OpenBK (dokumentacja)

| Endpoint | Metoda | Opis | Przykład |
|---|---|---|---|
| `/api/info` | GET | Podstawowe info (JSON) | `{"flags":"134218820","ip":"192.168.0.115","mac":"4c:a9:19:74:51:d5"}` |
| `/api/pins` | GET | Konfiguracja pinów (JSON) | `{"roles":[0,0,1,...],"channels":[0,0,1,...]}` |
| `/cm?cmnd=status` | GET | Pełny status (JSON) | Wszystkie bloki Status*, StatusMQT, StatusNET |
| `/cfg_name?shortName=X&name=Y` | GET | Ustaw nazwy | `GET /cfg_name?shortName=Test` |
| `/cfg_generic?flag2=1&flag27=1&setFlags=1` | GET | Ustaw flagi | `GET /cfg_generic?flag2=1&flag34=1&setFlags=1` |
| `/cfg_mqtt_set?host=X&port=Y&group=Z` | GET | Konfiguruj MQTT | `GET /cfg_mqtt_set?host=192.168.0.101&group=bekens` |
| `/ha_discovery?prefix=homeassistant` | GET | Wywołaj HA Discovery | `GET /ha_discovery?prefix=homeassistant` |
| `/reboot` | GET | Restart | `GET /reboot` |

---

## Priorytety

| Priorytet | Feature | Uzasadnienie |
|---|---|---|
| 🔴 **P1** | `iot_set_flags`, `iot_set_name`, `iot_configure_mqtt` | Bez tych nie da się skonfigurować urządzenia przez MCP |
| 🔴 **P1** | Rozszerzyć `iot_get_device_info` o MAC, wersję, flagi | "Version: Unknown" i "MAC: null" bezużyteczne |
| 🟡 **P2** | `iot_set_gpio`, `iot_start_ha_discovery` | Umożliwia zdalną konfigurację przez MCP |
| 🟢 **P3** | `iot_detect_device_type`, GPIO finder | Ułatwia debugowanie i automatyzację |
| ⚪ **P4** | Testy, dokumentacja, mocki | Jakość kodu |

---

## Uwagi końcowe

Obecna architektura `local-home-devices-mcp` wymaga Playwright do pełnej konfiguracji, co jest nieefektywne. OpenBK ma REST API, które pozwala na **pełną konfigurację przez GET requesty bez potrzeby Web UI**. Wszystkie niezbędne endpointy zostały zidentyfikowane i udokumentowane powyżej.

Kluczowa różnica między OpenBK a Tasmotą:
- **OpenBK** ma REST API (`/api/info`, `/api/pins`) – łatwe do automatyzacji
- **Tasmota** ma tylko command endpoint (`/cm?cmnd=X`) – inne API
- MCP powinien wykrywać typ i używać odpowiedniego API

Wersja OpenBK firmware na testowanych urządzeniach: 1.17.306 (nowszy włącznik) i 1.18.287 (LED). API jest kompatybilne między wersjami.
