import json, torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from src.serve.core import MODEL_DIR
tok = AutoTokenizer.from_pretrained(MODEL_DIR / "merged")
r = [json.loads(l) for l in open("data/sft/gold.jsonl")][0]
enc = tok(tok.apply_chat_template([{"role": "user", "content": r["prompt"]}], tokenize=False, add_generation_prompt=True), return_tensors="pt")
m = AutoModelForCausalLM.from_pretrained(MODEL_DIR / "merged", torch_dtype=torch.float32).eval()
errs, hooks = {}, []
def hook(name, mod):
    def f(_, inp, out):
        q = mod; q.qconfig = torch.ao.quantization.default_dynamic_qconfig
        qo = torch.ao.nn.quantized.dynamic.Linear.from_float(q)(inp[0])
        errs[name] = (float((out - qo).norm() / out.norm()), float(inp[0].abs().max()))
    return f
for n, mod in m.named_modules():
    if isinstance(mod, torch.nn.Linear):
        hooks.append(mod.register_forward_hook(hook(n, mod)))
with torch.inference_mode():
    m(**enc)
worst = sorted(errs.items(), key=lambda kv: -kv[1][0])
for n, (e, mx) in worst[:12]:
    print(f"{n:40s} rel_err {e:.3f}  max|x| {mx:.0f}")
by = {}
for n, (e, mx) in errs.items():
    by.setdefault(n.split(".")[-1], []).append(e)
print({k: round(max(v), 3) for k, v in by.items()})
