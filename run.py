"""Launch the local app. Install requirements.txt first."""

import argparse
import socket
import threading
import webbrowser


def main():
    parser = argparse.ArgumentParser(
        description="DamnLens AI Agent local document-to-Excel agent"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Explicit port; otherwise select a free port from 8765-8784",
    )
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    try:
        import uvicorn
    except ImportError:
        raise SystemExit(
            "Install dependencies first: python -m pip install -r requirements.txt"
        ) from None
    listener = None
    ports = [args.port] if args.port is not None else range(8765, 8785)
    for port in ports:
        if not 1 <= port <= 65535:
            raise SystemExit("Port must be between 1 and 65535.")
        candidate = socket.socket()
        try:
            candidate.bind(("127.0.0.1", port))
            listener = candidate
            break
        except OSError:
            candidate.close()
    if listener is None:
        raise SystemExit(
            "The requested port is busy. Close the other app or use --port 8786."
        )
    url = f"http://127.0.0.1:{listener.getsockname()[1]}"
    print(
        f"\nDamnLens AI Agent is starting at {url}\nLocal processing is the default. Optional Gemini sends selected pages to Google after opt-in. Press Ctrl+C to stop.\n"
    )
    config = uvicorn.Config(
        "app.main:app",
        host="127.0.0.1",
        port=listener.getsockname()[1],
        log_level="info",
    )
    server = uvicorn.Server(config)
    if not args.no_browser:

        def open_when_ready():
            import time

            for _ in range(200):
                if server.started:
                    webbrowser.open(url)
                    return
                if server.should_exit:
                    return
                time.sleep(0.1)

        threading.Thread(target=open_when_ready, daemon=True).start()
    try:
        server.run(sockets=[listener])
    finally:
        listener.close()


if __name__ == "__main__":
    main()
