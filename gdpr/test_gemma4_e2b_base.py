import gc
import importlib.util
import os
from threading import Thread
from pathlib import Path

# Avoid a native Windows access violation in the async Transformers weight loader.
os.environ.setdefault("HF_DEACTIVATE_ASYNC_LOAD", "1")

import gradio as gr
import torch
from transformers import (
    AutoModelForCausalLM,
    AutoProcessor,
    BitsAndBytesConfig,
    StoppingCriteria,
    StoppingCriteriaList,
    TextIteratorStreamer,
)


ROOT = Path(__file__).resolve().parent
BASE_MODEL = os.getenv("GEMMA4_BASE_MODEL", "google/gemma-4-E2B-it")

DEVICE_MAP_MODE = os.getenv("GEMMA4_DEVICE_MAP", "auto").strip().lower()
GPU_MAX_MEMORY = os.getenv("GEMMA4_GPU_MAX_MEMORY", "7GiB")
CPU_MAX_MEMORY = os.getenv("GEMMA4_CPU_MAX_MEMORY", "14GiB")
SERVER_NAME = os.getenv("GRADIO_SERVER_NAME", "127.0.0.1")
SERVER_PORT = int(os.getenv("GRADIO_SERVER_PORT", "7860"))

SYSTEM_PROMPT = (
    "Convert one legal article into a faithful XML process model.\n"
    "Use only the provided legal text.\n"
    "Do not invent legal logic.\n"
    "Output only valid XML with root <processModel>."
)

USER_PROMPT_PREFIX = (
    "Generate process-structure XML from this legal text.\n"
    "Model only process-relevant legal logic.\n"
    "Use short task names, question-style exclusive gateways, and labeled exclusive branches.\n"
    "Use this exact top-level order:\n"
    "<pools><tasks><events><gateways><sequenceFlows><messageFlows>\n"
    "Text:\n\n"
)


def ensure_gemma4_transformers_support() -> None:
    if importlib.util.find_spec("transformers.models.gemma4") is None:
        raise RuntimeError(
            "This environment's transformers build does not support Gemma4 yet. "
            "Install a Gemma4-capable release, for example: "
            "python -m pip install --upgrade \"transformers>=5.6,<5.7\""
        )


def cuda_report() -> str:
    if not torch.cuda.is_available():
        return "CUDA not available; CPU inference will be very slow."
    props = torch.cuda.get_device_properties(0)
    free_bytes, total_bytes = torch.cuda.mem_get_info()
    return (
        f"GPU: {props.name} | "
        f"VRAM free: {free_bytes / 1024**3:.2f} GiB / {total_bytes / 1024**3:.2f} GiB | "
        f"CUDA: {torch.version.cuda}"
    )


def pick_compute_dtype() -> torch.dtype:
    if not torch.cuda.is_available():
        return torch.float32
    major, _ = torch.cuda.get_device_capability(0)
    return torch.bfloat16 if major >= 8 else torch.float16


def load_base_model(compute_dtype: torch.dtype):
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_quant_storage=compute_dtype,
    )

    load_kwargs = {
        "quantization_config": bnb_config,
        "attn_implementation": "sdpa",
        "low_cpu_mem_usage": True,
        "dtype": compute_dtype,
    }

    if torch.cuda.is_available():
        if DEVICE_MAP_MODE in {"cuda", "gpu", "single_gpu"}:
            load_kwargs["device_map"] = {"": 0}
        elif DEVICE_MAP_MODE == "auto":
            load_kwargs["device_map"] = "auto"
            load_kwargs["max_memory"] = {0: GPU_MAX_MEMORY, "cpu": CPU_MAX_MEMORY}
            load_kwargs["offload_folder"] = str(ROOT / "offload")
        else:
            raise ValueError("GEMMA4_DEVICE_MAP must be 'cuda' or 'auto'.")
    else:
        load_kwargs["device_map"] = "cpu"
        load_kwargs["max_memory"] = {"cpu": CPU_MAX_MEMORY}

    try:
        return AutoModelForCausalLM.from_pretrained(BASE_MODEL, **load_kwargs)
    except TypeError as exc:
        if "dtype" not in str(exc):
            raise
        load_kwargs["torch_dtype"] = load_kwargs.pop("dtype")
        return AutoModelForCausalLM.from_pretrained(BASE_MODEL, **load_kwargs)


compute_dtype = pick_compute_dtype()

print(cuda_report())
print(f"Base model: {BASE_MODEL}")
print("Adapter: none")
print(f"Compute dtype: {compute_dtype}")
print(f"Device map mode: {DEVICE_MAP_MODE}")
if DEVICE_MAP_MODE == "auto":
    print(f"GPU max memory: {GPU_MAX_MEMORY} | CPU max memory: {CPU_MAX_MEMORY}")

ensure_gemma4_transformers_support()
processor = AutoProcessor.from_pretrained(
    BASE_MODEL,
    padding_side="left",
    extra_special_tokens={"video_token": "<|video|>"},
)
tokenizer = processor.tokenizer
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

model = load_base_model(compute_dtype)
model.eval()
model.config.use_cache = True

print("Device map:", getattr(model, "hf_device_map", None))
if torch.cuda.is_available():
    print(f"Loaded footprint: {model.get_memory_footprint() / 1024**3:.2f} GiB")


def build_prompt(legal_text: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_PROMPT_PREFIX + legal_text.strip()},
    ]

    try:
        return processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    except Exception:
        return (
            "<bos><|turn>system\n"
            f"{SYSTEM_PROMPT}<turn|>\n"
            "<|turn>user\n"
            f"{USER_PROMPT_PREFIX}{legal_text.strip()}<turn|>\n"
            "<|turn>model\n"
        )


def cleanup_output(text: str) -> str:
    closing_tag = "</processModel>"
    if closing_tag in text:
        text = text.split(closing_tag, 1)[0] + closing_tag
    for stop_token in ["<turn|>", "<|turn>", tokenizer.eos_token or ""]:
        if stop_token and stop_token in text:
            text = text.split(stop_token, 1)[0]
    return text.strip()


class StopAfterText(StoppingCriteria):
    def __init__(self, tokenizer, stop_texts):
        self.tokenizer = tokenizer
        self.stop_texts = tuple(stop_texts)
        self.max_stop_chars = max(len(text) for text in self.stop_texts)

    def __call__(self, input_ids, scores, **kwargs):
        suffix_token_count = min(input_ids.shape[-1], 64)
        suffix = self.tokenizer.decode(input_ids[0, -suffix_token_count:], skip_special_tokens=False)
        suffix = suffix[-(self.max_stop_chars + 32) :]
        return any(stop_text in suffix for stop_text in self.stop_texts)


def memory_summary() -> str:
    if not torch.cuda.is_available():
        return "cpu"
    allocated = torch.cuda.memory_allocated() / 1024**3
    reserved = torch.cuda.memory_reserved() / 1024**3
    free_bytes, total_bytes = torch.cuda.mem_get_info()
    return (
        f"allocated={allocated:.2f} GiB | reserved={reserved:.2f} GiB | "
        f"free={free_bytes / 1024**3:.2f}/{total_bytes / 1024**3:.2f} GiB"
    )


def generate_xml(legal_text, max_new_tokens, temperature, top_p, repetition_penalty):
    legal_text = (legal_text or "").strip()
    if not legal_text:
        yield "", "No input text."
        return

    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    prompt = build_prompt(legal_text)
    inputs = processor(text=prompt, return_tensors="pt")
    input_tokens = int(inputs["input_ids"].shape[-1])
    input_device = "cuda" if torch.cuda.is_available() else "cpu"
    inputs = {key: value.to(input_device) for key, value in inputs.items()}

    do_sample = float(temperature) > 0.001
    generation_kwargs = {
        **inputs,
        "max_new_tokens": int(max_new_tokens),
        "do_sample": do_sample,
        "repetition_penalty": float(repetition_penalty),
        "pad_token_id": tokenizer.pad_token_id or tokenizer.eos_token_id,
        "eos_token_id": tokenizer.eos_token_id,
        "use_cache": True,
        "stopping_criteria": StoppingCriteriaList([StopAfterText(tokenizer, ["</processModel>"])]),
    }
    if do_sample:
        generation_kwargs["temperature"] = float(temperature)
        generation_kwargs["top_p"] = float(top_p)

    streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
    generation_kwargs["streamer"] = streamer
    errors = []
    chunks = []

    def run_generation():
        try:
            with torch.inference_mode():
                model.generate(**generation_kwargs)
        except Exception as exc:
            errors.append(exc)
            streamer.on_finalized_text(f"\n\nGeneration error: {exc}", stream_end=True)

    thread = Thread(target=run_generation, daemon=True)
    thread.start()

    for new_text in streamer:
        chunks.append(new_text)
        output_text = cleanup_output("".join(chunks))
        generated_tokens = len(tokenizer(output_text, add_special_tokens=False)["input_ids"])
        stats = (
            f"input_tokens={input_tokens} | generated_tokens~={generated_tokens} | "
            f"adapter=none | model={BASE_MODEL} | streaming | {memory_summary()}"
        )
        yield output_text, stats

    thread.join()
    output_text = cleanup_output("".join(chunks))
    generated_tokens = len(tokenizer(output_text, add_special_tokens=False)["input_ids"])
    status = "error" if errors else "done"
    stats = (
        f"input_tokens={input_tokens} | generated_tokens~={generated_tokens} | "
        f"adapter=none | model={BASE_MODEL} | {status} | {memory_summary()}"
    )
    yield output_text, stats


with gr.Blocks(title="Gemma 4 E2B Base Model Test") as demo:
    gr.Markdown("# Gemma 4 E2B Base Model Test")
    with gr.Row():
        with gr.Column(scale=1):
            legal_text = gr.Textbox(
                label="Legal text",
                lines=18,
                placeholder="Paste a legal article here...",
            )
            with gr.Row():
                max_new_tokens = gr.Slider(128, 4096, value=1024, step=128, label="max_new_tokens")
                temperature = gr.Slider(0.0, 1.2, value=0.0, step=0.05, label="temperature")
            with gr.Row():
                top_p = gr.Slider(0.1, 1.0, value=0.9, step=0.05, label="top_p")
                repetition_penalty = gr.Slider(1.0, 1.3, value=1.05, step=0.01, label="repetition_penalty")
            run_button = gr.Button("Generate XML", variant="primary")
        with gr.Column(scale=1):
            xml_output = gr.Textbox(label="Generated XML", lines=24, max_lines=32)
            stats_output = gr.Textbox(label="Run stats", interactive=False)

    run_button.click(
        fn=generate_xml,
        inputs=[legal_text, max_new_tokens, temperature, top_p, repetition_penalty],
        outputs=[xml_output, stats_output],
    )


if __name__ == "__main__":
    demo.queue()
    demo.launch(server_name=SERVER_NAME, server_port=SERVER_PORT, share=False)
