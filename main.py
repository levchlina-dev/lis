import sys
from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python main.py <channel>")
        print("Channels: cli, http, telegram")
        sys.exit(1)

    channel = sys.argv[1].lower()

    if channel == "cli":
        from channels.cli import run
        run()

    elif channel == "http":
        import uvicorn
        from channels.http import app
        host = "0.0.0.0"
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
        print(f"Starting HTTP channel on http://{host}:{port}")
        uvicorn.run(app, host=host, port=port)

    elif channel == "telegram":
        from channels.telegram import run
        run()

    elif channel == "pc":
        from channels.pc import run
        run()

    else:
        print(f"Unknown channel: {channel!r}")
        print("Available channels: cli, http, telegram, pc")
        sys.exit(1)


if __name__ == "__main__":
    main()
