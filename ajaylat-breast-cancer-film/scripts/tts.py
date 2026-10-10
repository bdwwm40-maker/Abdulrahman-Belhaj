import sys, certifi
certifi.where = lambda: "/root/.ccr/ca-bundle.crt"
import asyncio, edge_tts
voice, rate, pitch, text, out = sys.argv[1:6]
async def m():
    await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(out)
asyncio.run(m())
