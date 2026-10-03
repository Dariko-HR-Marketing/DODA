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
| FR-KNW-004 | — | **Qurildi** — `CITATION_INSTRUCTION` + knowledge_search'ning o'z "[manba: document_id=..., chunk=...]" locator formati, real Gemini'ga qarshi `citation_eval.py` bilan isbotlandi. Pastga qarang. |
| FR-KNW-005 | — | **Qurildi** — mexanizmning o'zi (CASCADE + blob delete) 002/001 davridanoq bor edi, lekin TRD'ning o'z qabul mezoni ("retrieval 0 qaytaradi; blob mavjud emas") hech qachon shu aniq shaklda, end-to-end tekshirilmagan edi. Pastga qarang. |
| FR-KNW-006 | — | **Qurildi** — unconditional `GROUNDEDNESS_INSTRUCTION` har bir burilishga qo'shiladi, real Gemini'ga qarshi uch stsenariyli eval bilan isbotlandi (`backend/scripts/groundedness_eval.py`). Pastga qarang. |
| FR-KNW-007 / FR-CTL-004 | C (qisman A) | "Preference" xotira turi allaqachon boshqa ID'lar ostida qurilgan; qolgan to'rt turi (Working/Episodic/Semantic/Sensitive) yangi PO qarori kerak |
| FR-KNW-008 | C | Asinxron ingest+progress — 002'ning SINXRON versiyasi qurilgandan keyin ham, bu hamon alohida ish (job-queue infratuzilmasi, FR-KNW-002'ning o'z docstring'ida ochiq qoldirilgan) |
| FR-KNW-009 | — | **Qurildi** — `Document.superseded_by_id` orqali versiyalash + `search_knowledge`ning o'z exclusion filtri. Pastga qarang. |

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

**Eslatma — bu bo'lim CLAUDE.md'da bir necha marta hujjatlashtirilgan
"current-state hujjat faqat yangi yozuv qo'shilganda emas, davriy ravishda
qayta o'qilishi kerak" darsining o'z nusxasi edi**: quyidagi paragraf
FR-KNW-003/005/006/009 hali qurilmagan vaqtda yozilgan, keyinchalik
to'rttasi ham qurilganda bu paragrafning o'zi qaytib yangilanmay qolgan
edi — yuqoridagi jadval to'g'ri, faqat shu paragraf eskirgan edi. Endi
to'g'rilandi.

To'qqizta FR-KNW ID'idan ettitasi (001, 002, 003, 004, 005, 006, 009)
qurilgan. Qolgan ikkitasidan FR-KNW-008 (asinxron ingest) alohida,
job-queue infratuzilmasi talab qiladigan ish bo'lib qoladi. FR-KNW-007/
FR-CTL-004 (memory) — beshta turdan bittasi (Preference) allaqachon
boshqa ID'lar ostida qondirilgan, qolgan to'rttasi (Working/Episodic/
Semantic/Sensitive) yangi Product Owner qaroriga bog'liq (Sensitive
consent modeli — eng muhimi).

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

## FR-KNW-005: qurilgan holat (texnik tafsilot)

Mexanizmning o'zi (hujjat o'chirilganda uning chunk'lari CASCADE orqali,
blob'i esa `delete_document`ning o'z `storage.delete(...)` chaqiruvi
orqali o'chishi) FR-KNW-001/002 qurilgandan beri bor edi — bu yangi kod
emas. Yetishmagani TRD'ning o'z qabul mezonining AYNAN ikkala yarmini
("retrieval 0 natija qaytaradi; blob mavjud emas") bitta end-to-end
testda, to'g'ridan-to'g'ri HTTP orqali tekshirish edi: mavjud
`test_deleting_a_document_cascades_to_its_chunks` faqat `DocumentChunk`
qatorlarini to'g'ridan-to'g'ri DB so'rovi bilan tekshirar edi (SEARCH
ENDPOINT'ning o'zi emas), va hech qanday test `delete_document`ning o'z
`storage.delete(...)` chaqiruvi haqiqatda diskdan faylni o'chirishini
tasdiqlamagan edi (mavjud `test_downloading_a_document_whose_stored_
object_went_missing_is_a_clean_404` buning TESKARISINI — faylni qo'lda
o'chirib, DB qatori qolgan holatni — sinaydi, `delete_document`ning
o'zini emas).

Yangi `test_deleting_a_document_makes_it_unsearchable_and_removes_its_
blob` (`test_knowledge_api.py`) uchtasini ham bitta oqimda tekshiradi:
hujjat yuklanadi (bitta blob yoziladi, `tmp_path.rglob`da tasdiqlanadi),
`GET .../documents/search` uni topadi, `DELETE .../documents/{id}`
chaqiriladi, keyin AYNAN SHU qidiruv endi bo'sh ro'yxat qaytarishi VA
`tmp_path`da hech qanday fayl qolmaganligi tasdiqlanadi.

Audit-zanjiri uslubida isbotlandi: `delete_document`ning o'z
`storage.delete(document.storage_key)` chaqiruvini vaqtincha `pass`ga
almashtirib, test aynan kutilgan tarzda (blob hamon diskda qolib)
muvaffaqiyatsiz bo'lishini ko'rsatdim, keyin qaytarib (`git diff` bilan
0 farq tasdiqlab) yashil ekanini ko'rsatdim. 647 test, barchasi real
Postgres'da; `ruff`/`mypy src/doda`/`mypy scripts` toza. Kod o'zgarmadi
(faqat yangi test) — mexanizmning o'zi allaqachon to'g'ri edi, endi
TRD'ning o'z so'zlari bilan, to'liq isbotlangan.

## FR-KNW-006: qurilgan holat (texnik tafsilot)

Qabul mezoni — "'Ma'lumot yetarli emas' eval stsenariylari PASS" — sof
prompt-engineering ishi, haqiqiy model chaqiruvisiz "isbotlab" bo'lmaydi
(bu AI qatlamining o'zi: kod-darajasidagi gate emas, `doda.ai.
groundedness`ning o'z docstring'i bu farqni `file_validation.py`'ning
"malware validatsiyasi" bilan bir xil tilda chizadi). `GROUNDEDNESS_
INSTRUCTION` (`backend/src/doda/ai/groundedness.py`) — `knowledge_search`
hech narsa topmasa yoki modelning o'zida yetarli ma'lumot bo'lmasa, buni
ochiq aytish, taxmin qilmaslik, to'qib chiqarmaslik haqidagi aniq
ko'rsatma — `conversation_service.stream_message`'ning `instructions`
qatoriga SHARTSIZ qo'shildi (FR-CONV-001'ning shartli til-ko'rsatmasi
bilan bir qatorda, lekin undan farqli — til ko'rsatmasi ba'zan bo'sh
bo'ladi, bu esa hech qachon). Mavjud yagona `instructions == [""]`
testi (`test_an_ambiguous_message_sends_no_language_directive_at_all`)
yangilandi — endi aniq bo'sh bo'lmasligini tasdiqlaydi.

`backend/scripts/groundedness_eval.py` — boshqa mustaqil eval
skriptlari (`retrieval_eval.py`, `run_ai_eval_suite.py`) bilan bir xil
konventsiya: pytest emas, qo'lda ishga tushiriladi, real sozlangan
provayderga qarshi, hech qanday provayder sozlanmasa ishdan bosh
tortadi (NullModelGateway'ning soxta "pass"ini oldini olish uchun).
Uchta stsenariy, bittasi emas — "haddan tashqari ehtiyotkor" bo'lib
qolmasligini (hamma narsaga "bilmayman" deyish) tekshirish ham xuddi
haqiqiy ishonchni tekshirishning o'zi kabi muhim:
- `fictional_identifier` — mavjud bo'lmagan, o'ylab topilgan kod haqida
  so'raladi, hujjat yo'q.
- `unanswered_by_documents` — embedding sozlangan bo'lsagina ishga
  tushadi: workspace'ga haqiqiy, lekin aloqasiz hujjatlar yuklanadi,
  `knowledge_search` chaqirilishi aniq so'raladi, u haqiqatda "hech narsa
  topilmadi" qaytarishi kerak.
- `easy_factual_control` — oddiy, javobi aniq savol (nazorat): bu
  ko'rsatma modelni hamma narsadan bosh tortishga majburlamasligini
  isbotlaydi.

Hukm — Uzbek/English "bilmayman" iboralarining oddiy, shaffof ro'yxati
(statistik baholovchi emas) — `retrieval_eval.py`'ning o'zi ham xuddi
shunday halol chegarani qabul qiladi.

**Birinchi real ishga tushirishda yangi, jiddiy, aloqasiz xato chiqdi:
Gemini'ning ko'p bosqichli tool-chaqiruvi (model → tool call → tool
natija → yakuniy javob, BIR HTTP so'rovi ichida) butunlay buzuq edi.**
`gemini-3.1-flash-lite` har bir function-call Part'iga `thought_
signature` (opaque, Gemini'ning o'z "fikrlash" davomiyligini saqlash
uchun signature'i) biriktiradi — va buni KEYINGI so'rovda aynan
qaytarmasa, Gemini `400 INVALID_ARGUMENT` bilan BUTUN so'rovni rad
etadi ("Function call is missing a thought_signature..."). Bu
`google-genai`'ning o'z qulay `response.function_calls` xususiyati
`FunctionCall`ni Part'dan ajratib olib, signature'ni (Part'ning o'z,
alohida maydoni, `FunctionCall`da yo'q) jimgina tashlab yuborgani
sababli `gemini_gateway.py`da hech qachon o'qilmagan, demak hech qachon
keyingi so'rovga qaytarilmagan edi — bu AYNAN mening yangi `knowledge_
search`ni ishlatadigan eval stsenariylarim birinchi marta haqiqiy
Gemini'ga qarshi, ko'p bosqichli tool-aylanish bilan ishga tushgani
uchun ochilgan, taxmin qilinmagan, real xato.

Real API'ga qarshi (`/tmp/gemini_probe*.py`, uchta alohida tekshiruv)
tasdiqlandi: (1) `thinking_budget=0` muammoni HAL QILMAYDI — model
baribir signature biriktiradi; (2) signature'ni qo'lda qayta
biriktirish muammoni to'liq hal qiladi (ikkinchi so'rov muvaffaqiyatli,
haqiqiy javob matni bilan); (3) wire-format `thoughtSignature` (camelCase,
base64), `google-genai`ning o'zi `bytes <-> base64` konvertatsiyasini
avtomatik bajaradi.

Tuzatish: `doda.ai.types.ToolCallRequest`ga yangi, ixtiyoriy
`provider_metadata: dict[str, Any] | None = None` maydoni qo'shildi —
provayder-neytral turni buzmaydi (hech narsa provayder nomini
ATAMAYDI), faqat bitta adapterga kerak bo'lgan narsani xavfsiz
tashishga mo'ljallangan umumiy bo'shliq, boshqa adapterlar uni e'tiborsiz
qoldiradi. `gemini_gateway.py`ning `stream_chat`i endi `chunk.
function_calls` o'rniga `candidate.content.parts`ni to'g'ridan-to'g'ri
aylanib, har bir `function_call` Part'ning o'z `thought_signature`sini
`provider_metadata`ga joylaydi; `_to_gemini_contents` esa shu
metadata'dan signature'ni o'qib, qayta qurilgan `Part.from_function_
call(...)`ga biriktiradi.

Ikkala yo'nalish ham `test_gemini_gateway.py`'da real wire-shape bilan
tekshirildi (`MockTransport` orqali, haqiqiy HTTP so'rov tanasi
ushlanib): signature javobdan to'g'ri o'qilishi, va keyingi so'rovning
JSON tanasida to'g'ri `thoughtSignature` bilan qaytarilishi. Audit-
zanjiri uslubida isbotlandi — `_to_gemini_contents`ning signature
biriktirish qatorini vaqtincha olib tashlab, replay-testi aynan
kutilgan `KeyError: 'thoughtSignature'` bilan muvaffaqiyatsiz bo'lishi
ko'rsatildi, keyin qaytarib (`diff` bilan 0 farq tasdiqlab) yashil
ekani ko'rsatildi.

**Ataylab qolgan bo'shliq**: bu faqat BIR HTTP burilish ichidagi
(round-trip) holatni tuzatadi. Agar bir nechta HTTP so'rov oldin
chaqirilgan tool call suhbat TARIXIGA (`_messages_to_history`, DB'dan
qayta qurilganda) kirsa, `Message` jadvalida `provider_metadata`ni
saqlaydigan ustun yo'qligi sababli signature baribir yo'qoladi — bu
holat ham AYNAN shu xatoni qayta hosil qiladi (yangi migratsiya +
`Message` ustuni talab qiladi, bu ishning doirasidan tashqarida ataylab
qoldirildi, `conversation_service.py`ning o'z docstring'ida ochiq
yozilgan).

**Birinchi real ishga tushirishda OpenAI (tarmoq siyosati bloklaydi) va
Claude (Anthropic hisobida kredit yetarli emas) — ikkalasi ham oldindan
hujjatlashtirilgan, bu ish bilan aloqasiz sabablar bilan — ERROR
qaytardi.** Gemini tuzatishdan KEYIN uchala stsenariy ham (fictional_
identifier, unanswered_by_documents, easy_factual_control) PASS berdi —
real, sintetik bo'lmagan Gemini javoblari bilan: ikkala "hedge"
stsenariyida ham model ochiq "Bu savolga javob berish uchun ma'lumot
yetarli emas" deb javob berdi, nazorat stsenariysida esa to'g'ridan-
to'g'ri "4" javobini berdi — ko'rsatma modelni haddan tashqari
ehtiyotkor qilib qo'ymagani tasdiqlandi.

652 test, barchasi real Postgres(+Redis)'da; `ruff`/`mypy src/doda`/
`mypy scripts` toza.

**Yo'l-yo'lakay topilgan, aloqasiz ikkinchi xato**: `mypy scripts`
(CI'ning o'z, alohida "mypy (scripts)" bosqichi) `doda` paketini
editable-install orqali o'zining fayl to'plamidan TASHQARIDA hech qachon
to'g'ri aniqlay olmas edi — `ignore_missing_imports = true` bilan
birgalikda, bu HAR BIR `doda.*` import'ini jimgina `Any`ga aylantirib,
haqiqiy chaqiruv-joyidagi xatolarni (masalan, kerakli argumentning
yo'qligi) umuman ushlamasdi. `reveal_type()` bilan tasdiqlandi. Bu
aynan `backend/scripts/run_ai_eval_suite.py`'ning o'zida HAQIQIY,
ishlamaydigan holatga olib kelgan edi: `stream_message`ga FR-AUTH-009's
R2-cap tuzatishida qo'shilgan majburiy `actor_kind` argumenti hech
qachon uzatilmagan, lekin `mypy scripts` buni hech qachon ko'rsatmagan
edi. `pyproject.toml`ning `[tool.mypy]`siga `mypy_path = "src"`
qo'shilib tuzatildi (`mypy src/doda scripts`ni BIRGA ishga tushirish
muammoni ko'rsatganini avval tasdiqlab, keyin bu konfiguratsiya
yechimi alohida, tezroq `mypy scripts` chaqiruvi uchun ham xuddi shunday
ishlashi tasdiqlandi) — `run_ai_eval_suite.py`ning o'zi ham to'g'ri
`actor_kind=ActorKind.HUMAN` bilan tuzatildi.

## FR-KNW-009: qurilgan holat (texnik tafsilot)

Qabul mezoni — "Superseded versiya javobda manba sifatida ishlatilmaydi"
— ikki qismdan iborat: (1) versiyalash mexanizmining o'zi, (2) retrieval'dan
chiqarish. `domain.knowledge.models.Document`ning o'z docstring'i
FR-KNW-002 qurilishidan beri "version_id hali modellanmagan" deb ochiq
yozgan edi — bu safar yopildi.

Versiyalash **alohida `version`/`version_id` ustun yoki "lineage" qatori
sifatida emas**, balki `Document.superseded_by_id` — o'z-o'ziga
bog'langan, nullable FK (migratsiya 0030, `ondelete="SET NULL"`) — orqali
modellandi: `NULL` = "bu joriy versiya", qiymat = "meni ALMASHTIRGAN
Document'ning id'si". `application.knowledge_service.create_document_
version` — `ingest_file`ning aynan bir xil validate+store+record
bosqichini (endi `_store_and_record_document`ga chiqarilgan, ikkalasi ham
shuni chaqiradi) qayta ishlatib, YANGI, mustaqil Document qatori (o'z
id'si, o'z storage obyekti — ESKI faylni HECH QACHON ustiga yozmaydi)
yaratadi, so'ng eski Document'ning `superseded_by_id`sini unga
yo'naltiradi. Eski Document **o'chirilmaydi** — FR-KNW-005'ning o'z
o'chirish semantikasi butunlay daxlsiz qoladi, hamon yuklab olish mumkin
(`download_document` o'zgarishsiz) — faqat `search_knowledge` uni endi
manba sifatida ko'rmaydi. Allaqachon superseded bo'lgan Document'ni
qayta versiyalashga urinish (versiya zanjirining faqat O'Z UCHIDAN
o'sishi kerak, aks holda ikkita Document bitta "current" deb da'vo
qilgan, noaniq holat paydo bo'lar edi) yangi `DocumentAlreadySupersededError`
→ 409 `DOCUMENT_ALREADY_SUPERSEDED` bilan rad etiladi.

`search_knowledge`ning o'zgarishi minimal: bitta qo'shimcha subquery-asosli
filtr (`DocumentChunk.document_id.not_in(select(Document.id).where(
Document.superseded_by_id.is_not(None)))`) `filters` ro'yxatiga qo'shildi
— bu ro'yxat ikkala leg (keyword, vector) tomonidan ham `.where(*filters,
...)` orqali baham ko'rilgani uchun ikkalasi ham avtomatik ravishda
superseded chunk'larni chiqarib tashlaydi, alohida ikkinchi o'zgarish
shart emas edi.

`POST /v1/workspaces/{id}/documents/{document_id}/versions` — `upload_
document`bilan bir xil authz/validatsiya/indekslash zanjiri, faqat
`document_id`ning joriy versiya ekanini (`_get_owned_document` orqali
workspace tekshiruvi + `create_document_version`ning o'z supersede-check'i
orqali) talab qiladi. `DocumentOut`ga `superseded_by_id` maydoni
qo'shildi — frontend buni "Almashtirilgan" belgisi sifatida ko'rsatadi.

Audit-zanjiri uslubida isbotlandi: `search_knowledge`ning yangi exclusion
filtrini vaqtincha olib tashlab, yangi `test_a_new_version_supersedes_
the_old_one_which_stays_downloadable` aynan kutilgan tarzda (superseded
Document'ning o'z chunk'i qidiruv natijasida qaytib) muvaffaqiyatsiz
bo'lishi ko'rsatildi, keyin qaytarib (`diff` bilan 0 farq tasdiqlab)
yashil ekani ko'rsatildi. Testning o'zini yozishda bitta amaliy xato
topildi va tuzatildi: dastlabki versiya ikkita hujjat kontentida umumiy
so'z ("marker") ishlatgan edi — `_FakeEmbeddingPort`ning o'zi (pozitsiya-
asosli, kontentdan mustaqil embedding qaytaradi) superseded bo'lmagan
yagona qolgan chunk'ni SO'ROVNING KONTENTIDAN qat'i nazar har doim vektor
leg orqali qaytarardi, bu esa "bo'sh natija" assertioniga ishonib bo'lmasligini
ko'rsatdi — assertion "superseded document_id hech qachon ko'rinmaydi"ga
(kengroq, lekin to'g'ri mezon) o'zgartirildi, bu fake-embedding stub'ning
o'ziga xos cheklovi, `search_knowledge`ning haqiqiy xatosi emas.

Yangi `test_a_sibling_workspaces_document_cannot_be_versioned`
(`test_cross_workspace_record_access.py`) — yangi endpoint ham mavjud
`_get_owned_document` guard'idan foydalanganini tasdiqlaydi (bir xil
customer, boshqa workspace'ning hujjatini versiyalashga urinish → 404).

**Frontend**: "Fayllar" bo'limidagi har bir joriy (superseded bo'lmagan)
hujjat qatoriga "Yangi versiya yuklash" tugmasi qo'shildi (bitta,
umumiy, yashirin `<input type="file">`ga yo'naltirilgan — ro'yxat
dinamik render qilingani uchun har qator uchun alohida ref shart emas),
superseded hujjatlar esa "Almashtirilgan" belgisi bilan ko'rsatiladi va
o'z "Yangi versiya yuklash" tugmasini yo'qotadi (backend'ning
DocumentAlreadySupersededError'ini aks ettiradi). Yangi E2E test
(`knowledge.spec.ts`) to'liq oqimni (v1 yuklash → versiyalash → badge
ko'rinishi → tugma yo'qolishi → v1 hamon o'z asl baytlari bilan yuklab
olinishi → ikkalasini ham tozalash) real backend+production frontend'ga
qarshi tasdiqladi.

**Tekshiruv jarayonida ikkita, aloqasiz muhit-drift topilmasi aniqlandi
(FR-KNW-009'ning o'zi tomonidan yaratilmagan, mavjud bo'shliqning yangi
ko'rinishlari)**: to'liq E2E suite'ni ishga tushirishda `knowledge.
spec.ts`ning ESKI FR-KNW-001 testi va `task-attachments.spec.ts`ning
o'z testi — ikkalasi ham sintetik, faqat magic-byte header'ga ega
"PDF" fixture ishlatadi — bu sandbox'ning `.env`ida endi HAQIQIY Gemini
kaliti borligi sababli (bu `.env` CI'dan farq qiladi, CI hech qachon
embedding kaliti o'rnatmaydi) `extract_text`ning haqiqiy `PdfStreamError`
bilan butun yuklashni bekor qilishiga olib keladi — bu FR-KNW-003'ning
o'z yozuvida ALLAQACHON "Halol, ochiq qoldirilgan topilma" sifatida
hujjatlashtirilgan, bu PR doirasidan tashqarida qoldirilgan muammo.
Bu safar UCHINCHI, yangi ko'rinishi ham topildi: `chat.spec.ts`ning
birinchi testi "NullModelGateway reply" degan aniq matnni kutadi, lekin
endi real Gemini kaliti konfiguratsiya qilingani uchun chat haqiqiy
Gemini javobini qaytaradi — bu ham bir xil ildiz sabab (sandbox `.env`i
CI'dan farq qiladi), yangi topilma sifatida shu yerda qayd etilmoqda,
lekin FR-KNW-009'ning o'z diff doirasidan tashqarida bo'lgani uchun
TUZATILMADI (minimal-diff qoidasi — bu `chat.spec.ts`ning o'z muammosi,
FR-KNW-009 bilan aloqasi yo'q). Har uchala holat ham **baseline'da
(mening o'zgarishlarimdan OLDIN, `git stash` bilan tasdiqlangan) AYNAN
bir xil tarzda muvaffaqiyatsiz bo'lishi** bilan isbotlandi — bu FR-KNW-009
keltirib chiqargan regressiya emasligini tasdiqlaydi. Bitta toza,
to'liq E2E ishga tushirishda: 10 ta test to'liq o'tdi, 3 tasi shu
pre-existing sabab bilan muvaffaqiyatsiz bo'ldi, 5 tasi shu fayllarning
`test.describe.configure({mode:"serial"})`i tufayli (knowledge.spec.ts'da
MENING FR-KNW-009 testim ham shu jumladan) ishga tushmadi — lekin
FR-KNW-009'ning o'z testi mustaqil, izolyatsiyalangan holda (`--grep`
bilan, ikki marta, fresh seed bilan) ishga tushirilganda izchil yashil
ekani alohida tasdiqlandi.

655 test (652 + 3: 2 integration — `test_knowledge_api.py`, 1 — `test_
cross_workspace_record_access.py`), barchasi real Postgres'da; `ruff`/
`mypy src/doda`/`mypy scripts` toza; frontend `tsc`/ESLint toza,
production build muvaffaqiyatli. Migratsiya round-trip (0029→0030→
0029→0030) qo'lda tekshirildi.

## FR-KNW-004: qurilgan holat (texnik tafsilot)

Qabul mezoni — "Groundedness eval >=90%; manbasiz claim flag qilinadi" —
TRD'ning o'z EVAL-GRD-010'si FR-KNW-004'ni FR-KNW-006 bilan bir qatorda,
"Ishonchli javob" ostida birgalikda ro'yxatlaydi. FR-KNW-006'ning o'zi
qurilgandan (`GROUNDEDNESS_INSTRUCTION`) va uning qurilish jarayonida
Gemini'ning ko'p bosqichli tool-chaqiruvi tuzatilgandan keyin,
FR-KNW-004'ning o'zi ham sof prompt-engineering ish bo'lib qoldi — hech
qanday yangi infratuzilma yoki Product Owner qarori kerak emas edi.

`doda.ai.citation.CITATION_INSTRUCTION` — `GROUNDEDNESS_INSTRUCTION`
bilan bir xil "bu PROMPT, kod-darajasidagi gate emas" falsafasi: modelga
`knowledge_search` natijasidan olingan har bir da'voni darhol o'sha
natijada ko'rsatilgan manba belgisini ANIQ ko'chirib qo'yishni so'raydi.
Bu locator formati o'ylab topilgan emas — `ai_tools.dispatch_read_tool`'
ning o'z `knowledge_search` filiali endi har bir qaytarilgan chunk'ga
`[manba: document_id=..., chunk=...]` prefiksini qo'shadi (avval faqat
`document_id` bor edi, `chunk_index` yo'q edi — FR-KNW-002'ning o'z
source-lineage maydonlaridan biri, bitta hujjat ichidagi bitta aniq
chunk'ga ishora qilish uchun zarur). Model shu aniq matnni o'zgartirmasdan
qaytarishi so'raladi — bu citation'ning haqiqiy, bitta DocumentChunk
qatoriga qaytarib bog'lanadigan (traceable) bo'lib qolishini
ta'minlaydi, erkin matnli "hujjatga ko'ra..." iborasiga aylanib
ketishini emas.

`CITATION_INSTRUCTION` `GROUNDEDNESS_INSTRUCTION`bilan bir qatorda,
`stream_message`'ning `instructions`ga SHARTSIZ qo'shildi (bu burilish
`knowledge_search`ni chaqiradimi yoki yo'qmi — bilib bo'lmaydi, model
javob berishdan OLDIN). Mavjud yagona "instructions == [...]" testi
yangilandi — endi ikkala ko'rsatma ham birga kutiladi.

Audit-zanjiri uslubida isbotlandi: `ai_tools.py`ning yangi locator
formatini vaqtincha eski (faqat `document_id`, `chunk` yo'q) formatga
qaytarib, yangilangan `test_knowledge_search_tool_finds_indexed_content`
aynan kutilgan tarzda muvaffaqiyatsiz bo'lishi ko'rsatildi, keyin qaytarib
(`diff` bilan 0 farq tasdiqlab) yashil ekani ko'rsatildi. Yangi
`tests/unit/test_citation.py` (4 test, `test_groundedness.py`bilan bir
xil "sof matn konstantasini pin qilish" naqshi) — jumladan
`CITATION_INSTRUCTION`ning o'zi `ai_tools.py`ning haqiqiy locator
formatidagi `document_id=`/`chunk=` so'zlarini nomlaganini tekshiradigan
test, kelajakda ikkisi bir-biridan jimgina uzoqlashib ketmasligi uchun.

**Eval harness** (`backend/scripts/citation_eval.py`) — `groundedness_
eval.py`ning aynan bir xil konventsiyasi, lekin har ikkala provayder
(chat VA embedding) sozlanmaguncha ishlashdan bosh tortadi (citation'ning
o'zi haqiqiy `knowledge_search` round-trip'isiz ma'nosiz). Ikki
stsenariy: `cited_claim` — haqiqiy, boshqacha taxmin qilib bo'lmaydigan
fakt (o'ylab topilgan xarid buyurtma raqami) bilan hujjat yuklanadi,
model undan foydalanib javob berishi VA citation'ni ko'rsatishi
so'raladi; PASS = javobda HAQIQIY document_id (aniq shu hujjatning o'zi)
VA "chunk=" so'zi borligi. `no_fabricated_citation_without_a_source` —
hech qanday hujjat javob bermaydigan savol; PASS = javobda HECH QANDAY
"document_id="-shaklidagi citation yo'qligi (model'ning o'zidan to'qib,
unga soxta citation yopishtirib qo'ymasligi — bu FR-KNW-006'ning o'z
groundedness ko'rsatmasi bilan birga ishlashini tasdiqlaydi).

**Haqiqiy natija** (real Gemini'ga qarshi): ikkalasi ham PASS — `cited_
claim`'da model aynan "[manba: document_id=<haqiqiy-uuid>, chunk=0]"ni
so'z-so'ziga ko'chirib qo'ydi; `no_fabricated_citation_without_a_source`da
esa (groundedness ko'rsatmasining o'zi bilan mos) "Bu savolga javob
berish uchun ma'lumot yetarli emas" deb ochiq rad etdi, hech qanday
soxta citation qo'shmasdan. OpenAI (tarmoq bloklangan) va Claude
(Anthropic hisobida kredit yetarli emas) — ikkalasi ham oldindan
hujjatlashtirilgan, bu ish bilan aloqasiz sabablar bilan ERROR qaytardi.

Frontend'ga hech narsa qo'shilmadi — chat UI assistant matnini o'zgarishsiz
render qiladi, citation locator shunchaki javob matnining bir qismi
sifatida tabiiy ko'rinadi (FR-KNW-006'ning o'zi ham aynan shu sababdan
frontend o'zgarishi talab qilmagan edi).

659 test (655 + 4: `test_citation.py`), barchasi real Postgres(+Redis)'da;
`ruff`/`mypy src/doda`/`mypy scripts` toza.
