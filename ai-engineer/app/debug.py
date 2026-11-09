import asyncio
import sys

import uvicorn


def main() -> None:
    config = uvicorn.Config("app.main:app", host="127.0.0.1", port=8001)
    server = uvicorn.Server(config)
    if sys.platform == "win32":
        asyncio.run(server.serve(), loop_factory=asyncio.SelectorEventLoop)
    else:
        server.run()


if __name__ == "__main__":
    main()
