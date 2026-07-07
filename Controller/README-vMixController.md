# vMixController v4 — YRU Scoreboard Server + Web App

สถาปัตยกรรมใหม่: **โปรแกรมบนคอมพิวเตอร์ (vMixController.exe) = Server + Setup Match** / **เว็บแอพบนมือถือ = Remote Control**

```
┌──────────────────────────────┐          ┌─────────────────────────┐
│  vMixController.exe (Win)    │          │  มือถือ / iPad          │
│  • HTTP Server :8080         │◄────────►│  เปิด http://<ip>:8080  │
│  • Setup Match ทั้งหมด        │  /config │  • คุมสกอร์/นาฬิกา/สื่อ  │
│  • Drag&Drop โลโก้ 3 จุด      │  /logos  │  • แก้ config ด่วนได้    │
│  • ย่อ/ปิด → System Tray     │          │  • ยิงคำสั่งตรงถึง vMix  │
└──────────────┬───────────────┘          └───────────┬─────────────┘
               │ C:\vMixData\{config.json, logos\}    │ HTTP API :8088
               └──────────────────► vMix ◄────────────┘
```

## ไฟล์ในชุดนี้

| ไฟล์ | หน้าที่ |
|---|---|
| `vMixController.py` | ซอร์สโปรแกรม Desktop (Python/tkinter) |
| `build-exe.bat` | สคริปต์ build เป็น `vMixController.exe` (PyInstaller) |
| `index.html` | เว็บแอพ (ฝังใน exe อัตโนมัติ — copy ไป `C:\vMixData` ตอนรันครั้งแรก) |

## Build (ทำครั้งเดียวบนเครื่อง Windows)

1. ติดตั้ง Python 3.10+ (ติ๊ก **Add to PATH**)
2. วาง `vMixController.py`, `build-exe.bat`, `index.html` ไว้โฟลเดอร์เดียวกัน
3. ดับเบิลคลิก `build-exe.bat` → ได้ `dist\vMixController.exe`

## การใช้งาน

1. รัน `vMixController.exe` — สร้าง `C:\vMixData\` (config.json + logos\ + index.html) อัตโนมัติ
2. ด้านบนสุดของโปรแกรม = **Connection**: Server (.local) / Lan IP / WiFi IP พร้อมปุ่ม **Copy**
3. ตั้งค่าแมตช์ในโปรแกรม: Setup Mode → Match Setup → Competition & Teams (ลากโลโก้มาวางได้เลย) → Timing
4. มือถือ (WiFi วงเดียวกัน) เปิด URL ที่ copy มา → Connect → พร้อมใช้งาน
5. กดปิด/ย่อโปรแกรม → เข้า **Tray มุมขวาล่าง** (คลิกขวาที่ icon เพื่อเปิดกลับ/ออกจากโปรแกรม)
6. แนะนำวาง shortcut ของ exe ใน `shell:startup` ให้เปิดอัตโนมัติ

## หน้าที่แบ่งกันอย่างไร (v4)

**ทำบนโปรแกรมคอมพิวเตอร์ (source of truth):**
- Match Mode / Title Type (เว็บแอพเห็นเป็น **badge** อ่านอย่างเดียว)
- วัน/วันที่/Kick Off, จำนวน period (2–4), นาทีต่อรอบ, Clock Mode
- ชื่อ+โลโก้รายการ, ชื่อ+โลโก้+สีทีม Home/Away (**Drag & Drop**)
- Countdown duration / Goal! duration

**เว็บแอพ (มือถือ/ไอแพด) — ส่งคำสั่งเป็นหลัก:**
- Score +/−, GOAL!, Start Match, นาฬิกา, FTB, Sync ไป vMix
- Media / Input Control / Playlist ทั้งหมด
- **แก้ config ด่วนได้** ที่แท็บ Settings — บันทึกกลับไปโปรแกรมอัตโนมัติ (POST /config)

**สิ่งที่ตัดออกจากเว็บแอพ (ลดภาระ):**
- ตัวเลือก Match Mode / Title Type ใน header → badge
- อัปโหลดโลโก้ + preview base64 → preview จาก `/logos/<file>` ของ server แทน
- การ์ด Logo Folder Path → path คงที่ `C:\vMixData\logos`
- `importFromVmix` (~190 บรรทัด) → โหลดจาก `/config` แทน (แม่นกว่า อ่าน XML น้อยลง)

## API ของ Server

| Endpoint | Method | หน้าที่ |
|---|---|---|
| `/` | GET | เว็บแอพ (index.html) |
| `/config` | GET | การตั้งค่าแมตช์ทั้งหมด (JSON) |
| `/config` | POST | อัปเดต config (จากมือถือ) — โปรแกรมเห็นทันที |
| `/logos/<file>` | GET | ไฟล์โลโก้ (สำหรับ preview บนมือถือ) |

## กติกา Timing (คงตาม v4)

- Countdown Mode: Start จับเวลาแข่งจริงที่ **(Countdown duration − 1750ms)** เสมอ
- General Mode: ไม่เกี่ยวกับ Countdown เลย (pre-warm 2000ms ของตัวเอง)

## Checklist ก่อนวันจริง

☐ รัน exe → เปิด URL จากมือถือได้
☐ ลากโลโก้ลงโปรแกรม → มือถือเห็น preview + Sync แล้วโลโก้ขึ้น vMix (SetImage)
☐ แก้ชื่อทีมบนมือถือ → โปรแกรมบนคอมเปลี่ยนตาม (ขึ้น "✓ อัปเดตจากมือถือ")
☐ แก้บนคอม → มือถือเปลี่ยนตามภายใน 15 วิ (หรือทันทีเมื่อเปิดจอ)
☐ ปิดหน้าต่างโปรแกรม → ยังอยู่ใน tray, มือถือยังใช้งานได้
☐ Start Match / GOAL! / FTB / ปิดจอ 1 นาที เวลายังตรง
