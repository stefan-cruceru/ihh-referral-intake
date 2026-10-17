# English and Spanish

Team decision, October 17: **everything a person sees in our solution works in English and in
Spanish.** This file says what that covers, how to build it, and which words to use.

The team's working notes in `docs/` stay in English. They are for us, not for IHH staff or
hospitals.

Clients who need health information explained, or a language beyond English and Spanish, go to
My Happy Health, which covers about 30 languages (`docs/myhappyhealth.md`).

---

## 1. What has to be bilingual

| Piece | How |
|---|---|
| Every screen: the queue, the 2-hour tracker, cards, buttons, alerts, statuses | One **English / Español** switch per user. English by default |
| The review screen: the two gates, rule results, flags, open questions | Claude writes the summary in the chosen language. Rule IDs stay the same in both |
| Drafts to hospitals: missing items, chase nudges, supervisor escalation, the decision reply | Drafted in the chosen language, with one click for the other language. A person picks one and sends it |
| The status a hospital can check | Both languages on the same page |
| The three handoffs after a yes | The ops email follows the switch. The Kipu fields and the census row keep the field names IHH's systems use, so they paste in cleanly. Labels on screen follow the switch |
| The demo | Show one card and one draft in English, flip the switch, show the same card and draft in Spanish |
| The team README | A short **Resumen en español** near the top: the problem, what we built, how to run it |

---

## 2. Rules for the Spanish side

- **Quotes are never translated in place.** Evidence quotes stay word for word as they appear on the
  page, because the verifier checks them against the page. Put the translation underneath, labeled
  "Traducción" or "Translation".
- **If a page is in Spanish**, Claude reads it the same way and quotes it in Spanish.
- **Preferred language** is a field on IHH's referral form
  (`challenges/1-referral-intake/criteria/referral-form-and-checklist.md`). Show it on the card and
  carry it into the ops email, so the site knows before the patient arrives. Not on the form:
  "unknown / desconocido". Blacked out: "removed for privacy / eliminado por privacidad".
- **IHH's English criteria are the source.** Spanish rule text is a translation for reading, marked
  "traducido". If the two ever seem to say different things, the English governs.
- **Same quality control in both languages.** The verifier runs on Spanish output too. A Spanish
  draft must list exactly the same missing items (same DOC IDs) as the English one.
- **Label AI translations:** "Borrador traducido por IA. Revíselo antes de enviarlo." / "AI-translated
  draft. Check before sending." Nothing is sent automatically, in either language.
- **No medical, legal or immigration advice** in either language. Point to staff.
- **Before any pilot, a bilingual IHH staff member reviews** the word list and the draft templates.
  Our translations are a starting point, not a final version.

---

## 3. How to build it (Streamlit)

- **No hard-coded English in the UI.** Keep every on-screen string in one file, for example
  `app/strings.json`, with an `en` and an `es` value for each key.
- **One switch.** `st.session_state["lang"]` holds `"en"` or `"es"`. A toggle in the sidebar sets
  it.
- **Data stays language-free.** Statuses are codes in the data (`met`, `not_met`, `cant_tell`,
  `not_applicable`, `needs_info`, `missing`, `unverified`) and become words only on screen. The rule
  pass, the verifier and the eval harness never depend on which language is showing.
- **Pass the language into every prompt that writes something a person reads:** "Write in
  {English|Spanish}. Keep every quote word for word in its original language." Facts, rule IDs and
  page numbers come back as structured JSON, same as today.
- **Test:** run one packet in English and once in Spanish. Rule IDs, statuses, page numbers and the
  missing-items list must match exactly. Only the wording changes.

---

## 4. Word list

Check these with a bilingual IHH staff member before a pilot.

| English | Español |
|---|---|
| Received | Recibido |
| Needs info | Falta información |
| Clinical check | En revisión clínica |
| Likely no: sent to the clinical line | Probable rechazo: enviado a revisión clínica |
| Intake cleared. Do not discharge yet. | Admisión preliminar aprobada. Todavía no dé de alta al paciente. |
| Accepted. OK to discharge. | Aceptado. Ya puede dar de alta al paciente. |
| Denied | Denegado |
| Withdrawn | Retirado |
| Can care for themselves | Puede cuidarse por sí mismo/a |
| Behaviorally stable | Estable en su conducta |
| Met / Not met / Can't tell / Not applicable | Cumple / No cumple / No se puede determinar / No aplica |
| Missing | Falta |
| Unknown | Desconocido |
| Removed for privacy | Eliminado por privacidad |
| Unverified | Sin verificar |
| Time left | Tiempo restante |
| Owner | Responsable |
| Hand off | Reasignar |
| Draft. Not sent. | Borrador. No enviado. |
| Preferred language | Idioma preferido |
| Referral | Referido |
| Case manager | Administrador/a de casos |
| Discharge | Alta |
| Recuperative care | Cuidado recuperativo |
| Translation | Traducción |
