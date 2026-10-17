# The public web demo

`build.py` makes the GitHub Pages site. `.github/workflows/pages.yml` runs it on every push to `main`.

The working app on that site is the same Python code as the exe. It runs inside the browser with
[Pyodide](https://pyodide.org):

- `sw.js` is a service worker. It acts as the server for every page under `app/`. On first use it loads
  Pyodide, Pillow, SQLite and fpdf2, unpacks `carebridge.zip`, and imports `bridge.py`.
- `bridge.py` hands each request to `webapp.Handler`, the same handler the exe uses, with no socket.
- The app was written to live at `/`. `sw.js` moves its links under `app/` and keeps the practice
  sign-in cookie itself, since a service worker can't set real cookies.

It has no API key, so it does not read the pages of a referral you add, and nothing leaves the browser.
State lives in the service worker's memory: if the browser stops the worker, the board starts fresh.

Build and try it locally:

```
pip install markdown
python app/pages/build.py _site/ihh-referral-intake
python -m http.server 8811 --directory _site
```

Then open http://127.0.0.1:8811/ihh-referral-intake/.
