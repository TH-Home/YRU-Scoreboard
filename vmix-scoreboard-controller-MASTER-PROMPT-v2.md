# vMix Scoreboard Controller — Master Prompt v2
## YRU Stadium Football Broadcast Controller

> อัปเดตจาก v1 — ครอบคลุมทุกการเปลี่ยนแปลงที่เกิดขึ้นในโปรเจกต์จนถึงปัจจุบัน

---

## 1. ภาพรวมโปรเจกต์

**Single-file HTML** (ไม่มี backend, ไม่มี framework) — Responsive Web App สไตล์ **Dark Glassmorphism** สำหรับควบคุม vMix ผ่าน HTTP API บนมือถือ/แท็บเล็ตที่สนามกีฬา YRU

รองรับ iPhone, iPad, Android, และเว็บเบราว์เซอร์ทุกชนิด รันผ่าน `python -m http.server 8080` บนเครื่อง vMix (จำเป็นสำหรับ CORS ตอนอ่าน XML state กลับ)

---

## 2. Stack และ Design System

- **Font:** Inter (UI) + JetBrains Mono (ตัวเลข/เวลา/โค้ด) — โหลดจาก Google Fonts
- **Icons:** Google Material Symbols Rounded **เท่านั้น** — ห้ามใช้ emoji เด็ดขาด
  ```css
  @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,300..600,0..1,-25..0&display=block');
  ```
  เรียกใช้ผ่าน `<span class="msr">icon_name</span>` — class variants: `.msr.sm` (16px), `.msr.lg` (28px), `.msr.xl` (36px), `.msr.fill`
- **Color accents:** blue `#3b9eff`, cyan `#00d4ff`, green `#00e676`, amber `#ffb300`, red `#ff3d3d`, purple `#b57bff`
- **Grid:** mobile-first 1 คอลัมน์, ≥768px 2 คอลัมน์, ≥1024px 3 คอลัมน์

---

## 3. โครงสร้างแอพ — 4 แท็บ

ลำดับตายตัว: **Match | Media | Settings | vMix**

### แท็บ Match
- **Scoreboard Display** — แสดงผลจุดเดียว สไตล์ broadcast strip: แถบสีข้างซ้าย(Home)/ขวา(Away) ขยายเต็มความสูงตามจอ, ครึ่งเวลา (1ST-4TH) บนสุด, ตัวเลขคะแนนใหญ่กลาง, เวลา **mm:ss** (00:00) ใต้คะแนน
- **ปุ่ม +/- ปรับคะแนน** อยู่ล่างสุดของการ์ด แบ่ง 2 คอลัมน์ Home/Away มีชื่อทีมกำกับ
- **ปุ่ม GOAL! Macro** — มี confirm dialog ป้องกันกดพลาด

### แท็บ Media
- **PVW/PGM Status Bar** (sticky บนสุด) — แสดงชื่อ source จริงจาก vMix: ฝั่ง PVW กรอบเขียว / ฝั่ง PGM กรอบแดง อัปเดตทุกครั้งที่ fetch XML
- **Input Control Cards** — ดึง input ทุกตัวจาก vMix มาแสดงเป็น card แต่ละใบ ไม่มีฉากดำ (`background:#000`), border แดง=PGM/เขียว=PVW
- **Playlist Queue** — drag & drop, play/next/stop/loop

### แท็บ Settings
- Match Clock + Start Match macro (อยู่การ์ดเดียวกัน)
- Period Settings, Competition Setup, Match Date, Home/Away Team
- Timing Settings, Logo Folder Path (ล่างสุด)

### แท็บ vMix
- Connection, API Log, Manual API sender

---

## 4. Header — กฎที่ต้องคงไว้ทุกครั้ง

```
[icon] YRU Scoreboard — vMix Controller v3.0  |  [Match Mode▼] [Title Type▼] [● STATUS] [↺ Sync]
```

- **Portrait (≤600px):** ซ่อน `.header-text` ทั้งหมด เหลือแค่ icon สีน้ำเงิน + controls — **บรรทัดเดียวเสมอ ไม่ wrap**
- **Landscape (≥601px):** แสดง "YRU Scoreboard — vMix Controller v3.0" กลับมา
- **ลำดับ controls คงที่:** Match Mode → Title Type → Status → Sync (ขวาสุดเสมอ)
- Match Mode: `Thai League` / `General` | Title Type: `Logo` / `Title`
- ค่าเริ่มต้น: **Thai League + Logo**
- **ห้ามมี badge/selector แสดงค่าเหล่านี้ซ้ำที่อื่น** — จุดเดียวคือ Header

```css
@media(max-width:600px){ .header-text{display:none;} .app-header{flex-wrap:nowrap;} }
@media(min-width:601px){ .header-text{display:block;} .app-header{flex-wrap:nowrap;} }
```

---

## 5. Input Control Cards (VIC) — ส่วนใหม่ที่สำคัญ

### Layout แต่ละ card (ไม่มีฉากดำ, background: #000)

```
Row 1: #num  [type badge]                    [PGM/PVW badge]
Row 2: ชื่อ input (ใหญ่กว่า Row 1)           [+PL] (เฉพาะ Video/Audio)
Row 3: ▶▶▶ PLAYING (แสดงเฉพาะเมื่อกำลังเล่น)
Row 4: [Overlay][Cut][Fade][Reset][Audio][Loop][Play/Pause]  ← 7 ปุ่ม
```

### 7 ปุ่มและพฤติกรรม (ลำดับตายตัว)

| # | ปุ่ม | Icon | สี | พฤติกรรม |
|---|---|---|---|---|
| 1 | **Overlay** | `layers` | purple | `OverlayInput1` ซ้อนบน PGM ไม่เปลี่ยน main output |
| 2 | **Cut** | `flash_on` | red | **Cut ก่อนเลย** (คำสั่งแรก) → SetVolume/AudioBusOn/AudioOn ตาม |
| 3 | **Fade** | `gradient` | blue | **Fade 500ms ก่อนเลย** → SetVolume/Audio ตาม |
| 4 | **Reset** | `restart_alt` | amber | Pause + SetPosition=0 (fire-and-forget ทั้งคู่) |
| 5 | **Audio** | `volume_off/up` | cyan | กด 1: เปิด audio-only mode / กด 2: ปิด (toggle) |
| 6 | **Loop** | `repeat/repeat_on` | cyan | LoopOn/LoopOff (toggle, icon และ active class เปลี่ยน) |
| 7 | **Play/Pause** | `play_arrow/pause` | green | เล่น/หยุด — ถ้า Audio mode เปิดอยู่จะเล่นผ่าน Bus A ไม่ตัดภาพ |

### state ที่ track ต่อ input

```js
state.inputAudioOnly = {}  // {title: bool}
state.inputPlaying   = {}  // {title: bool}
state.inputLoop      = {}  // {title: bool}
state.vmixInputs     = []  // [{num, title, type, state}]
state.vmixActive     = null // PGM input number
state.vmixPreview    = null // PVW input number
```

### กฎสำคัญ: renderVicGrid() ต้องอัปเดต PVW/PGM name bar ด้วยทุกครั้ง

```js
document.getElementById('pgmName').textContent = pgmInput?.title || '—';
document.getElementById('pvwName').textContent = pvwInput?.title || '—';
```

---

## 6. vMix API — สองชั้น (สำคัญมาก)

### `vmixFire(func, params)` — fire-and-forget (ไม่ await, ไม่บล็อก)

ใช้กับทุกคำสั่งควบคุมที่ไม่ต้องการผลตอบกลับ:

```js
function vmixFire(func, params={}){
  // สร้าง URL แล้ว fetch() โดย ไม่ await — browser ยิงปืนแล้วไปต่อทันที
  fetch(url, {mode:'no-cors', method:'GET'}).catch(()=>setConnected(false));
}
```

**ใช้ vmixFire() สำหรับ:** Cut, Fade, Play, Pause, SetPosition, SetVolume, AudioBusOn/Off, AudioOn/Off, LoopOn/Off, OverlayInput, PreviewInput

### `vmixApi(func, params)` — async/await (รอผล)

ใช้เฉพาะเมื่อต้องการ sequence ที่ถูกต้อง:

```js
async function vmixApi(func, params={}){
  await fetch(url, {mode:'no-cors', method:'GET'});
}
```

**ใช้ vmixApi() + await สำหรับ:** SetText, SetColor, ChangeCountdown, SetCountdown, StartCountdown, SuspendCountdown, StopCountdown, Fade (ใน macro ที่ต้องรอจังหวะ)

> **กฎ Fade:** ต้องระบุ `Input` (ปลายทาง) ในคำสั่งเดียว เสมอ — ห้ามพึ่ง PreviewInput ก่อนแล้วค่อย Fade ไม่มี Input (ทำให้ delay ผิดปกติ)

### `fetchVmixState()` — อ่าน XML state กลับ

ใช้ `mode:'cors'` — ต้องรัน app ผ่าน local server บนเครื่อง vMix

ทำงานอัตโนมัติทุก 10 วินาที + trigger หลัง Cut/Fade + trigger ตอนเปิดจอมือถือกลับมา (`visibilitychange`)

---

## 7. Field Mapping — vMix SelectedName

มี 4 ไฟล์: `PA-LOGO.gtzip`, `PA-TileName.gtzip`, `SB-LOGO.gtzip`, `SB-TileName.gtzip`

เลือกคู่ตาม Title Type ใน Header (ตลอดเวลา ไม่ cache):
```js
function getSBInput(){ return state.titleType==='logo' ? 'SB-LOGO.gtzip' : 'SB-TileName.gtzip'; }
function getPAInput(){ return state.titleType==='logo' ? 'PA-LOGO.gtzip' : 'PA-TileName.gtzip'; }
```

| Field | SelectedName | PA | SB |
|---|---|---|---|
| ชื่อรายการ | `Title-Match.Text` | ✓ | ✓ |
| โลโก้รายการ | `Logo-Match.Source` | ✓ | ✓ |
| Day of Week | `Day.Text` | ✓ | — |
| วันที่ | `Date.Text` | ✓ | — |
| เดือน | `Month-Match.Text` | ✓ | — |
| ปี | `Year-Match.Text` | ✓ | — |
| Kick off | `Kick-Off.Text` | ✓ | — |
| ชื่อทีมเหย้า/เยือน | `Title-Home/Away.Text` | ✓ | ✓ |
| โลโก้ทีม | `Logo-Home/Away.Source` | ✓ | ✓ |
| สีทีม | `Home/Away-Color.Fill.Color` | ✓ | ✓ |
| Score | `Score-Home/Away.Text` | ❌ ห้าม | ✓ |
| เวลา (Timer) | `Time.Text` | — | ✓ |

---

## 8. Start Match Flow (Thai League)

```
กด Start Match
    → confirm dialog
    ↓ ยืนยัน
[1] Cut → Countdown.mp4 ทันที (vmixFire ไม่รอ)
[2] sendAllToVmixSilent() — sync data เบื้องหลัง ไม่บล็อก
[3] หลัง (cdDur - PRESTART_MS) ms = 5000ms (default):
    → selectPeriod(1) + clockStart() — vMix เริ่มนับ countdown เบื้องหลัง
[4] หลัง (cdDur - SB_FADE_MS + 50) ms = 6800ms (default):
    → Fade 250ms → SB  [ผู้ชมเห็น 00:01 ตอน fade เริ่ม, tick เป็น 00:02 กลาง fade]
[5] Reset Countdown.mp4 → position 0
```

**ค่าคงที่ที่ต้องเข้าใจ:**
- `PRESTART_MS = 2000` — เริ่มนับก่อนวิดีโอจบ 2 วิ (ตรงกับจังหวะ "Kick Off" ในวิดีโอ)
- `SB_FADE_MS = 250` — ระยะเวลา fade เข้า SB
- ทุกค่า duration อ่านจาก Timing Settings แบบ dynamic (ห้าม hardcode) เพื่อรองรับวิดีโอหลายความยาว
- **สูตร fadeAt = cdDur - SB_FADE_MS + 50** ให้ fade window ครอบจังหวะ tick 00:01→00:02 พอดี

### General Mode
PA → **Cut ทันที** → SB + เริ่มจับเวลา + safety-reset Countdown.mp4

---

## 9. GOAL! Macro

```
กด GOAL! → confirm → Cut ทันที → Goal.mp4
หลัง goalDuration (default 13000ms) → Fade 250ms → SB
Reset Goal.mp4 → position 0
```

---

## 10. ระบบนาฬิกา — vMix Built-in Countdown

**ปัญหาที่แก้แล้ว:** ถ้าใช้ `setInterval` บนมือถือ พอปิดจอ timer ค้าง แก้ด้วยให้ vMix นับเอง

**คำสั่งตอนเริ่ม:**
```
ChangeCountdown {Input, Value=hh:mm:ss}  // ตั้งจุดเริ่มต้น
SetCountdown    {Input, Value=hh:mm:ss}  // ตั้งจุดสิ้นสุด
StartCountdown  {Input}                  // เริ่มนับ (vMix นับเองอิสระ)
```

**GT Title Designer:** ต้องตั้งค่า field `Time.Text` ให้เป็น Countdown object แล้วติ๊ก **Reverse mode** (count up)

**Pause:** `SuspendCountdown` / **Reset:** `StopCountdown` + `ChangeCountdown`

**Wake-up sync:** เมื่อเปิดจอมือถือกลับมา (`visibilitychange`) → `fetchVmixState()` → `parseVmixXML()` → `syncClockFromVmixText()` — ตัวเลขในแอพ sync กลับมาตรงกับ vMix อัตโนมัติ

**Period Settings:** `getPeriodStart(p)` / `getPeriodLimit(p)` คำนวณ dynamic จาก `state.periodMins` และ `state.clockMode` (continuous/reset) รองรับ 2-4 periods, 5-90 นาที/period ในสูตรเดียว

---

## 11. State Object หลัก

```js
const state = {
  connected, reconnectTimer,
  titleType: 'logo',    // ค่าเริ่มต้น
  matchMode: 'thai',    // ค่าเริ่มต้น
  periodCount: 2, periodMins: 45, clockMode: 'continuous',
  currentPeriod: 1, clockSeconds: 0, clockRunning: false, clockTimer: null,
  homeScore: 0, awayScore: 0,
  homeName: 'HOME', awayName: 'AWAY',
  homeColor: '#1a3a6b', awayColor: '#8b0000',
  homeLogoData: '', awayLogoData: '',
  mediaItems: [], nowPlaying: null,
  playlist: [], plIndex: -1, plRunning: false, plLoop: false,
  pendingAction: null,
  vmixInputs: [],       // [{num, title, type, state}]
  vmixActive: null,     // PGM input number
  vmixPreview: null,    // PVW input number
  inputAudioOnly: {},   // {title: bool}
  inputPlaying: {},     // {title: bool}
  inputLoop: {},        // {title: bool}
};
```

---

## 12. UI/UX ที่ต้องคงไว้เสมอ

- **แถบสีข้าง card ขยายเต็มความสูงเสมอ** ตามจอจริง ไม่ fix height
- **เวลาแสดงแบบ mm:ss** (00:00) ไม่ใช่ "00'"
- **Confirm dialog ก่อน Start Match และ GOAL! เสมอ** — กดพลาดหน้างานสด แก้ไขยาก
- **ปิดจอมือถือได้หลัง Start Match** — vMix นับเวลาเองอิสระ
- **Input card background: #000** (ไม่ใช่ bg-card เดิม) ให้ตัดกับ border PGM/PVW ชัดขึ้น
- **Input card PGM border แดง + box-shadow แดง, PVW border เขียว + box-shadow เขียว** — คงไว้ทุกครั้ง

---

## 13. จุดที่ต้องระวังเป็นพิเศษ (บทเรียนจากการพัฒนา)

### 13.1 vmixFire vs vmixApi
- **VIC buttons ทั้ง 7 ปุ่ม** ต้องใช้ `vmixFire()` — ห้ามใช้ `vmixApi()` ไม่งั้นจะเกิด delay สะสม
- **Cut ต้องเป็นคำสั่งแรกเสมอ** ใน vicCut() — ยิง Cut ก่อน แล้วค่อย SetVolume/Audio ตามมา ไม่ใช่กลับกัน
- **Fade ต้องระบุ Input ปลายทางเสมอ** — ห้ามพึ่ง PreviewInput ก่อนแล้ว Fade ไม่มี Input

### 13.2 JavaScript ที่เขียนทับ icon ใน DOM
ถ้า JS ใช้ `element.textContent = 'ข้อความ'` กับ element ที่มี `<span class="msr">` อยู่ข้างใน มันจะ**ลบ icon ทิ้งทันที** ต้องใช้:
```js
element.innerHTML = '<span class="msr">icon_name</span> ข้อความ';
```
จุดที่เจอบ่อย: sync button ตอน syncing, connect indicator ตอน setConnected(), playlist play/loop button ตอน toggle

### 13.3 null check ก่อนใช้ getElementById
element ที่เคยมีแล้วถูกลบออกจาก HTML (เช่น `vmixInputsScroll`, `videoList`, `audioList`, `videoBadge`, `audioBadge`) ต้องมี null check ก่อน เช่น:
```js
const scroll = document.getElementById('vmixInputsScroll');
if (scroll) scroll.innerHTML = html;  // ไม่ crash ถ้า element ไม่มี
```

### 13.4 ลำดับ view → แก้ไข เสมอ
ก่อนแก้โค้ดทุกครั้ง ต้อง `view` ไฟล์จาก `/mnt/user-data/outputs/` ก่อน — ไม่สันนิษฐานจากความจำ เพราะไฟล์ถูกแก้หลายรอบจน exact string เปลี่ยนไปได้

### 13.5 ตรวจสอบหลังแก้ทุกครั้ง
```bash
node --check extracted.js            # syntax
grep duplicate ids                   # ไม่มี id ซ้ำ
grep orphaned getElementById()      # ทุก id ที่ JS อ้างถึงต้องมีอยู่ใน HTML หรือ null-safe
```

### 13.6 timing คำนวณ trace ทีละ step
ทุกตัวเลขที่เกี่ยวกับ countdown/fade ต้อง trace จริง (t=0, t=X, t=Y) ก่อนเขียนโค้ด พลาด 100-500ms ทำให้จังหวะภาพดูแปลก

### 13.7 renderVicGrid() ต้องเรียกหลัง parseVmixXML เสมอ
```js
// parseVmixXML ต้องลงท้ายด้วย
renderVicGrid();  // อัปเดต card + PVW/PGM bar พร้อมกัน
```

---

## 14. Timing Settings (ค่า default ปัจจุบัน)

| Setting | Default | หมายเหตุ |
|---|---|---|
| Countdown duration | 7000ms | ความยาววิดีโอ Countdown.mp4 ที่ใช้จริง |
| PRESTART_MS | 2000ms | hardcoded — เริ่มนับก่อนวิดีโอจบ |
| SB_FADE_MS | 250ms | hardcoded — fade เข้า SB |
| Goal! duration | 13000ms | ความยาววิดีโอ Goal.mp4 |
| Goal fade | 250ms | hardcoded — fade กลับ SB |
| vMix polling | 10000ms | auto-refresh XML state |

---

## 15. GT Title Designer — สิ่งที่ต้องตั้งค่าในไฟล์ gtzip

ต้องทำนอกโค้ด (ไม่สามารถแก้จากแอพได้):

**ในไฟล์ `SB-LOGO.gtzip` และ `SB-TileName.gtzip` ทั้งสองไฟล์:**
- เลือก object `Time` (field `Time.Text`) → เปิด Countdown Settings
- ติ๊ก **Reverse mode** (count up ไม่ใช่ countdown)
- Duration ใส่อะไรก็ได้ (โค้ดจะ override ด้วย `ChangeCountdown`/`SetCountdown` ทุกครั้ง)
