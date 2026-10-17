# Demo

Everything here is for showing Lamplight, not for running it at IHH. The app itself is in
[`app/`](../app). Everything here is made up.

| Folder | What it is |
|---|---|
| [`synthetic/`](synthetic/README.md) | The 10 practice patients (S01 to S10): invented packets, page text and an answer key |
| `attack/` | A test packet with hidden instructions, to show the security hold |
| `inbox.json` | The practice referrals the demo board starts with |
| [`pages/`](pages/README.md) | The public demo site on GitHub Pages: the real app running in the browser, practice patients only |
| `media/` | The 2-minute demo video, its cover and its English and Spanish subtitles |

The app finds this folder by itself: `from demo import synthetic` works from a source checkout,
and the exe build and the Pages site bundle what they need from here.
