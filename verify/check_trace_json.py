import json

from app.core.aes.engine import build_trace
from app.schemas.trace import AesKeyBits, AesMode

trace = build_trace(
    "3243f6a8885a308d313198a2e0370734",
    "2b7e151628aed2a6abf7158809cf4f3c",
    AesKeyBits.BITS_128,
    AesMode.ENCRYPT,
)
data = json.loads(trace.model_dump_json(by_alias=True))
print("top-level keys:", list(data.keys()))
print("step[0] keys:", list(data["steps"][0].keys()))
print("keySchedule[0] keys:", list(data["keySchedule"][0].keys()))
print("cell keys:", list(data["steps"][0]["cells"][0].keys()))
print("steps count:", len(data["steps"]))
print("output:", data["output"])
print("stateBefore len:", len(data["steps"][0]["stateBefore"]))
print()
print("step[1]:", json.dumps({k: v for k, v in data["steps"][1].items() if k != "cells"}, ensure_ascii=False))
print("cell[0]:", json.dumps(data["steps"][1]["cells"][0], ensure_ascii=False))