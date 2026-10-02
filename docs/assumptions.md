# Assumptions tracker (TRD 8-bo'lim: "Taxminlar va tashqi bog'liqliklar")

TRD'ning o'z 8-bo'limi besh assumption'ni (ASM-001..005) ro'yxatlaydi, har
biri "agar noto'g'ri chiqsa" degan aniq oqibat bilan — bu `docs/open-
decisions.md`/`docs/risk-register.md` bilan bir xil turkumdagi tracker,
faqat bu safar Product Owner qarorini emas, loyihaning o'z **taxminlarini**
haqiqiy kod bazasi holatiga qarshi tekshiradi. Bu fayl traceability
auditda uchinchi marta o'tkazilgan to'liq TRD-ID sweep'da ASM-002/003/004
hech qayerda (kod ham, CLAUDE.md ham) ID bo'yicha keltirilmagani
aniqlangandan keyin yozildi — ASM-001 CLAUDE.md'ning o'z boshida ("Jamoa"
bo'limi) allaqachon muhokama qilingan edi.

Status "taxmin haligacha to'g'rimi" (holds) yoki "taxmin noto'g'ri chiqdi,
lekin oqibat qanday bo'ldi" (falsified — bilan bog'liq oqibat real yoki
yo'q) sifatida baholanadi, kalendar emas — `open-decisions.md`ning o'z
metodologiyasi.

| ID | Taxmin | Agar noto'g'ri bo'lsa | Holat |
|----|--------|------------------------|-------|
| ASM-001 | Jamoa 4.5–5 FTE hajmida va barqaror | Muddat proporsional uzayadi | **Boshidanoq noto'g'ri, ataylab qayta talqin qilingan** — CLAUDE.md'ning o'z kirish qismi ("Jamoa" bo'limi) buni ID bo'yicha keltirmasdan, lekin aniq hal qiladi: haqiqiy jamoa yo'q, loyihani to'liq AI coding agent quradi, Product Owner Hikmatullo To'rayev. TRD'ning kalendar sprint rejalashtirishi (17/18-bo'lim) shu sababli "rejalashtirish uchun emas, faqat ish tartibi ketma-ketligi" sifatida o'qiladi — bashorat qilingan oqibat (muddat uzayishi) ma'nosiz, chunki hech qanday kalendar muddat kuzatilmayapti. |
| ASM-002 | Tanlangan AI provider mintaqadan mavjud va barqaror | Fallback provider va qo'shimcha integratsiya ishi | **Holds — va bashorat qilingan oqibat allaqachon, ataylab, oldindan qurilgan.** ADR-008/ADR-009 uchta providerni (OpenAI/Gemini/Claude) bitta gateway ortida qurdi, `ai_preference_service`ning opt-in fallback mexanizmi (standart o'chirilgan, ADR-009) allaqachon mavjud — bitta provider mintaqadan yo'qolib qolsa, bu aynan TRD bashorat qilgan "fallback provider" javobi. Haqiqiy sinov (biror provayder haqiqatda mavjud bo'lmay qolishi) hali kuzatilmagan — bu sandbox real provider API'lariga umuman kira olmaydi (ADR-008/009'ning halol chegarasi) — lekin infratuzilma tayyor. |
| ASM-003 | Birinchi konnektor OAuth va sandbox muhitiga ega | S7 uzayadi; boshqa konnektor tanlanadi | **TRD'ning o'z taxmini noto'g'ri chiqdi, lekin bashorat qilingan oqibat sodir bo'lmadi.** OD-002 orqali tanlangan birinchi connector — Telegram — OAuth ISHLATMAYDI (Bot API oddiy, uzoq muddatli bot token bilan ishlaydi, OAuth 2.0 emas). TRD 8-bo'limi "OAuth va sandbox muhiti" deb taxmin qilgan, bu taxmin haqiqatga to'g'ri kelmadi. Lekin bashorat qilingan oqibat — "S7 uzayadi yoki boshqa connector tanlanadi" — YUZ BERMADI: bot-token modeli OAuth'dan SODDAROQ chiqdi (redirect/consent-screen/token-refresh oqimi shart emas), shuning uchun connector S7'gacha kutmasdan, shu sessiyaning o'zida qurildi va ishladi (`infrastructure/telegram_client.py`/`telegram_relay.py`). Bu holat OD-002'ning ADR-007 yozuvida allaqachon tasvirlangan, faqat ASM-003 ID'siga bog'lanmagan edi. |
| ASM-004 | MVP bitta tashkilot uchun (SaaS emas) | Billing, self-serve onboarding va tenant provisioning qo'shiladi | **Boshidanoq, ochiq ravishda noto'g'ri deb belgilangan — OD-001'ning o'zi buni bekor qiladi.** Product Owner OD-001'da aniq qildi: DODA boshidanoq to'liq multi-tenant (Customer→Workspace→Membership) arxitektura sifatida quriladi, "hozircha shaxsiy foydalanish uchun, lekin kelajakda boshqa foydalanuvchilarga taqdim eta olish (sotish) qobiliyati bilan". Demak ASM-004 TRD yozilgan paytdagi taxmindan farqli, loyihaning haqiqiy boshlang'ich nuqtasi edi. Bashorat qilingan oqibatning ikkala qismi ham hali **qurilmagan, ataylab**: (1) tenant provisioning — Customer/Workspace yaratish operator/test tooling orqali ochiq (`create_customer_with_owner`), lekin **self-serve public signup** TRD 2.3'ning o'zi "v1 uchun OUT OF SCOPE" deb belgilagan; (2) **billing** — hech qanday to'lov/obuna mexanizmi yo'q, chunki hozircha real pulli mijoz yo'q. Ikkalasi ham OD-001'ning "keyinchalik" qismiga tegishli, hozirgi ish doirasidan tashqarida — bu yangi bo'shliq emas, OD-001'ning o'z ziddiyatsiz davomi. |
| ASM-005 | Hosting mintaqasi managed PostgreSQL va object storage taklif qiladi | Self-managed infra — SRE yuklamasi ikki baravar oshadi | **Holds bugungi kunda, lekin kelajakdagi VPS yo'nalishi uchun ochiq savol qoladi.** OD-005'ning joriy production sirti — Render.com — managed Postgres taqdim etadi (`render.yaml`), demak taxmin bugun to'g'ri. Lekin OD-005'ning kelajakdagi, hozircha talab qilinmagan VPS/Hetzner yo'nalishi (`docker-compose.prod.yml`, `deploy/`) **self-managed** Postgres'ni nazarda tutadi (`infra/postgres-init/01-create-app-role.sql` orqali qo'lda bootstrap qilinadigan ikkita rol) — agar loyiha shu yo'nalishga o'tsa, ASM-005'ning bashorat qilingan oqibati (SRE yuklamasi ikki baravar) HAQIQIY bo'lib qoladi, chunki bugungi kod bazasida hech qanday avtomatlashtirilgan backup/monitoring/patching mavjud emas (NFR-DUR-001'ning "PITR" qismi ham xuddi shu sababdan OD-005'ga bog'liq, `backend/scripts/backup_restore_drill.py`ning o'z halol chegarasiga qarang). Bu VPS qaroriga birga keladigan, hali materiallashmagan xarajat — ochiq, kuzatilishi kerak bo'lgan narsa, hozircha muammo emas. |

## Ownership

`docs/open-decisions.md` bilan bir xil: bu tracker kuzatish uchun, harakat
uchun emas. ASM-004 kabi allaqachon Product Owner tomonidan qarama-qarshi
hal qilingan taxminlar bu yerda "falsified" deb qoladi — TRD matni
o'zgartirilmaydi (u tarixiy hujjat), faqat haqiqiy holat shu yerda aniq
ko'rsatiladi. Yangi taxmin haqiqatga to'g'ri kelmasa (masalan ASM-002ning
haqiqiy provider outage bilan birinchi marta sinovi), shu qatorni yangilash
kifoya.
