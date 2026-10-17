"""ihh-care-bridge.exe [command]

  (no command)     open the app in your browser
  mcp              run as an MCP server on stdin/stdout (for Copilot / Claude Desktop)
  install          copy the exe to your user folder, add a Start menu shortcut, register with Copilot
  uninstall        undo install
  review FILE      review one packet and print the result (needs an API key)
  set-key          save a Claude API key in Windows Credential Manager
"""

import getpass
import sys


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else ""
    if cmd in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    if cmd == "mcp":
        from .mcp import serve_stdio

        serve_stdio()
        return 0
    if cmd == "install":
        from .install import install

        return install()
    if cmd == "uninstall":
        from .install import uninstall

        return uninstall()
    if cmd == "set-key":
        from . import config

        config.set_api_key(getpass.getpass("Claude API key (input hidden): "))
        print("Saved.")
        return 0
    if cmd == "review" and len(argv) > 1:
        from pathlib import Path

        from . import intake
        from .mcp import report_markdown
        from .pages import load_packet

        p = Path(argv[1])
        review = intake.Review(load_packet(p.read_bytes(), p.name), p.name)
        lang = argv[2] if len(argv) > 2 else "en"
        rep = intake.run(review)
        sys.stdout.reconfigure(encoding="utf-8")
        print(report_markdown(rep, lang))
        return 0
    from .webapp import serve

    port = int(argv[1]) if cmd == "serve" and len(argv) > 1 else 0
    serve(port=port, open_browser="--no-browser" not in argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
