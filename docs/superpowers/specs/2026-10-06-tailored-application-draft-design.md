# Bozza candidatura su misura (CV adattato + lettera + Gmail)

Data: 2026-10-06

## Obiettivo
Da un annuncio (link o testo) generare in Gmail una **bozza** con lettera nel corpo e **PDF del CV adattato** allegato. L'utente rivede e preme Invia. Nessun invio automatico.

## Decisioni
- CV allegato: **PDF**.
- Adattamento CV: selezione e riordino di esperienze/skill + riscrittura con le keyword dell'annuncio. **Nessuna informazione inventata.**
- Link annuncio: scraping automatico; se non leggibile (login wall) l'utente incolla il testo.
- Inserzionista: `recruiter` | `direct`, rilevato dall'AI, correggibile dall'utente. Cambia il tono della lettera.
- Destinatario: estratto dall'annuncio se presente, altrimenti vuoto.
- Pipeline unica nel flusso Candidature (`JobApplication`); il bottone bozza del Market Scout la riusa.

## Dati (`job_applications`)
Nuove colonne: `source_url` (str, null), `advertiser_type` (str, null: `recruiter`/`direct`), `contact_email` (str, null), `tailored_cv` (Text JSON `ParsedCV`, null), `draft_url` (str, null), `draft_status` (str, default `idle`). Migrazione in `core/database.py` come per le colonne esistenti.

## Componenti
1. **`services/job_fetcher.py`** — `fetch_job_posting(url) -> {text, company?, role?, contact_email?}`. Scarica la pagina, estrae il testo. Se vuoto/login wall solleva `JobFetchError` e l'API risponde 422 con messaggio "incolla il testo".
2. **Estrazione metadati** — chiamata `chat()` (mai client diretti) che dal testo ricava azienda, ruolo, `advertiser_type`, email di contatto.
3. **`agents/cv_tailor/`** (prompt.md + agent.py, sul modello di `cv_expert`) — input `ParsedCV` base + testo annuncio, output `ParsedCV` adattato.
   - **Guardia anti-invenzione** (codice, non solo prompt): ogni azienda, titolo, data, titolo di studio e tecnologia dell'output deve esistere nel CV base; altrimenti l'elemento viene scartato e loggato, o l'operazione fallisce con `CVTailorError`.
4. **`services/cv_pdf.py`** — `render_cv_pdf(ParsedCV) -> bytes` da template. Libreria scelta nel piano (ReportLab vs WeasyPrint, compatibile con Windows e srvSviluppo).
5. **`agents/cover_letter`** — riceve `advertiser_type`: recruiter = più breve, su profilo e disponibilità; direct = più mirata su azienda e ruolo.
6. **`services/gmail_service.create_draft`** — estesa a MIME multipart: `to` opzionale, corpo, allegato PDF (`attachments: list[tuple[filename, bytes]]`). Label CareerOS invariata.
7. **Endpoint** (`applications`):
   - `POST /applications/` accetta `source_url` o testo; salva i metadati.
   - `PATCH /applications/{id}` per correggere `advertiser_type`/`contact_email`.
   - `POST /applications/{id}/draft` (202, background): tailor → lettera → PDF → bozza Gmail → salva `draft_url`, `draft_status`.
   - Market Scout `/opportunities/{id}/draft` delega alla stessa pipeline.
8. **Frontend** — form Candidature: campo link + fallback testo, selettore recruiter/diretto con valore rilevato, bottone "Crea bozza Gmail", stato e link alla bozza.

## Flusso
link → fetch → metadati (azienda, ruolo, tipo, email) → utente conferma/corregge → tailor CV (+guardia) → lettera col tono giusto → PDF → bozza Gmail con allegato → utente invia a mano.

## Errori
- Fetch fallito: 422, UI chiede il testo.
- Gmail non autenticato (`RuntimeError`): `draft_status=error`, messaggio in UI.
- Guardia anti-invenzione: elementi non verificabili scartati; se il CV risulta vuoto/incoerente, `error`.
- Stati visibili come per cover letter (`idle/generating/ready/error`).

## Test
- Guardia: CV adattato con azienda/tecnologia inventata viene rifiutato; con solo riordino/riscrittura passa.
- `job_fetcher`: pagina valida, pagina vuota/login wall, estrazione email.
- `create_draft`: MIME multipart con allegato e `to` vuoto/valorizzato (Gmail mockato).
- Tono lettera: prompt diverso per `recruiter` vs `direct`.

## Fuori scope
Invio automatico, DOCX, scraping autenticato (LinkedIn), modifica del CV base.
