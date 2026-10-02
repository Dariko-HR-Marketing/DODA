# FR-KNW-002..009 va FR-CTL-004 (Knowledge/RAG pipeline + Memory): dizayn eslatmalari

**Holat**: taklif/eslatma hujjati, kod emas. TRD'ning to'liq talab-ID
sweep'ida FR-KNW-003..009 hech qayerda (kod ham, CLAUDE.md ham) ID
bo'yicha keltirilmagani aniqlandi — faqat FR-KNW-001'ning o'z commit
xabarida "FR-KNW-002 dan boshlab... barchasi qurilmadi" deb JAMOAVIY
zikr qilingan edi. QOIDA 2 ("ID'siz talab yo'q") buni to'liq
qondirmaydi — bu hujjat har bir ID'ni alohida, TRD'ning o'z matniga
(3.5-bo'lim va 8-bo'lim, `docs/DODA-TRD-v2.0.docx`) qarab baholaydi.

## Xulosa jadvali

| ID | Toifa | Holat |
|---|---|---|
| FR-KNW-001 | — | **Qurildi** (avvalgi sessiyada) — fayl ingest, tur/hajm/malware validatsiyasi |
| FR-KNW-002 | — | **Qurildi** — Product Owner haqiqiy Gemini API kalitini taqdim etgandan keyin (bu hujjat yozilgan vaqtda ADR-008/009'ning "uchala provayder ham bloklangan" holati endi noto'g'ri — ADR-009'ning o'zi keyinroq yangilandi). Pastga qarang. |
| FR-KNW-003 | C | Endi bitta YANGI, torroq blokerga bog'liq: eval to'plami + reranking dizayni (qabul mezoni "eval to'plamida baseline'dan yaxshi natija" — eval to'plami hali yo'q) |
| FR-KNW-004 | C | 003'ning retrieval natijasisiz "manba"ning o'zi yo'q — endi 003'ga bog'liq, 002'ga emas |
| FR-KNW-005 | B (qisman) | "Indeks"ning o'zi endi mavjud (002) — FK `ondelete="CASCADE"` orqali hujjat o'chirilganda chunk'lar ham avtomatik o'chadi, bu mezonning "indeks"ga tegishli yarmini qamraydi. "Blob va derived artifact"lar (cache, boshqa hosilalar) hali mavjud emas — ularning o'zi yo'q, tarqatadigan narsa yo'q. Mustaqil, alohida FR-KNW-005 ID bilan ochiq hal qilinmadi (CASCADE 002'ning o'z qurilishining tabiiy natijasi, maqsadli FR-KNW-005 ishi emas) |
| FR-KNW-006 | C | 003/004'ning retrieval+citation natijasisiz "topilmadi" holatini simulyatsiya qilib bo'lmaydi — 003'ga bog'liq |
| FR-KNW-007 / FR-CTL-004 | C (qisman A) | "Preference" xotira turi allaqachon boshqa ID'lar ostida qurilgan; qolgan to'rt turi (Working/Episodic/Semantic/Sensitive) yangi PO qarori kerak |
| FR-KNW-008 | C | Asinxron ingest+progress — 002'ning SINXRON versiyasi qurilgandan keyin ham, bu hamon alohida ish (job-queue infratuzilmasi, FR-KNW-002'ning o'z docstring'ida ochiq qoldirilgan) |
| FR-KNW-009 | C | Versiyalash DB darajasida mustaqil qurilishi mumkin, lekin "retrieval'dan chiqarish" 003'ning o'z mexanizmini talab qiladi — 003'ga bog'liq |

Toifalar FR-ADM design-proposal hujjatining o'zi bilan bir xil: (A)
allaqachon mavjud, faqat ID bilan bog'lash kerak edi; (B) mavjud
infratuzilma bilan kichik xavfsiz qadam; (C) yangi Product Owner/
arxitektura qarorini yoki hali qurilmagan tashqi bog'liqlikni talab
qiladi.

## FR-KNW-002 qurildi — zanjir endi 003'da to'xtaydi, 002'da emas

**Bu bo'lim yozilgan vaqtda** (ushbu hujjatning birinchi versiyasi)
FR-KNW-002 (parsing→chunking→embedding→indexing) real, ishlaydigan
embedding chaqiruvini talab qilardi, va bu muhitning tarmoq siyosati
uchala AI provayderning ham haqiqiy API'siga chiqishni bloklardi
(ADR-008/ADR-009'ning o'z "honest limitation" bo'limlari). **Bu holat
keyinroq o'zgardi**: Product Owner haqiqiy, ishlaydigan Gemini API
kalitini taqdim etdi, va bu muhitning `generativelanguage.googleapis.com`
ga tarmoq yo'li ham (sabab noma'lum — tashqi tomondan o'zgargan)
alohida tekshirilib ochiq ekani tasdiqlandi. Shundan keyin FR-KNW-002
haqiqatda, real Gemini embedding API'ga qarshi (sintetik emas) qurildi
va tasdiqlandi — pastdagi "FR-KNW-002: qurilgan holat" bo'limiga qarang.

Qurilish jarayonida **haqiqiy, jiddiy xato topildi va tuzatildi**:
Gemini'ning `embed_content`iga `contents=` sifatida oddiy `list[str]`
uzatish SDK'ning o'z `t_contents` transformerida BITTA ko'p-qismli
`Content`ga aylanadi (chat'ning bitta ko'p-qismli BURILISHI uchun
mo'ljallangan shakl, N ta mustaqil hujjat uchun emas) — va real API bu
holatda talab qilingandan KAMROQ embedding qaytarishi mumkin ekani
aniqlandi (2 ta 2000/239-belgili chunk uchun aynan 1 ta embedding
qaytdi, 2 emas). Tuzatish: har bir matn uchun ALOHIDA `Content` obyekti
qurish (`doda/infrastructure/gemini_embedding.py`ning o'z docstring'iga
qarang) — bu real API'ga qarshi tasdiqlandi (2 ta matn uchun 2 ta,
haqiqatda farqli embedding). Bu aynan "kichik, uzoq umr ko'radigan
ad-hoc tekshiruv kerak" degan QOIDA 1 intizomining o'zi topib bergan
xato — faqat avtomatlashtirilgan pytest testlari (fake embedding port
bilan) bu xatoni hech qachon ushlay olmasdi.

**Endi zanjir 003'da to'xtaydi, 002'da emas**: 003 (gibrid retrieval:
metadata+keyword+vector+reranking) endi YANGI, torroq blokerga ega —
"eval to'plamida baseline'dan yaxshi natija" qabul mezoni haqiqiy eval
to'plamini talab qiladi, bu alohida, kattaroq ish (reranking dizayni +
baseline o'lchovi). 004/006/009 shu 003'ga bog'liq bo'lib qoladi.
005 esa 002'ning o'z CASCADE xatti-harakati tufayli QISMAN, tasodifan
yopildi (yuqoridagi jadvalga qarang) — bu alohida, maqsadli FR-KNW-005
ishi emas.

## FR-KNW-007 / FR-CTL-004 — Memory: qisman allaqachon qurilgan

**Talab (TRD 8-bo'lim)**: beshta memory turi — Working (joriy chat
konteksti), **Preference** (til, format, ism, uslub — "foydalanuvchiga
ko'rinadi va tahrirlanadi"), Episodic (oldingi task natijasi),
Semantic (tasdiqlangan fakt/knowledge), Sensitive (sog'liq/moliya/
sirlar — "default o'chiq, explicit consent"). FR-CTL-004'ning qabul
mezoni: "Sensitive memory default o'chiq; yoqish explicit consent
talab qiladi."

**Preference turi — allaqachon, boshqa ID'lar ostida, mustaqil
qurilgan**: TRD'ning o'z misoli ("til, format, ism, uslub") aynan
mos keladigan narsalar bu kod bazasida allaqachon bor —
`Conversation.pinned_language`/`WorkspaceLanguageSetting` (FR-CONV-001/
FR-WKS-007), `UserAIPreference`/`WorkspaceAIPreference` (FR-ADM-006) —
barchasi "foydalanuvchiga ko'rinadi va tahrirlanadi" (GET/PUT/DELETE
endpoint'lari, frontend forma) va "provenance" (audit event — FR-ADM-006
tuzatishidan keyin) talabini qondiradi. Bu qurilganda "memory" atamasi
ishlatilmagan edi — TRD 8-bo'limining o'zi buni keyinroq o'qib
solishtirilganda aynan shu qatlamning bir qismi ekani ma'lum bo'ldi.

**Working/Episodic/Semantic/Sensitive — yangi Product Owner qarorini
talab qiladi, qurilmadi**:
1. **Working** (joriy chatdagi vaqtinchalik kontekst) — bu allaqachon
   `conversation_service.stream_message`ning o'z `history`si (suhbat
   davomidagi xabarlar) orqali AMALDA mavjud, lekin TRD uni alohida
   "memory" sifatida nomlab, retention/consent siyosatiga bog'laydi —
   buni alohida ID sifatida "qurish" kerakmi, yoki mavjud suhbat
   tarixining o'zi yetarlimi, Product Owner hal qilishi kerak savol.
2. **Episodic** ("oldingi task natijasi", "relevance + consent" bilan
   yoziladi) — bu FR-KNW-002/003'ning retrieval mexanizmiga tayanadi
   (task natijasini keyingi suhbatda "eslash" degani — semantik qidiruv
   kerak), demak shu blokerning o'zi bilan bog'liq.
3. **Semantic** ("tasdiqlangan fakt yoki knowledge", versiyalangan) —
   xuddi Episodic kabi, FR-KNW-002/003'ga bog'liq.
4. **Sensitive** (default o'chiq, explicit consent, "secretlar
   butunlay chiqarib tashlanadi") — bu OD-003'ning kengaytmasi bo'lar
   edi (`doda.ai.outbound_guard`/`doda.ai.data_classification`
   allaqachon C4/C5'ni bloklaydi, lekin bu YO'QLIKKA majburlaydi, uni
   "consent bilan yoqish mumkin memory" qilib saqlash butunlay boshqa,
   ancha xavfliroq xususiyat — qanday shifrlanadi, kim ko'ra oladi,
   qachon o'chiriladi — hammasi yangi qaror).

8.1-bo'limning "Memory write gate" (7 bosqichli ketma-ket tekshiruv:
scope→sensitivity→consent→dedup→provenance→retention→encryption) va
8.2'ning "Retrieval ACL" (filter-before-vector) — ikkalasi ham FR-KNW-
002/003 mavjud bo'lmasa amalga oshirib bo'lmaydigan mexanizmlar,
shuning uchun bu ham asosiy blokerning bir qismi.

**Taklif (agar/qachon boshlansa)**: FR-KNW-002 (embedding+chunking
pipeline) qurilishi bilan bir vaqtda, Working/Episodic/Semantic uchun
`domain/memory` yangi domeni — 8.1'ning gate'ini bitta, markazlashtirilgan
`write_memory_candidate(...)` funksiyasi sifatida (kelajakda 8.1'ning
yetti bosqichini alohida-alohida qo'shish o'rniga, boshidanoq to'liq
zanjir bilan). Sensitive turi esa alohida, keyinroq Product Owner
qaroridan keyin — bu eng yuqori xavfli, eng kech boshlanishi kerak
qism.

## Umumiy xulosa

To'qqizta FR-KNW ID'idan ikkitasi (001, 002) qurilgan; 005 qisman,
tasodifan (002'ning CASCADE xatti-harakati orqali) yopilgan. Qolgan
to'rttasi (003/004/006/009) endi YANGI, torroq blokerga (eval to'plami +
reranking dizayni, FR-KNW-003) bog'liq — avvalgi "real embedding
chaqiruvi yo'q" blokeri endi mavjud emas. FR-KNW-008 (asinxron ingest)
alohida, job-queue infratuzilmasi talab qiladigan ish bo'lib qoladi.
FR-KNW-007/FR-CTL-004 (memory) — beshta turdan bittasi (Preference)
allaqachon boshqa ID'lar ostida qondirilgan, qolgan to'rttasi ham
yuqoridagi retrieval blokeri bilan (Episodic/Semantic) yoki yangi,
alohida Product Owner qaroriga (Sensitive consent modeli) bog'liq.

## FR-KNW-002: qurilgan holat (texnik tafsilot)

`doda.ai.embedding_port`/`embedding_factory` — `doda.ai.port.
ModelGateway`ning bir xil "Protocol + Null fallback" naqshi, FAQAT
Gemini uchun (Anthropic'da embedding endpoint umuman yo'q, OpenAI esa
bu sandbox'dan hamon bloklangan). `doda.domain.knowledge.text_extraction`
(TXT/PDF/DOCX/XLSX — pypdf/python-docx/openpyxl) va `chunking` (sof,
belgi-asosli, overlap bilan) domain qatlamida, DB/tarmoqdan mustaqil.
`DocumentChunk` (migratsiya 0029, pgvector 0.6.0, `vector(3072)` ustuni,
`knowledge_documents`ga `ondelete="CASCADE"` bilan bog'langan) —
`knowledge_documents`ning aynan bir xil RLS shakli.

Indekslash fayl yuklash HTTP so'rovining O'ZIDA, sinxron ishlaydi (AI
chat gateway'lari bilan bir xil "caller'ning o'z javobi shu chaqiruvga
bog'liq, async worker yo'q" mulohazasi) — embedding kaliti sozlanmagan
bo'lsa, yuklash FR-KNW-002'dan oldingi xatti-harakatning aynan o'zi
bilan davom etadi (0 ta chunk, xato emas). Rasmiy, avtomatlashtirilgan
pytest qamrovi (`tests/unit/test_chunking.py`, `test_text_extraction.py`,
`test_embedding_port.py`, `test_gemini_embedding.py`,
`tests/integration/test_knowledge_api.py`) haqiqiy tarmoq/kredensialga
bog'liq emas — soxta, deterministik `EmbeddingPort` ishlatadi (xuddi
chat testlarining `NullModelGateway`/`_RecordingGateway` naqshi). Real,
to'liq pipeline (ingest→chunk→embed→DB) real Postgres+real Gemini'ga
qarshi, pytest'dan tashqarida, bir martalik skript bilan tasdiqlandi —
2 ta chunk, to'g'ri lineage (offset 0-2000, 1800-2039), 3072-o'lchamli
haqiqiy vektorlar.
