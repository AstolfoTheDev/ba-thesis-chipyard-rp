#!/usr/bin/env python3
"""
Chipyard Embench-IoT 1.0 Benchmark Suite Runner

This script:
1. Discovers available Scala processor configs from Chipyard and submodule config directories.
2. Compiles specified Embench-IoT 1.0 bare-metal C benchmarks.
3. Executes benchmark binaries across specified processor configs (using Verilator or Spike).
4. Captures cycle count, instruction count, IPC, host wall-clock execution time, HPM metrics (branches, cache miss/hits).
5. Saves the results into a structured JSON benchmark report file.
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time

SUBMODULE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CHIPYARD_DIR = os.path.abspath(os.path.join(SUBMODULE_DIR, "..", ".."))
CONFIG_DIRS = [
    os.path.join(CHIPYARD_DIR, "generators", "chipyard", "src", "main", "scala", "config"),
    os.path.join(SUBMODULE_DIR, "src", "main", "scala")
]
VERILATOR_DIR = os.path.join(CHIPYARD_DIR, "sims", "verilator")
EMBENCH_DIR = os.path.join(SUBMODULE_DIR, "software", "embench-iot")
SUPPORT_DIR = os.path.join(EMBENCH_DIR, "support")
BOARD_SUPPORT = os.path.join(EMBENCH_DIR, "chipyard_boardsupport.c")
TESTS_DIR = os.path.join(CHIPYARD_DIR, "tests")

DEFAULT_OUTPUT_JSON = os.path.join(SUBMODULE_DIR, "results", "embench_benchmark_results.json")

# Embench 1.0 Benchmark Source Mapping
EMBENCH_BENCHMARKS = {
    "aha-mont64": ["src/aha-mont64/mont64.c"],
    "crc32": ["src/crc32/crc_32.c"],
    "cubic": ["src/cubic/libcubic.c", "src/cubic/basicmath_small.c"],
    "edn": ["src/edn/libedn.c"],
    "huffbench": ["src/huffbench/libhuffbench.c"],
    "matmult-int": ["src/matmult-int/matmult-int.c"],
    "minver": ["src/minver/libminver.c"],
    "nbody": ["src/nbody/nbody.c"],
    "nettle-aes": ["src/nettle-aes/nettle-aes.c"],
    "nettle-sha256": ["src/nettle-sha256/nettle-sha256.c"],
    "nsichneu": ["src/nsichneu/libnsichneu.c"],
    "picojpeg": ["src/picojpeg/picojpeg_test.c", "src/picojpeg/libpicojpeg.c"],
    "qrduino": ["src/qrduino/qrtest.c", "src/qrduino/qrframe.c", "src/qrduino/qrencode.c"],
    "sglib-combined": ["src/sglib-combined/combined.c"],
    "slre": ["src/slre/libslre.c"],
    "st": ["src/st/libst.c"],
    "statemate": ["src/statemate/libstatemate.c"],
    "ud": ["src/ud/libud.c"],
    "wikisort": ["src/wikisort/libwikisort.c"]
}

# Environment setup helper
def get_env():
    env = os.environ.copy()
    conda_bin = os.path.join(CHIPYARD_DIR, ".conda-env", "bin")
    riscv_tools_bin = os.path.join(CHIPYARD_DIR, ".conda-env", "riscv-tools", "bin")

    path_entries = env.get("PATH", "").split(os.pathsep)
    if riscv_tools_bin not in path_entries:
        path_entries.insert(0, riscv_tools_bin)
    if conda_bin not in path_entries:
        path_entries.insert(0, conda_bin)
    env["PATH"] = os.pathsep.join(path_entries)
    env["RISCV"] = os.path.join(CHIPYARD_DIR, ".conda-env", "riscv-tools")
    return env

def discover_scala_configs():
    """Discover all Config class names in Chipyard and submodule config directories"""
    configs = []
    config_pattern = re.compile(r"class\s+([A-Za-z0-9_]+)\s+extends\s+Config")

    for cdir in CONFIG_DIRS:
        if os.path.exists(cdir):
            for root, _, files in os.walk(cdir):
                for file in files:
                    if file.endswith(".scala"):
                        path = os.path.join(root, file)
                        with open(path, "r", encoding="utf-8", errors="ignore") as f:
                            for line in f:
                                match = config_pattern.search(line)
                                if match:
                                    cfg = match.group(1)
                                    if cfg not in configs:
                                        configs.append(cfg)
    return sorted(configs)

def find_compiled_verilator_configs():
    """Find pre-compiled verilator simulator binaries in sims/verilator/"""
    prefix = "simulator-chipyard.harness-"
    compiled = []
    if not os.path.exists(VERILATOR_DIR):
        return compiled

    for fname in os.listdir(VERILATOR_DIR):
        if fname.startswith(prefix) and not fname.endswith("-debug"):
            config_name = fname[len(prefix):]
            compiled.append(config_name)
    return sorted(compiled)

def get_gcc_path(env):
    gcc_path = subprocess.run(
        ["which", "riscv64-unknown-elf-gcc"],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    ).stdout.strip()

    if not gcc_path or not os.path.exists(gcc_path):
        raise RuntimeError("riscv64-unknown-elf-gcc compiler not found in PATH!")
    return gcc_path

def compile_embench_benchmark(env, bench_name):
    if bench_name not in EMBENCH_BENCHMARKS:
        raise ValueError(f"Unknown Embench benchmark: {bench_name}")

    sources = EMBENCH_BENCHMARKS[bench_name]
    src_dir = os.path.dirname(os.path.join(EMBENCH_DIR, sources[0]))
    elf = os.path.join(EMBENCH_DIR, f"{bench_name}.riscv")
    gcc_path = get_gcc_path(env)

    print(f"[+] Compiling Embench benchmark '{bench_name}'...")
    cmd = [
        gcc_path,
        "-O2",
        "-DWARMUP_HEAT=0",
        "-DCPU_MHZ=1",
        "-march=rv64gc",
        "-mabi=lp64d",
        "-mcmodel=medany",
        "-specs=htif_nano.specs",
        "-T", os.path.join(TESTS_DIR, "htif.ld"),
        f"-I{SUPPORT_DIR}",
        f"-I{src_dir}",
        os.path.join(SUPPORT_DIR, "main.c"),
        os.path.join(SUPPORT_DIR, "beebsc.c"),
        BOARD_SUPPORT
    ] + [os.path.join(EMBENCH_DIR, s) for s in sources] + [
        "-o", elf,
        "-lm"
    ]

    res = subprocess.run(cmd, cwd=CHIPYARD_DIR, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        print(f"[-] Compilation failed for Embench benchmark '{bench_name}':\n{res.stderr}")
        sys.exit(1)
    print(f"[+] Successfully compiled: {elf}")
    return elf

def run_verilator_sim(config_name, bench_name, elf_path, env, build_missing=False, timeout=1800):
    """Run benchmark binary on Verilator simulator for given config"""
    sim_binary = os.path.join(VERILATOR_DIR, f"simulator-chipyard.harness-{config_name}")

    if not os.path.exists(sim_binary):
        if build_missing:
            print(f"[+] Building Verilator simulator for {config_name} (this may take several minutes)...")
            build_cmd = ["make", "-C", VERILATOR_DIR, f"CONFIG={config_name}"]
            b_res = subprocess.run(build_cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if b_res.returncode != 0 or not os.path.exists(sim_binary):
                return {
                    "config": config_name,
                    "benchmark": bench_name,
                    "simulator": "verilator",
                    "status": "BUILD_FAILED",
                    "error": b_res.stderr[-500:] if b_res.stderr else "Build returned error code"
                }
        else:
            return {
                "config": config_name,
                "benchmark": bench_name,
                "simulator": "verilator",
                "status": "NOT_COMPILED",
                "error": f"Verilator executable {os.path.basename(sim_binary)} does not exist. Use --build-missing to compile."
            }

    print(f"[+] Running {bench_name} on {config_name} via Verilator...")
    cmd = [sim_binary, elf_path]
    start_time = time.time()
    try:
        proc = subprocess.run(cmd, cwd=VERILATOR_DIR, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
        wall_clock_time = time.time() - start_time

        output = proc.stdout + proc.stderr
        result = parse_benchmark_output(output)
        result.update({
            "config": config_name,
            "benchmark": bench_name,
            "simulator": "verilator",
            "status": "SUCCESS" if proc.returncode == 0 and result.get("cycles") is not None else "FAILED",
            "wall_clock_time_sec": round(wall_clock_time, 4),
            "return_code": proc.returncode
        })
        return result
    except subprocess.TimeoutExpired:
        wall_clock_time = time.time() - start_time
        return {
            "config": config_name,
            "benchmark": bench_name,
            "simulator": "verilator",
            "status": "TIMEOUT",
            "wall_clock_time_sec": round(wall_clock_time, 4),
            "error": f"Execution timed out after {timeout} seconds"
        }

def run_spike_sim(config_name, bench_name, elf_path, env, timeout=60):
    """Run benchmark binary on Spike simulator"""
    spike_path = subprocess.run(
        ["which", "spike"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    ).stdout.strip()

    if not spike_path:
        return {
            "config": config_name,
            "benchmark": bench_name,
            "simulator": "spike",
            "status": "ERROR",
            "error": "Spike executable not found in PATH"
        }

    print(f"[+] Running {bench_name} on {config_name} via Spike ISA Simulator...")
    cmd = [spike_path, elf_path]
    start_time = time.time()
    try:
        proc = subprocess.run(cmd, cwd=CHIPYARD_DIR, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
        wall_clock_time = time.time() - start_time

        output = proc.stdout + proc.stderr
        result = parse_benchmark_output(output)
        result.update({
            "config": config_name,
            "benchmark": bench_name,
            "simulator": "spike",
            "status": "SUCCESS" if proc.returncode == 0 and result.get("cycles") is not None else "FAILED",
            "wall_clock_time_sec": round(wall_clock_time, 4),
            "return_code": proc.returncode
        })
        return result
    except subprocess.TimeoutExpired:
        wall_clock_time = time.time() - start_time
        return {
            "config": config_name,
            "benchmark": bench_name,
            "simulator": "spike",
            "status": "TIMEOUT",
            "wall_clock_time_sec": round(wall_clock_time, 4),
            "error": f"Execution timed out after {timeout} seconds"
        }

def parse_benchmark_output(output):
    """Extract metrics from benchmark output tag"""
    pattern = re.compile(r"BENCHMARK_RESULT:\s+cycles=(\d+)\s+instret=(\d+)\s+checksum=(\d+)(?:\s+branches=(\d+)\s+br_misses=(\d+)\s+ic_misses=(\d+)\s+dc_accesses=(\d+)\s+dc_misses=(\d+))?")
    match = pattern.search(output)

    if match:
        cycles = int(match.group(1))
        instret = int(match.group(2))
        checksum = int(match.group(3))
        ipc = round(instret / cycles, 4) if cycles > 0 else 0.0

        res = {
            "cycles": cycles,
            "instructions": instret,
            "ipc": ipc,
            "checksum": checksum,
            "raw_match": match.group(0)
        }

        if match.group(4) is not None:
            branches = int(match.group(4))
            br_misses = int(match.group(5))
            ic_misses = int(match.group(6))
            dc_accesses = int(match.group(7))
            dc_misses = int(match.group(8))

            br_miss_rate = round(br_misses / branches * 100, 2) if branches > 0 else 0.0

            total_accesses = instret + dc_accesses
            total_misses = ic_misses + dc_misses
            cache_miss_rate = round(total_misses / total_accesses * 100, 2) if total_accesses > 0 else 0.0
            cache_hit_rate = round(100.0 - cache_miss_rate, 2)

            res.update({
                "branches": branches,
                "br_misses": br_misses,
                "br_miss_rate_pct": br_miss_rate,
                "ic_misses": ic_misses,
                "dc_accesses": dc_accesses,
                "dc_misses": dc_misses,
                "cache_miss_rate_pct": cache_miss_rate,
                "cache_hit_rate_pct": cache_hit_rate
            })

        return res
    return {
        "cycles": None,
        "instructions": None,
        "ipc": None,
        "checksum": None,
        "output_snippet": output[-500:] if output else ""
    }

def print_summary_table(results):
    """Print ASCII summary table of Embench benchmark results"""
    print("\n" + "=" * 135)
    print("EMBENCH-IOT 1.0 BENCHMARK RESULTS SUMMARY")
    print("=" * 135)
    header = f"{'Config':<20} | {'Benchmark':<16} | {'Simulator':<10} | {'Status':<8} | {'Cycles':<10} | {'IPC':<6} | {'Br Mispred':<10} | {'Cache Hit':<9} | {'Cache Miss':<10} | {'Time (s)':<8}"
    print(header)
    print("-" * 135)

    for r in results:
        cfg = r.get("config", "N/A")
        bench = r.get("benchmark", "N/A")
        sim = r.get("simulator", "N/A")
        status = r.get("status", "N/A")
        cycles = str(r.get("cycles")) if r.get("cycles") is not None else "N/A"
        ipc = str(r.get("ipc")) if r.get("ipc") is not None else "N/A"
        wtime = str(r.get("wall_clock_time_sec")) if r.get("wall_clock_time_sec") is not None else "N/A"

        br_miss = f"{r.get('br_miss_rate_pct', 0.0)}%" if "br_miss_rate_pct" in r else "N/A"
        cache_hit = f"{r.get('cache_hit_rate_pct', 0.0)}%" if "cache_hit_rate_pct" in r else "N/A"
        cache_miss = f"{r.get('cache_miss_rate_pct', 0.0)}%" if "cache_miss_rate_pct" in r else "N/A"

        print(f"{cfg:<20} | {bench:<16} | {sim:<10} | {status:<8} | {cycles:<10} | {ipc:<6} | {br_miss:<10} | {cache_hit:<9} | {cache_miss:<10} | {wtime:<8}")

    print("=" * 135 + "\n")

def main():
    parser = argparse.ArgumentParser(description="Run Embench-IoT 1.0 benchmark suite across Chipyard processor configs.")
    parser.add_argument("--benchmark", choices=list(EMBENCH_BENCHMARKS.keys()) + ["all"], default="all", help="Embench benchmark to run (default: all)")
    parser.add_argument("--configs", nargs="+", help="Processor configs to benchmark (default: pre-compiled verilator configs or RocketConfig)")
    parser.add_argument("--simulator", choices=["verilator", "spike", "auto"], default="auto", help="Simulation backend to use")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_JSON, help="Output JSON results file path")
    parser.add_argument("--build-missing", action="store_true", help="Automatically build missing Verilator binaries")
    parser.add_argument("--timeout", type=int, default=180, help="Per-run timeout in seconds")
    parser.add_argument("--list-benchmarks", action="store_true", help="List available Embench-IoT 1.0 benchmarks")
    parser.add_argument("--list-configs", action="store_true", help="List available Scala processor configs")
    args = parser.parse_args()

    if args.list_benchmarks:
        print("Available Embench-IoT 1.0 Benchmarks:")
        for b in sorted(EMBENCH_BENCHMARKS.keys()):
            print(f" - {b}")
        sys.exit(0)

    discovered_configs = discover_scala_configs()
    compiled_verilator = find_compiled_verilator_configs()

    if args.list_configs:
        print("Discovered Scala Processor Configs:")
        for c in discovered_configs:
            compiled_tag = " [Verilator compiled]" if c in compiled_verilator else ""
            print(f" - {c}{compiled_tag}")
        sys.exit(0)

    env = get_env()

    if args.benchmark == "all":
        benchmarks_to_run = sorted(EMBENCH_BENCHMARKS.keys())
    else:
        benchmarks_to_run = [args.benchmark]

    compiled_elfs = {}
    for bench in benchmarks_to_run:
        elf = compile_embench_benchmark(env, bench_name=bench)
        compiled_elfs[bench] = elf

    if args.configs:
        if "all" in args.configs:
            target_configs = discovered_configs
        elif "benchmark" in args.configs or "BenchmarkConfigs" in args.configs:
            target_configs = [c for c in discovered_configs if c.startswith("Benchmark")]
        else:
            target_configs = args.configs
    else:
        if compiled_verilator:
            target_configs = compiled_verilator
        else:
            target_configs = ["RocketConfig"]

    print(f"[+] Target configurations to benchmark: {', '.join(target_configs)}")

    benchmark_results = []
    start_timestamp = datetime.datetime.now().isoformat()

    for bench in benchmarks_to_run:
        elf_path = compiled_elfs[bench]
        for config in target_configs:
            if args.simulator == "spike":
                res = run_spike_sim(config, bench, elf_path, env, timeout=args.timeout)
            elif args.simulator == "verilator":
                res = run_verilator_sim(config, bench, elf_path, env, build_missing=args.build_missing, timeout=args.timeout)
            else: # auto
                if config in compiled_verilator or args.build_missing:
                    res = run_verilator_sim(config, bench, elf_path, env, build_missing=args.build_missing, timeout=args.timeout)
                else:
                    print(f"[!] Verilator binary not compiled for {config}. Falling back to Spike...")
                    res = run_spike_sim(config, bench, elf_path, env, timeout=args.timeout)

            benchmark_results.append(res)

    print_summary_table(benchmark_results)

    json_report = {
        "suite": "Embench-IoT 1.0",
        "benchmarks_evaluated": benchmarks_to_run,
        "timestamp": start_timestamp,
        "configs_evaluated": len(target_configs),
        "results": benchmark_results
    }

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(json_report, f, indent=2)

    print(f"[+] Embench 1.0 benchmark results exported to: {args.output}")

if __name__ == "__main__":
    main()
