"""Synchronous bridge to an MCP server over stdio using the official MCP Python SDK client."""
import asyncio, sys, threading, json
from concurrent.futures import Future as concurrent_future
from mcp import Client, StdioServerParameters
from . import config

class MCPBridge:
    def __init__(self, server_path=None, env=None):
        import os
        env = {**(env or {}), "STUDY_DB": config.STUDY_DB, "PATH": os.environ.get("PATH", "")}
        self.params = StdioServerParameters(command=sys.executable, args=[str(server_path or config.MCP_SERVER)], env=env, cwd=str(config.ROOT))
        self.loop = asyncio.new_event_loop(); self.client = None; self._stack = None; self.log = []
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True); self.thread.start()
    def _run(self, coro, timeout=30):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)
    def start(self):
        ready = concurrent_future()
        async def _main():  # enter and exit the client in ONE task (anyio cancel-scope requirement)
            try:
                async with Client(self.params) as cl:
                    self.client = cl
                    res = await cl.list_tools()
                    self._stop = asyncio.Event()
                    ready.set_result(res)
                    await self._stop.wait()
            except Exception as e:
                if not ready.done(): ready.set_exception(e)
        self._main = asyncio.run_coroutine_threadsafe(_main(), self.loop)
        res = ready.result(60)
        self.tools = [{"name": t.name, "description": t.description or "", "parameters": t.input_schema} for t in res.tools]
        return self.tools
    def call(self, name, arguments):
        async def _c():
            return await self.client.call_tool(name, arguments)
        try:
            r = self._run(_c())
        except Exception as e:
            out = {"ok": False, "error": f"MCP transport error: {e}"}
            self.log.append({"tool": name, "args": arguments, "result": out}); return out
        text = " ".join(getattr(b, "text", "") for b in r.content)
        if r.is_error: out = {"ok": False, "error": text}
        else:
            data = getattr(r, "structured_content", None)
            if data is None:
                try: data = json.loads(text)
                except Exception: data = {"text": text}
            out = {"ok": True, "data": data}
        self.log.append({"tool": name, "args": arguments, "result": out})
        return out
    def close(self):
        if getattr(self, "_stop", None):
            self.loop.call_soon_threadsafe(self._stop.set)
            try: self._main.result(15)
            except Exception: pass
        self.loop.call_soon_threadsafe(self.loop.stop)
