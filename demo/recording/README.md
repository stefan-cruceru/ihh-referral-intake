# Lamplight presentation demo

[Watch or download the two-minute demo](https://github.com/stefan-cruceru/ihh-referral-intake/releases/tag/demo-lamplight-2026-10-17).
The release includes the 1080p film, 720p copy, cover, optional English and Spanish subtitles, source credits,
logo exports, a [sample resource handout PDF](../media/resource-handout.pdf) and a standalone interactive architecture map. These sources recreate its artwork,
practice-app recording and compositor.

**Referral-workflow recording revision:** `a8e52e5db69955a8a15ed3ceed6ac09f96a4fa02`.
The resource-plan/PDF insert uses the later `95e22a9d8b9a45806fce4b443b530679858e67f3` application.
Both recordings use synthetic practice workflows. The film follows
[project rules](../../CLAUDE.md), [bilingual requirements](../../docs/bilingual.md), and
[workflow and timing](../../docs/workflow-and-timing.md), with Sam’s Lamplight campaign and Public Sans.
The original event [submission](https://github.com/stefan-cruceru/ihh-referral-intake/blob/d4b772170dfca3cfcd2f90533f2cd41ba3f840c6/docs/submission.md),
[judging](https://github.com/stefan-cruceru/ihh-referral-intake/blob/d4b772170dfca3cfcd2f90533f2cd41ba3f840c6/docs/judging.md), and
[ground rules](https://github.com/stefan-cruceru/ihh-referral-intake/blob/d4b772170dfca3cfcd2f90533f2cd41ba3f840c6/docs/ground-rules.md)
remain in history after the starter-doc cleanup.

## The two-minute workflow

| Time | What the audience sees | Workflow improvement shown |
|---|---|---|
| 0:00–0:13 | Real-person stock footage and animated paper/clock/lamp artwork | Establishes the referral coordinator’s two-hour response target |
| 0:13–0:19 | Sam’s four-step welcome | Staff pick their role and see what they control before using the tool |
| 0:19–0:30 | The working queue, owners and deadlines | One visible place to track each referral and its next action |
| 0:30–0:46 | A stroke referral and the original page 11 | Staff check the underlying evidence when the form tells a different story |
| 0:46–1:00 | Rule-linked findings and unknowns | Conflicts and missing evidence remain visible for human review |
| 1:00–1:16 | Missing records, hospital questions and follow-up drafts | Staff can review one assembled request for the missing pieces |
| 1:16–1:32 | The same referral and draft in English and Spanish | The same work is available in either language; quotes stay original |
| 1:32–1:43 | A staff acceptance action and handoff drafts | The person’s decision connects to chart, census and site-email drafts |
| 1:43–1:47 | A separate fictional admin reviews the audit view | Who did what and when remains visible to the permitted role |
| 1:47–2:00 | People at work, a connected workflow and the lamp | Human authority and prototype limitations remain explicit |

The recording uses invented practice patients and made-up practice staff. Practice reviews come
from the organizers’ answer key and pass through the app’s checks; **this film does not demonstrate
live AI extraction**. Kipu, Microsoft sign-in and downstream IHH connections are practice flows.
Drafts require staff review. The film demonstrates no measured accuracy, measured time savings,
or clinical effectiveness. IHH bilingual review and staff accuracy validation remain pending.

## Recreate it

Use Python 3.12 or newer. Run commands from the repository root. Keep the virtual environment,
browser download, stock clips, recordings, generated fonts and final encodes in your session
scratchpad outside the repository. In the PowerShell examples, set `$demoScratch` to that existing
session scratch directory first. Do not use the repository, home directory or a new drive-root
folder as scratch.

If a later application revision retires the practice patients, run the practice app from the
recorded revision in a separate checkout, using the recording sources from this release.

```powershell
python -m venv "$demoScratch/venv"
& "$demoScratch/venv/Scripts/Activate.ps1"
python -m pip install -r app/requirements.txt -r demo/recording/requirements.txt
$env:PLAYWRIGHT_BROWSERS_PATH = "$demoScratch/browsers"
python -m playwright install chromium
python demo/recording/prepare_lamplight_fonts.py --destination "$demoScratch"
```

Download the two licensed clips from the source pages below into `$demoScratch/stock-footage/`,
using the listed filenames. The HTML reads the canonical repository logo and font directly;
`capture_lamplight.py` serves the stock files from the supplied external directory.

Start a **fresh local practice app** in another terminal, following the repository’s source-run
instructions. Use a dedicated settings directory so existing accounts or settings are preserved:

```powershell
& "$demoScratch/venv/Scripts/Activate.ps1"
$env:LOCALAPPDATA = "$demoScratch/app-settings"
$env:CAREBRIDGE_AUTH = "practice"
cd app
python -m carebridge serve 8780 --no-browser
```

Use the local URL printed by the app for `--app-url`. The capture script signs in as the invented
Avery lead, verifies practice authentication, refuses a queue containing non-demo cards, and then
resets the synthetic practice queue. Session cookies remain in memory. The small artwork server
starts and stops with the capture command.

```powershell
python demo/recording/capture_lamplight.py --app-url http://127.0.0.1:8780 --assets-dir "$demoScratch/stock-footage" --scratch "$demoScratch" --quick
python demo/recording/capture_lamplight.py --app-url http://127.0.0.1:8780 --assets-dir "$demoScratch/stock-footage" --scratch "$demoScratch" --output "$demoScratch/lamplight-raw.webm"
```

The capture prints a `video_offset` after finding the first clean frame. Use that number in the
render command. `--inspect` checks light, dark, color-vision and larger-text modes without
recording; `--quick` rehearses the full workflow without timeline waits. Neither output belongs
in git. Authentication must remain practice mode for this demonstration.

Reuse the released film’s audio track to preserve its exact narration and cue timing. The renderer
accepts an MP4 as `--audio`; FFmpeg selects its audio stream. No speech-service account, signed
media URL or downloaded narration manifest is required.

```powershell
gh release download demo-lamplight-2026-10-17 --repo stefan-cruceru/ihh-referral-intake --pattern "Lamplight-Demo-1080p.mp4" --dir "$demoScratch"
python demo/recording/render_lamplight.py --raw "$demoScratch/lamplight-raw.webm" --audio "$demoScratch/Lamplight-Demo-1080p.mp4" --timeline demo/recording/lamplight-timeline.json --scratch "$demoScratch" --video-offset 0 --resources-raw "$demoScratch/lamplight-resources.webm" --resources-offset 0 --cover-time 3 --output "$demoScratch/Lamplight - Remade.mp4"
python demo/recording/encode_lamplight_share.py --source "$demoScratch/Lamplight - Remade.mp4" --output "$demoScratch/Lamplight - Remade (720p).mp4"
```

Replace `--video-offset 0` with the reported value. The result is exactly 120 seconds at
1920 × 1080, 30 fps, H.264/AAC, with optional bilingual subtitle files and a cover PNG. Narration captions are not baked into the picture. Enable a single subtitle track in your player when needed. Rendering
removes its own temporary overlays and subtitle files. After viewing the whole result, check the
source page reveal, language switch, staff decision, caption timing and audio, then remove unused
scratch artifacts and stop the practice app. Browser load times may change between machines, so
the capture is reproducible as a workflow rather than guaranteed identical video bytes.

Export the interactive architecture map as one offline file, including its canonical lamp and
Public Sans license:

```powershell
python demo/recording/export_architecture.py --output "$demoScratch/Lamplight - Architecture.html"
```

## Sources and credits

| Asset | Source and local filename |
|---|---|
| Opening stock footage | [Doctor Using a Computer — Pavel Danilyuk](https://www.pexels.com/video/doctor-using-a-computer-6997946/), `coordinator-computer-pexels-6997946.mp4` |
| Closing stock footage | [Woman Working with Computer — Antoni Shkraba](https://www.pexels.com/video/woman-working-with-computer-8048240/), `team-computers-pexels-8048240.mp4` |
| Footage terms | [Pexels License](https://www.pexels.com/license/) |
| Narration | Synthesized Leslie preset, ElevenLabs `eleven_multilingual_v2` through Runway; source speed 1.05. The released mix preserves the final timing. |
| Quiet opening/closing underscore | Original synthesized sine-wave chords; no third-party music recording |
| Typography | Public Sans, [SIL Open Font License](../../app/carebridge/web/fonts/OFL.txt); canonical variable font stays in `app/carebridge/web/fonts/` |
| Logo and palette | [Lamplight campaign](../../campaign/README.md), refined canonical SVG in `campaign/logo/` |
| Captions | [English SRT](lamplight-en.srt), [Spanish SRT](lamplight-es.srt) and `lamplight-timeline.json` |

People in the stock footage are illustrative. They are not presented as IHH staff, patients or
endorsers. No stock footage, generated narration, raw recording, browser profile, cookies or API
credentials are included in this source folder. The full narration text is in the timeline.
