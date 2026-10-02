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
| FR-KNW-003 | — | **Qurildi** — keyword (ILIKE, per-word) + vector (cosine distance) + metadata filter (document_id), Reciprocal Rank Fusion bilan birlashtirilgan. Pastga qarang. |
| FR-KNW-004 | C | 003'ning retrieval natijasisiz "manba"ning o'zi yo'q edi — endi 003 qurilgan, lekin FR-KNW-004'ning o'z qabul mezoni (citation UI/format) alohida, hali qurilmagan ish — 003 faqat uning ORQASIDAGI retrieval mexanizmini ta'minlaydi |
| FR-KNW-005 | B (qisman) | O'zgarmadi — "Indeks"ning o'zi mavjud (002) — FK `ondelete="CASCADE"` orqali hujjat o'chirilganda chunk'lar ham avtomatik o'chadi |
| FR-KNW-006 | C | 003 endi qurilgan, lekin "manba topilmasa ochiq ayt" (chat javobining o'zi) alohida ish — bugun `knowledge_search` tool'i "No matching documents found." deb aniq qaytaradi (model buni ko'radi), lekin modelning bu javobni QANDAY taqdim qilishi (masalan "bu savolga javob topa olmadim" deb ochiq aytishi) prompt-injection emas, modelning o'z javobi — tekshirilmagan |
| FR-KNW-007 / FR-CTL-004 | C (qisman A) | "Preference" xotira turi allaqachon boshqa ID'lar ostida qurilgan; qolgan to'rt turi (Working/Episodic/Semantic/Sensitive) yangi PO qarori kerak |
| FR-KNW-008 | C | Asinxron ingest+progress — 002'ning SINXRON versiyasi qurilgandan keyin ham, bu hamon alohida ish (job-queue infratuzilmasi, FR-KNW-002'ning o'z docstring'ida ochiq qoldirilgan) |
| FR-KNW-009 | C | Versiyalash DB darajasida mustaqil qurilishi mumkin, lekin "retrieval'dan chiqarish" 003'ning o'z mexanizmini talab qiladi — 003 endi qurilgan, lekin versiyalashning o'zi (DocumentChunk bir nechta versiyasi) hali yo'q |

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

## FR-KNW-003: qurilgan holat (texnik tafsilot)

`doda.domain.knowledge.retrieval.reciprocal_rank_fusion` — TRD'ning
o'z "reranking" talabining deterministik, ML'siz yechimi (Cormack,
Clarke & Buettcher, 2009) — har bir ranking ro'yxatidan `1/(k+rank)`
qo'shib, ikkita MUSTAQIL natija (keyword, vector) ro'yxatini birlashtiradi.
Bu qasddan tanlov: RRF algoritmining o'zini tekshirish uchun eval
to'plam shart emas (hech qanday o'qitish ma'lumoti yo'q), faqat uning
retrieval sifatiga ta'sirini isbotlash uchun kerak — bu farq pastda
"eval harness" bo'limida muhim.

`doda.application.knowledge_service.search_knowledge` — ikkita mustaqil
"leg" + RRF fusion: (1) keyword — `DocumentChunk.content.ilike(...)`,
so'rovning har bir >=3 belgili so'zi bo'yicha, nechta so'z mos kelgani
bo'yicha saralangan (FR-CONV-006'ning `search_messages_in_workspace`
bilan bir xil LIKE-escape intizomi, lekin butun-ibora emas, so'z-so'z);
(2) vector — pgvector'ning `DocumentChunk.embedding.cosine_distance(...)`
komparatori orqali, eng yaqinidan boshlab. `document_id` — FR-KNW-003'ning
"metadata filter" qismi, ixtiyoriy. Bo'sh/probel so'rov FR-CONV-006'ning
o'zi bilan bir xil sababdan bo'sh natija qaytaradi (unbounded scan emas).
Workspace chegarasi aniq `DocumentChunk.workspace_id == workspace_id`
predikati orqali (RLS'ning o'ziga tayanmasdan — RLS faqat `customer_id`ni
bilar, bitta customer ichidagi workspace'larni emas, NFR-ISO-002'ning
o'zi talab qilgan ikkinchi qatlam).

`GET /v1/workspaces/{id}/documents/search?q=...&document_id=...&limit=...`
— `{document_id}` route'idan OLDIN ro'yxatdan o'tkazilgan (Starlette
registratsiya tartibida moslashtiradi, FR-TASK-002'ning o'z `/plan`
darsining takrori — bu bu safar ham real revert-test-restore bilan
isbotlandi: route tartibini vaqtincha almashtirib, 3 ta yangi test
aynan kutilgan 422 bilan muvaffaqiyatsiz bo'lishi ko'rsatildi, keyin
qaytarib yashil ekani tasdiqlandi). Embedding sozlanmagan bo'lsa
`EmbeddingNotConfiguredError` → 503 `EMBEDDING_NOT_CONFIGURED` (xuddi
chat'ning `AI_PROVIDER_NOT_CONFIGURED`si bilan bir xil "tell the
truth" naqshi).

**Chat'ga ulanish**: yangi `knowledge_search` READ tool (`ai_tools.py`)
— model so'rasa darhol bajariladi (WRITE tool'lardan farqli, approval
zanjiri shart emas — bu faqat o'qish). `dispatch_read_tool`'ning
signaturasiga yangi, majburiy `settings: Settings` parametri qo'shildi
(embedding provider'ni qurish uchun) — bu barcha mavjud chaqiruvchilarni
(testlar + `conversation_service.stream_message`) yangilashni talab
qildi, mypy orqali to'liq tasdiqlangan. Embedding sozlanmagan bo'lsa
tool natija sifatida oddiy matn qaytaradi ("Document search is not
available..."), xato ko'tarmaydi — bu holat modelning o'zi uchun
kutilgan, tiklanadigan holat, xato emas (`NullEmbeddingPort`ning "hech
qachon soxta natija bermaslik" falsafasining davomi, faqat bu safar
tool-natija darajasida).

**Eval harness** (`backend/scripts/retrieval_eval.py`) — FR-KNW-003'ning
o'z qabul mezonini ("eval to'plamida baseline'dan yaxshi natija") REAL
Gemini embedding'ga qarshi isbotlaydi, sintetik emas. Ikki usul
solishtiriladi: hybrid (`search_knowledge`) vs vektor-yagona baseline
(xuddi shu vektor so'rovining o'zi, keyword leg/RRF'siz). Eval to'plami
atayin "yaqin-dublikat" stsenariysi atrofida qurilgan: ikkita hujjat
bir xil gap tuzilishi va lug'at bilan, lekin FARQLI aniq kod bilan
(`ERRCODE-7731` vs `ERRCODE-9912`) — bu embedding-modellarning haqiqiy,
hujjatlashtirilgan zaifligi: ikkita ko'rinmagan alfanumerik kodni faqat
kontekstdan farqlash prinsipial jihatdan mumkin emas, keyword leg esa
xom matnni solishtiradi, ma'noni emas. **Haqiqiy natija** (real Gemini
embedding bilan, ikki marta ketma-ket takrorlanib tasdiqlangan): hybrid
MRR=1.000, baseline MRR=0.875 — parafraz qilingan so'rovda
(`"qanday xato kodi logda ko'rsatilgan"`) vector-only to'g'ri hujjatni
2-o'ringa qo'ygan, hybrid esa 1-o'ringa. Boshqa uchta so'rovda ikkalasi
ham teng (1-o'rin) — bu halol: kichik eval to'plamida har bir so'rov
hybrid'ning o'z ustunligini ko'rsatmaydi, faqat aniq shu stsenariy
ko'rsatadi.

**Frontend**: workspace sahifasining "Fayllar" bo'limiga qidiruv formasi
qo'shildi. Yangi E2E qadam (`knowledge.spec.ts`) muhitni OLDINDAN probe
qiladi (`page.request.get` bilan to'g'ridan-to'g'ri backend'ga) va shu
muhit haqiqatda qaysi holatda ekaniga qarab filiallanadi — CI hech
qachon embedding kaliti o'rnatmagani uchun u yerda doim 503-filial
ishlaydi, lekin real kalit mavjud bo'lgan muhitda (masalan operator
o'z `.env`ida) 200-filial (haqiqiy qidiruv, haqiqiy natija) sinaladi.
Bu ikkala holat ham shu sessiyada real, ikkala muhitni ham qo'lda
simulyatsiya qilib (`.env`dagi uchta AI kalitini vaqtincha olib tashlab,
keyin qaytarib) tasdiqlandi — ikkalasida ham butun 17 ta E2E spec
yashil.

**Halol, ochiq qoldirilgan topilma**: bu tekshiruv jarayonida FR-KNW-001
davridan qolgan ikkita E2E fixture (`knowledge.spec.ts`ning "report.pdf",
`task-attachments.spec.ts`ning "evidence.pdf") haqiqiy, sintetik
header-only "PDF" ekani (real PDF struktura yo'q) va ular FAQAT
embedding sozlanmagan muhitda "muvaffaqiyatli" yuklanishi (chunki
`index_document` chaqirilmaydi) aniqlandi — embedding sozlangan muhitda
`extract_text` haqiqiy `PdfStreamError` bilan qulab, butun yuklashni
(Document qatori bilan birga) bekor qiladi. Bu FR-KNW-003'ning o'zi
yaratgan xato EMAS — bu ikki fixture FR-KNW-001 qurilishidan beri shu
holatda, va CI hech qachon embedding kaliti o'rnatmagani uchun ularning
o'z CI tekshiruvi hamon to'g'ri, buzilmagan holda qoladi. Bu faqat shu
sandbox'ning `.env`i endi real kalitlar bilan CI'dan farq qilgani
sababli ko'ringan, kelajakdagi tuzatish uchun qayd etilgan topilma —
FR-KNW-003'ning o'z diff doirasidan tashqarida (minimal-diff qoidasi),
shuning uchun bu safar tuzatilmadi.
