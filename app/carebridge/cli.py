"""ihh-care-bridge.exe [command]

  (no command)     open the app in your browser
  mcp              run as an MCP server on stdin/stdout (for Copilot / Claude Desktop)
  install          copy the exe to your user folder, add a Start menu shortcut, register with Copilot
  uninstall        undo install
  review FILE      review one packet (PDF/TIFF, or a saved .eml email) and print the result (needs an API key)
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

        from . import guard, intake, mail
        from .mcp import report_markdown

        p = Path(argv[1])
        data, name = p.read_bytes(), p.name
        sys.stdout.reconfigure(encoding="utf-8")
        if p.suffix.lower() == ".eml":
            got = mail.packet_from_eml(data)
            print("\n".join(mail.summary_lines(got)) + "\n")
            if not got["pdf"]:
                print("Nothing in this email can be reviewed: no usable text or attachment.")
                return 1
            data, name = got["pdf"], p.stem + ".pdf"
        try:
            review = intake.review_file(data, name)
        except guard.Blocked as e:
            print(f"Blocked by the security check ({e}). The file was not opened.")
            return 1
        lang = argv[2] if len(argv) > 2 else "en"
        rep = intake.run(review)
        print(report_markdown(rep, lang))
        return 0
    from .webapp import serve

    port = int(argv[1]) if cmd == "serve" and len(argv) > 1 else 0
    serve(port=port, open_browser="--no-browser" not in argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
