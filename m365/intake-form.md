# The hospital referral form

One Power Pages form, open to anyone with the link, with a CAPTCHA. The hospital fills it in and
uploads the packet in the same form. Every label is in English and Spanish: the form has a
language switch at the top, and the language picked is saved as the submitter's language for the
status emails.

Fields marked * are required. Column names refer to [referrals-table.md](referrals-table.md).

## 1. About you / Sobre usted

| Field (EN) | Campo (ES) | Type | Column |
| --- | --- | --- | --- |
| Your name * | Su nombre * | Text | `submitter_name` |
| Your role * | Su puesto * | Choice: Case manager, Social worker, Discharge planner, Nurse, Other / Administrador(a) de casos, Trabajador(a) social, Planificador(a) de alta, Enfermero(a), Otro | `submitter_role` |
| Hospital * | Hospital * | Choice list kept by IHH, plus "Other" | `hospital` |
| Unit or floor | Unidad o piso | Text | `hospital_unit` |
| Work email * (status updates go here) | Correo de trabajo * (aquí le mandamos las novedades) | Email | `submitter_email` |
| Work phone * | Teléfono de trabajo * | Phone | `submitter_phone` |
| Language for updates * | Idioma para las novedades * | Choice: English, Español | `submitter_lang` |

Help text under email / Texto de ayuda: "We email you each time this referral moves: received,
being reviewed, need more documents, and the decision." / "Le escribimos cada vez que este
referido avanza: recibido, en revisión, faltan documentos, y la decisión."

## 2. About the referral / Sobre el referido

| Field (EN) | Campo (ES) | Type | Column |
| --- | --- | --- | --- |
| Expected discharge * | Alta prevista * | Date and time, or "Not known yet" | `expected_discharge` |
| Why recuperative care? (short) * | ¿Por qué cuidado de recuperación? (breve) * | Text, 500 characters | `reason_short` |
| Insurance | Seguro médico | Choice: CalOptima, Other Medi-Cal, Other, Not known / CalOptima, Otro Medi-Cal, Otro, No se sabe | `insurance` |

**What the chart shows / Lo que dice el expediente.** One row each, from IHH's referral form
front page (`criteria/admission-criteria.json`, `referral_form_screen`). Answers: Yes, No,
Not sure / Sí, No, No estoy seguro(a). They help the coordinator sort the queue; the chart
still decides.

| Rule | EN | ES |
| --- | --- | --- |
| FORM-M1 | Unhoused, at risk of it, or going back to an unsafe place after the hospital | Sin vivienda, en riesgo, o volvería a un lugar inadecuado después del hospital |
| FORM-M2 | Medically and psychiatrically stable at discharge | Estable médica y psiquiátricamente al darle de alta |
| FORM-M3 | Alert and oriented x4 | Alerta y orientado(a) x4 |
| FORM-M4 | Can manage their own activities of daily living (ADLs) | Puede manejar sus actividades de la vida diaria (AVD) |
| FORM-M5 | Can take their own medicines with staff oversight | Puede tomar sus medicinas con supervisión del personal |
| FORM-M6 | Can walk 100 feet (with or without a device) and transfer on their own. IHH's newer rules MOB-3 and MOB-4 replace this one; the reader checks those | Puede caminar 100 pies (con o sin aparato) y trasladarse solo(a). Las reglas MOB-3 y MOB-4 de IHH reemplazan esta |

Field names in the form store these as `screen_m1` to `screen_m6`.

## 3. Documents / Documentos

One upload field, many files: PDF, TIFF, JPG or PNG. IT sets the size limit per file.

Help text lists the checklist from the referral form (`referral_checklist`), so the hospital
knows what to send / Lista de lo que debe mandar:

- DOC-1 IHH Referral Form / Formulario de referido de IHH
- DOC-2 Client's demographic page / Hoja de datos del paciente
- DOC-3 CalOptima form, LOA or authorization / Formulario, LOA o autorización de CalOptima
- DOC-4 H&P (history and physical) / Historia clínica y examen físico
- DOC-5 Current progress notes (if needed) / Notas de evolución recientes (si aplica)
- DOC-6 Vitals from the last 24 hours / Signos vitales de las últimas 24 horas
- DOC-7 Medication list / Lista de medicamentos
- DOC-8 PT/OT or nursing notes / Notas de terapia física/ocupacional o de enfermería
- DOC-9 Blood or wound culture (if needed) / Cultivo de sangre o de herida (si aplica)
- DOC-10 30-day supply of all medications / Medicinas para 30 días

A checkbox list with the same ten items, "Included in my upload / Incluido en lo que subí",
saves to `docs_claimed`. The reader checks the pages anyway: the claim is not the proof.

## 4. Before you send / Antes de enviar

- Checkbox * "I'm sending this for this patient's discharge planning, and it's accurate as far
  as I know." / "Mando esto para la planificación de alta de este paciente y, que yo sepa, es
  correcto."
- CAPTCHA.
- Button: **Send referral / Enviar referido**.

## After sending / Después de enviar

The page shows the case code and says what happens next. No patient details are shown back.

> **Referral received. Your case code is {case_code}.** We start reading it now and answer
> within 2 hours. We'll email {submitter_email} when it moves. Questions? Reply to that email
> and include the case code.
>
> **Recibimos el referido. Su código de caso es {case_code}.** Empezamos a leerlo ahora y
> respondemos en 2 horas. Le escribiremos a {submitter_email} cuando avance. ¿Preguntas?
> Responda a ese correo e incluya el código de caso.

## Settings in Power Pages

- **Table permissions:** anonymous web role gets **Create** on `Referrals` and on attachments
  (Notes). No Read, Write, Append to others, or Delete. A hospital can't see any referral,
  including its own, after sending.
- **Attachments:** Basic form > Attach file: on, multiple files, storage Notes (Dataverse) or
  Azure Blob in IHH's own subscription. Turn on the newer file upload (`EnhancedFileUpload`
  site setting) on older sites.
- **CAPTCHA:** on for anonymous users.
- **Case code:** set by flow 1 right after create (see [flows.md](flows.md)). The confirmation
  page reads it back with a short wait, or says "Your case code is on its way by email."
- **No patient data in the URL**, in page titles or in analytics. Turn off any web analytics on
  the site.
