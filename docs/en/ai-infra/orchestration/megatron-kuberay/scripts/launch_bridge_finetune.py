#!/usr/bin/env python3
# SPDX-License-Identifier: MIT-0
"""LoRA fine-tune a Hugging Face model with Megatron Bridge on one KubeRay GPU worker.

Megatron Bridge trains with `torchrun`; it does not need Ray. Ray's job here is
orchestration on the KubeRay cluster:

  1. Place one launcher actor on the GPU worker, holding all of its GPUs.
  2. Inside that actor:
       a. download the base model from the Hugging Face Hub into HF_HOME
          (a persistent volume, so re-runs skip the download),
       b. run `torchrun --nproc_per_node <gpus> run_recipe.py --mode lora ...`,
          which loads the HF weights directly (no conversion step), and
       c. optionally export the LoRA adapter to Hugging Face PEFT format.
  3. Stream all output to the Ray job log, and stop torchrun cleanly if the
     job is cancelled (`kubectl delete rayjob`), so no process keeps the GPUs.

Anything this script does not recognise is passed straight to run_recipe.py
after the defaults below, e.g. `train.train_iters=200` or `--lr 2e-4`.

Use --dry-run to print the commands without needing Ray, GPUs or a download.
"""
import argparse
import os
import shlex
import signal
import subprocess
import sys

BRIDGE_DIR = os.environ.get("MEGATRON_BRIDGE_DIR", "/opt/Megatron-Bridge")

# Model presets: Megatron Bridge recipe stem -> Hugging Face repo + revision.
# The revision matches the one pinned inside the Megatron Bridge 0.6.x recipe,
# so the weights, config and tokenizer all come from the same snapshot.
MODELS = {
    "qwen3_8b": ("Qwen/Qwen3-8B", "b968826d9c46dd6066d109eabc6255188de91218"),
}


def parse_args(argv=None):
    # allow_abbrev=False: never let a pass-through run_recipe.py flag (e.g.
    # --save_interval) be swallowed as an abbreviation of one of ours.
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], allow_abbrev=False)
    p.add_argument("--model", default="qwen3_8b", choices=sorted(MODELS),
                   help="Megatron Bridge recipe stem (selects <model>_peft_config)")
    p.add_argument("--gpus", type=int, default=4, help="GPUs on the worker node")
    p.add_argument("--cpus", type=int, default=32,
                   help="CPUs the launcher actor reserves (must fit in the worker)")
    p.add_argument("--tp", type=int, default=1,
                   help="tensor-parallel size; keep 1 on GPUs without NVLink")
    p.add_argument("--max-steps", type=int, default=100)
    p.add_argument("--global-batch-size", type=int, default=32)
    p.add_argument("--micro-batch-size", type=int, default=1)
    p.add_argument("--save-dir", default="/data/checkpoints/qwen3-8b-lora")
    p.add_argument("--export-dir", default="/data/adapters/qwen3-8b-lora",
                   help="where the HF PEFT adapter is written")
    p.add_argument("--no-export", action="store_true",
                   help="skip exporting the adapter after training")
    p.add_argument("--placement-timeout", type=int, default=1800,
                   help="seconds to wait for the GPU worker to join the cluster")
    p.add_argument("--dry-run", action="store_true",
                   help="print the commands and exit (no Ray, GPUs or download)")
    return p.parse_known_args(argv)


def check_layout(a):
    if a.gpus % a.tp:
        sys.exit(f"error: --gpus {a.gpus} is not divisible by --tp {a.tp}")
    dp = a.gpus // a.tp
    if a.global_batch_size % (a.micro_batch_size * dp):
        sys.exit(f"error: global batch {a.global_batch_size} must be divisible by "
                 f"micro_batch*dp = {a.micro_batch_size}*{dp}")
    accum = a.global_batch_size // (a.micro_batch_size * dp)
    print(f"[launcher] {a.model}: {a.gpus} GPUs | TP={a.tp} DP={dp} | global batch "
          f"{a.global_batch_size} = micro {a.micro_batch_size} x DP {dp} x "
          f"{accum} accumulation steps | {a.max_steps} steps", flush=True)


def train_command(a, hf_path, extra):
    return [
        sys.executable, "-m", "torch.distributed.run",
        "--standalone", "--nproc_per_node", str(a.gpus),
        f"{BRIDGE_DIR}/scripts/training/run_recipe.py",
        "--model", a.model, "--mode", "lora",
        # Local HF directory: Megatron Bridge detects config.json + safetensors
        # and converts the weights to Megatron format in memory at startup.
        "--pretrained_checkpoint", hf_path,
        "--save_dir", a.save_dir,
        "-tp", str(a.tp),
        "-ms", str(a.max_steps),
        "-gb", str(a.global_batch_size),
        "-mb", str(a.micro_batch_size),
        # The recipe pads each packed sequence to a multiple of 4 (tuned for
        # H100). That leaves padding BETWEEN sequences in the packed (THD)
        # batch, and on L40S (sm_89) Transformer Engine has no attention
        # backend for it: FlashAttention 2 and unfused attention reject
        # padding between sequences, and cuDNN fused attention does not
        # support the input on sm_89. Without padding, FlashAttention 2 is
        # used. With TP=1 and CP=1, Megatron Bridge needs no alignment here.
        "dataset.offline_packing_specs.pad_seq_to_mult=1",
        *extra,
    ]


def latest_iteration_dir(save_dir):
    """Return the newest complete iter_NNNNNNN checkpoint under save_dir, or None.

    The adapter exporter must be given an iteration directory: despite its
    docstring, Megatron Bridge 0.6.x passes --lora-checkpoint straight to
    dist_checkpointing, which rejects the parent run directory with
    "... is not a distributed checkpoint". A directory counts as complete when
    it has the distributed-checkpoint metadata file (same test Megatron Bridge
    uses in is_checkpoint_iteration_directory), so a save interrupted halfway
    is skipped. Names are zero-padded, so sorting by name sorts by step.
    """
    try:
        names = sorted(os.listdir(save_dir), reverse=True)
    except FileNotFoundError:
        return None
    for name in names:
        path = os.path.join(save_dir, name)
        if (name.startswith("iter_") and os.path.isdir(path)
                and any(os.path.exists(os.path.join(path, f))
                        for f in ("metadata.json", ".metadata"))):
            return path
    return None


def export_command(a, hf_path, ckpt_dir):
    # CPU path of the Megatron Bridge adapter exporter: reads the LoRA weights
    # out of the Megatron checkpoint and writes adapter_config.json +
    # adapter_model.safetensors that the `peft` library can load.
    # ckpt_dir must be an iter_* directory (see latest_iteration_dir).
    return [
        sys.executable,
        f"{BRIDGE_DIR}/examples/conversion/adapter/export_adapter.py",
        "--hf-model-path", hf_path,
        "--lora-checkpoint", ckpt_dir,
        "--output", a.export_dir,
    ]


def make_launcher_class():
    """Defined lazily so --dry-run works on a machine without Ray installed."""
    import ray

    @ray.remote
    class FinetuneLauncher:
        def __init__(self):
            self.proc = None
            self.stopped = False

        def ready(self):
            return ray.util.get_node_ip_address()

        def latest_checkpoint(self, save_dir):
            # Runs on the GPU worker, where /data is mounted.
            return latest_iteration_dir(save_dir)

        def download(self, repo_id, revision):
            from huggingface_hub import snapshot_download
            print(f"[launcher] downloading {repo_id}@{revision[:8]} into "
                  f"{os.environ.get('HF_HOME', '~/.cache/huggingface')} ...", flush=True)
            path = snapshot_download(
                repo_id, revision=revision,
                allow_patterns=["*.json", "*.safetensors", "*.txt", "*.model",
                                "*.tiktoken", "*.py"],
            )
            print(f"[launcher] model ready at {path}", flush=True)
            return path

        def run(self, cmd, cwd):
            if self.stopped:
                return 130
            print(f"[launcher] $ {shlex.join(cmd)}", flush=True)
            self.proc = subprocess.Popen(
                cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
                start_new_session=True,  # own process group so stop() can signal it
            )
            for line in self.proc.stdout:
                print(line, end="", flush=True)
            return self.proc.wait()

        def stop(self, grace=60):
            self.stopped = True
            p = self.proc
            if p is None or p.poll() is not None:
                return
            os.killpg(p.pid, signal.SIGTERM)
            try:
                p.wait(timeout=grace)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)

    return FinetuneLauncher


def main():
    a, extra = parse_args()
    check_layout(a)
    repo_id, revision = MODELS[a.model]

    if a.dry_run:
        hf_path = f"$HF_HOME/hub/models--{repo_id.replace('/', '--')}/snapshots/{revision}"
        print(f"\n# 1. download {repo_id}@{revision} -> {hf_path}")
        print(f"\n# 2. train (cwd={BRIDGE_DIR})\n{shlex.join(train_command(a, hf_path, extra))}")
        if not a.no_export:
            ckpt = os.path.join(a.save_dir, f"iter_{a.max_steps:07d}")
            print(f"\n# 3. export adapter from the newest complete iter_* under "
                  f"{a.save_dir} (e.g. {ckpt})\n"
                  f"{shlex.join(export_command(a, hf_path, ckpt))}")
        return 0

    import ray

    ray.init(address="auto")
    launcher = make_launcher_class().options(
        num_gpus=a.gpus, num_cpus=a.cpus,
        max_concurrency=2,  # lets stop() run while run() is blocking
    ).remote()

    # Turn SIGTERM (`ray job stop`, RayJob deletion) into a clean shutdown.
    def on_sigterm(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, on_sigterm)
    try:
        print(f"[launcher] waiting for a worker with {a.gpus} GPUs ...", flush=True)
        try:
            node_ip = ray.get(launcher.ready.remote(), timeout=a.placement_timeout)
        except ray.exceptions.GetTimeoutError:
            print(f"[launcher] error: no worker with {a.gpus} GPUs after "
                  f"{a.placement_timeout}s. Check `ray status` and "
                  "`kubectl get nodeclaims`.", flush=True)
            return 2
        print(f"[launcher] running on worker {node_ip}", flush=True)

        hf_path = ray.get(launcher.download.remote(repo_id, revision))

        rc = ray.get(launcher.run.remote(train_command(a, hf_path, extra), BRIDGE_DIR))
        print(f"[launcher] training exited with {rc}", flush=True)
        if rc != 0 or a.no_export:
            return rc

        ckpt = ray.get(launcher.latest_checkpoint.remote(a.save_dir))
        if ckpt is None:
            print(f"[launcher] error: no complete iter_* checkpoint in {a.save_dir}; "
                  "nothing to export", flush=True)
            return 1
        print(f"[launcher] exporting adapter from {ckpt}", flush=True)
        rc = ray.get(launcher.run.remote(export_command(a, hf_path, ckpt), BRIDGE_DIR))
        print(f"[launcher] adapter export exited with {rc}"
              + (f"; adapter in {a.export_dir}" if rc == 0 else ""), flush=True)
        return rc
    except KeyboardInterrupt:
        print("[launcher] stop requested, terminating torchrun", flush=True)
        return 130
    finally:
        try:
            ray.get(launcher.stop.remote(), timeout=90)
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
