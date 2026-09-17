#!/usr/bin/env python3
"""
Chipyard Processor Configs Benchmark Script

This script:
1. Discovers available Scala processor configs from Chipyard's config directory.
2. Compiles specified benchmark C programs (Edge Detection, FFTW FFT Benchmark, etc.).
3. Executes benchmark binaries across specified processor configs (using Verilator or Spike).
4. Captures cycle count, instruction count, IPC, host wall-clock execution time, HPM metrics, and verification checksum.
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
import urllib.request

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

SUBMODULE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CHIPYARD_DIR = os.path.abspath(os.path.join(SUBMODULE_DIR, "..", ".."))
CONFIG_DIRS = [
    os.path.join(CHIPYARD_DIR, "generators", "chipyard", "src", "main", "scala", "config"),
    os.path.join(SUBMODULE_DIR, "src", "main", "scala")
]
VERILATOR_DIR = os.path.join(CHIPYARD_DIR, "sims", "verilator")
BENCHMARKS_DIR = os.path.join(SUBMODULE_DIR, "software")
TESTS_DIR = os.path.join(CHIPYARD_DIR, "tests")

DEFAULT_OUTPUT_JSON = os.path.join(SUBMODULE_DIR, "results", "edge_detection_benchmark_results.json")
KODAK_BASE_URL = "https://r0k.us/graphics/kodak/kodak"
KODAK_CACHE_DIR = os.path.join(BENCHMARKS_DIR, "edge_detection", "kodak_images")

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

def download_kodak_image(image_id=1, cache_dir=KODAK_CACHE_DIR):
    """Download a Kodak true color image (kodim01.png - kodim24.png) and cache locally."""
    if not (1 <= image_id <= 24):
        raise ValueError(f"Kodak image ID must be between 1 and 24, got {image_id}")

    os.makedirs(cache_dir, exist_ok=True)
    filename = f"kodim{image_id:02d}.png"
    local_path = os.path.join(cache_dir, filename)

    if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
        return local_path

    url = f"{KODAK_BASE_URL}/{filename}"
    print(f"[+] Downloading Kodak test image #{image_id:02d} from {url}...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (ChipyardBenchmark/1.0)"})
        with urllib.request.urlopen(req, timeout=30) as response, open(local_path, "wb") as out_file:
            out_file.write(response.read())
        print(f"[+] Saved {filename} to {local_path} ({os.path.getsize(local_path)} bytes)")
    except Exception as e:
        if os.path.exists(local_path):
            os.remove(local_path)
        raise RuntimeError(f"Failed to download Kodak image from {url}: {e}")

    return local_path

def generate_optical_flow_header(width=32, height=32, kodak_id=1, shift_x=1, shift_y=1, pair=None, dest_header=None):
    """
    Generate optical_flow_data.h from Kodak image(s).
    If pair is given (e.g. [1, 2]), frame1 comes from kodim01 and frame2 from kodim02.
    Otherwise, frame1 is a center crop from kodim{kodak_id} and frame2 is shifted by (shift_x, shift_y).
    """
    if not PIL_AVAILABLE:
        raise RuntimeError("Pillow (PIL) is not installed. Please install pillow (`pip install pillow`) or use `--synthetic-frames`.")

    if dest_header is None:
        dest_header = os.path.join(BENCHMARKS_DIR, "edge_detection", "optical_flow_data.h")

    if pair:
        id1, id2 = pair[0], pair[1]
        p1 = download_kodak_image(id1)
        p2 = download_kodak_image(id2)
        img1 = Image.open(p1).convert("L").resize((width, height), Image.Resampling.BILINEAR)
        img2 = Image.open(p2).convert("L").resize((width, height), Image.Resampling.BILINEAR)
        frame1_bytes = list(img1.tobytes())
        frame2_bytes = list(img2.tobytes())
        desc = f"Kodak image pair #{id1:02d} and #{id2:02d}"
    else:
        p = download_kodak_image(kodak_id)
        img = Image.open(p).convert("L")
        orig_w, orig_h = img.size

        # Center crop frame1 and shifted frame2
        cx, cy = orig_w // 2, orig_h // 2
        x0 = max(0, min(orig_w - width - abs(shift_x), cx - width // 2))
        y0 = max(0, min(orig_h - height - abs(shift_y), cy - height // 2))

        crop1 = img.crop((x0, y0, x0 + width, y0 + height))
        crop2 = img.crop((x0 + shift_x, y0 + shift_y, x0 + shift_x + width, y0 + shift_y + height))

        frame1_bytes = list(crop1.tobytes())
        frame2_bytes = list(crop2.tobytes())
        desc = f"Kodak image #{kodak_id:02d} with motion displacement (dx={shift_x}, dy={shift_y})"

    print(f"[+] Generating optical flow dataset header ({width}x{height}) using {desc}...")
    npix = width * height

    with open(dest_header, "w", encoding="utf-8") as f:
        f.write("/* Auto-generated header containing Kodak image frames for Optical Flow Benchmark */\n")
        f.write("#ifndef OPTICAL_FLOW_DATA_H\n")
        f.write("#define OPTICAL_FLOW_DATA_H\n\n")
        f.write("#include <stdint.h>\n\n")
        f.write("#define USE_KODAK_DATA 1\n")
        f.write(f"#define KODAK_IMG_WIDTH  {width}\n")
        f.write(f"#define KODAK_IMG_HEIGHT {height}\n")
        f.write(f"#define KODAK_NPIX       ({npix})\n\n")

        f.write(f"/* Frame 1: {desc} */\n")
        f.write("static const uint8_t kodak_frame1[KODAK_NPIX] = {\n")
        for idx in range(0, npix, 16):
            chunk = frame1_bytes[idx:idx+16]
            f.write("    " + ", ".join(f"{val:3d}" for val in chunk) + ",\n")
        f.write("};\n\n")

        f.write(f"/* Frame 2: {desc} */\n")
        f.write("static const uint8_t kodak_frame2[KODAK_NPIX] = {\n")
        for idx in range(0, npix, 16):
            chunk = frame2_bytes[idx:idx+16]
            f.write("    " + ", ".join(f"{val:3d}" for val in chunk) + ",\n")
        f.write("};\n\n")

        f.write("#endif /* OPTICAL_FLOW_DATA_H */\n")

    print(f"[+] Header written to: {dest_header}")
    return dest_header

def resolve_unique_output_path(base_path, run_idx=None, total_runs=1, timestamp_str=None, overwrite=False, is_combined=False):
    """
    Resolve a unique file path so existing benchmark result files are not overridden.
    """
    dir_name = os.path.dirname(os.path.abspath(base_path))
    os.makedirs(dir_name, exist_ok=True)
    base_name = os.path.basename(base_path)
    stem, ext = os.path.splitext(base_name)
    if not ext:
        ext = ".json"

    if timestamp_str is None:
        timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # If overwrite is explicitly allowed for a single run
    if overwrite and total_runs == 1 and run_idx is None and not is_combined:
        return base_path

    # Construct candidate filename
    if is_combined:
        candidate_name = f"{stem}_all_runs_{timestamp_str}{ext}"
    elif total_runs > 1 and run_idx is not None:
        candidate_name = f"{stem}_run{run_idx}_{timestamp_str}{ext}"
    else:
        if not os.path.exists(base_path) and not overwrite:
            return base_path
        candidate_name = f"{stem}_{timestamp_str}{ext}"

    candidate_path = os.path.join(dir_name, candidate_name)
    counter = 1
    while os.path.exists(candidate_path):
        candidate_path = os.path.join(dir_name, f"{stem}_{timestamp_str}_{counter}{ext}")
        counter += 1

    return candidate_path

def compile_edge_detection(env, width=32, height=32, kernel_iterations=1):
    src = os.path.join(BENCHMARKS_DIR, "edge_detection", "edge_detection_benchmark.c")
    elf = os.path.join(BENCHMARKS_DIR, "edge_detection", "edge_detection_benchmark.riscv")
    gcc_path = get_gcc_path(env)

    iter_tag = f", {kernel_iterations} iter" if kernel_iterations > 1 else ""
    print(f"[+] Compiling Edge Detection benchmark source ({width}x{height}{iter_tag}): {src}")
    cmd = [
        gcc_path,
        "-O2",
        f"-DIMG_WIDTH={width}",
        f"-DIMG_HEIGHT={height}",
        f"-DKERNEL_ITERATIONS={kernel_iterations}",
        "-march=rv64gc",
        "-mabi=lp64d",
        "-mcmodel=medany",
        "-specs=htif_nano.specs",
        "-T", os.path.join(TESTS_DIR, "htif.ld"),
        src,
        "-o", elf,
        "-lm"
    ]

    res = subprocess.run(cmd, cwd=CHIPYARD_DIR, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        print(f"[-] Compilation failed for edge_detection:\n{res.stderr}")
        sys.exit(1)
    print(f"[+] Successfully compiled: {elf}")
    return elf

def compile_fft_benchmark(env):
    fft_sw_dir = os.path.join(BENCHMARKS_DIR, "fft")
    src = os.path.join(fft_sw_dir, "fft_benchmark.c")
    elf = os.path.join(fft_sw_dir, "fft_benchmark.riscv")
    gcc_path = get_gcc_path(env)

    libfftw = os.path.join(fft_sw_dir, "libfftw3.a")
    if not os.path.exists(libfftw):
        print(f"[!] Warning: {libfftw} not found. FFT compilation might fail if FFTW is not installed.")

    print(f"[+] Compiling FFTW benchmark source: {src}")
    cmd = [
        gcc_path,
        "-O2",
        "-march=rv64gc",
        "-mabi=lp64d",
        "-mcmodel=medany",
        "-specs=htif_nano.specs",
        "-T", os.path.join(TESTS_DIR, "htif.ld"),
        f"-I{fft_sw_dir}",
        src,
        "-o", elf,
        f"-L{fft_sw_dir}",
        "-lfftw3",
        "-lm"
    ]

    res = subprocess.run(cmd, cwd=CHIPYARD_DIR, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        print(f"[-] Compilation failed for fft_benchmark:\n{res.stderr}")
        sys.exit(1)
    print(f"[+] Successfully compiled: {elf}")
    return elf

def compile_optical_flow(env, width=32, height=32, use_kodak=True, kodak_id=1, shift_x=1, shift_y=1, kodak_pair=None):
    src = os.path.join(BENCHMARKS_DIR, "edge_detection", "optical_flow_benchmark.c")
    elf = os.path.join(BENCHMARKS_DIR, "edge_detection", "optical_flow_benchmark.riscv")
    gcc_path = get_gcc_path(env)
    edge_dir = os.path.join(BENCHMARKS_DIR, "edge_detection")

    cmd = [
        gcc_path,
        "-O2",
        f"-DIMG_WIDTH={width}",
        f"-DIMG_HEIGHT={height}",
        "-march=rv64gc",
        "-mabi=lp64d",
        "-mcmodel=medany",
        "-specs=htif_nano.specs",
        "-T", os.path.join(TESTS_DIR, "htif.ld"),
        f"-I{edge_dir}"
    ]

    if use_kodak:
        generate_optical_flow_header(width=width, height=height, kodak_id=kodak_id, shift_x=shift_x, shift_y=shift_y, pair=kodak_pair)
        cmd.append("-DUSE_KODAK_DATA")
        print(f"[+] Compiling Optical Flow with Kodak dataset ({width}x{height}): {src}")
    else:
        print(f"[+] Compiling Optical Flow benchmark with synthetic frames ({width}x{height}): {src}")

    cmd.extend([
        src,
        "-o", elf,
        "-lm"
    ])

    res = subprocess.run(cmd, cwd=CHIPYARD_DIR, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        print(f"[-] Compilation failed for optical_flow:\n{res.stderr}")
        sys.exit(1)
    print(f"[+] Successfully compiled: {elf}")
    return elf

def compile_benchmark(env, bench_type="edge_detection", width=32, height=32,
                      kernel_iterations=1, use_kodak=True, kodak_id=1,
                      shift_x=1, shift_y=1, kodak_pair=None):
    if bench_type in ["fft", "fft_benchmark"]:
        return compile_fft_benchmark(env)
    elif bench_type in ["optical_flow", "optflow", "optical_flow_benchmark"]:
        return compile_optical_flow(env, width=width, height=height, use_kodak=use_kodak,
                                    kodak_id=kodak_id, shift_x=shift_x, shift_y=shift_y,
                                    kodak_pair=kodak_pair)
    else:
        return compile_edge_detection(env, width=width, height=height, kernel_iterations=kernel_iterations)

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
            
            # Simple combined cache miss rate approximation
            total_accesses = instret + dc_accesses
            total_misses = ic_misses + dc_misses
            cache_miss_rate = round(total_misses / total_accesses * 100, 2) if total_accesses > 0 else 0.0
            
            # Cache hit rate is 100 - miss rate
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
    """Print ASCII summary table of benchmark results"""
    print("\n" + "=" * 135)
    print("BENCHMARK RESULTS SUMMARY")
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
    parser = argparse.ArgumentParser(description="Run benchmark suite across Chipyard processor configs.")
    parser.add_argument("--benchmark", choices=["edge_detection", "fft", "fft_benchmark", "optical_flow", "optical_flow_benchmark", "all"], default="all", help="Benchmark to run (default: all)")
    parser.add_argument("-n", "--runs", "--iterations", dest="runs", type=int, default=1, help="Number of benchmark evaluation runs to perform (default: 1)")
    parser.add_argument("--kernel-iterations", type=int, default=1, help="Sobel edge detection inner loop iterations per run (default: 1)")
    parser.add_argument("--configs", nargs="+", help="Processor configs to benchmark (default: pre-compiled verilator configs or RocketConfig)")
    parser.add_argument("--simulator", choices=["verilator", "spike", "auto"], default="auto", help="Simulation backend to use")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_JSON, help="Output JSON results file path")
    parser.add_argument("--overwrite", action="store_true", help="Allow overwriting target output file if it exists (default: False, generates unique name)")
    parser.add_argument("--img-width", type=int, default=32, help="Image width for benchmark (default: 32)")
    parser.add_argument("--img-height", type=int, default=32, help="Image height for benchmark (default: 32)")
    parser.add_argument("--kodak-id", type=int, default=1, help="Kodak suite image ID (1-24) to use for optical flow (default: 1)")
    parser.add_argument("--kodak-pair", type=int, nargs=2, default=None, help="Pair of Kodak image IDs (e.g. 1 2) for optical flow frames")
    parser.add_argument("--shift-x", type=int, default=1, help="Horizontal pixel shift for optical flow frame motion (default: 1)")
    parser.add_argument("--shift-y", type=int, default=1, help="Vertical pixel shift for optical flow frame motion (default: 1)")
    parser.add_argument("--synthetic-frames", action="store_true", help="Force synthetic checkerboard frames instead of Kodak images")
    parser.add_argument("--build-missing", action="store_true", help="Automatically build missing Verilator binaries")
    parser.add_argument("--timeout", type=int, default=180, help="Per-run timeout in seconds")
    parser.add_argument("--list-configs", action="store_true", help="List available Scala processor configs")
    args = parser.parse_args() # --benchmark edge_detection -n 10 --configs BenchmarkConfigs --simulator verilator

    discovered_configs = discover_scala_configs()
    compiled_verilator = find_compiled_verilator_configs()

    if args.list_configs:
        print("Discovered Scala Processor Configs:")
        for c in discovered_configs:
            compiled_tag = " [Verilator compiled]" if c in compiled_verilator else ""
            print(f" - {c}{compiled_tag}")
        sys.exit(0)

    env = get_env()

    # Determine benchmarks to run
    if args.benchmark == "all":
        benchmarks_to_run = ["edge_detection", "fft_benchmark", "optical_flow_benchmark"]
    elif args.benchmark in ["fft", "fft_benchmark"]:
        benchmarks_to_run = ["fft_benchmark"]
    elif args.benchmark in ["optical_flow", "optical_flow_benchmark"]:
        benchmarks_to_run = ["optical_flow_benchmark"]
    else:
        benchmarks_to_run = ["edge_detection"]

    compiled_elfs = {}
    for bench in benchmarks_to_run:
        elf = compile_benchmark(
            env,
            bench_type=bench,
            width=args.img_width,
            height=args.img_height,
            kernel_iterations=args.kernel_iterations,
            use_kodak=(not args.synthetic_frames),
            kodak_id=args.kodak_id,
            shift_x=args.shift_x,
            shift_y=args.shift_y,
            kodak_pair=args.kodak_pair
        )
        compiled_elfs[bench] = elf

    # Determine target configs
    if args.configs:
        if "all" in args.configs:
            target_configs = discovered_configs
        elif "benchmark" in args.configs or "BenchmarkConfigs" in args.configs:
            target_configs = [c for c in discovered_configs if c.startswith("Benchmark")]
        else:
            target_configs = args.configs
    else:
        # Use compiled verilator configs if available, otherwise default to RocketConfig
        if compiled_verilator:
            target_configs = compiled_verilator
        else:
            target_configs = ["RocketConfig"]

    print(f"[+] Target configurations to benchmark: {', '.join(target_configs)}")

    session_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    all_runs_reports = []

    for run_idx in range(1, args.runs + 1):
        if args.runs > 1:
            print(f"\n{'=' * 80}\n[+] BENCHMARK RUN {run_idx} OF {args.runs}\n{'=' * 80}")

        benchmark_results = []
        run_start_timestamp = datetime.datetime.now().isoformat()

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

                res["run_iteration"] = run_idx
                benchmark_results.append(res)

        print_summary_table(benchmark_results)

        json_report = {
            "benchmarks_evaluated": benchmarks_to_run,
            "timestamp": run_start_timestamp,
            "run_iteration": run_idx,
            "total_runs": args.runs,
            "configs_evaluated": len(target_configs),
            "results": benchmark_results
        }
        all_runs_reports.append(json_report)

        run_output_path = resolve_unique_output_path(
            args.output,
            run_idx=run_idx,
            total_runs=args.runs,
            timestamp_str=session_timestamp,
            overwrite=args.overwrite
        )

        with open(run_output_path, "w", encoding="utf-8") as f:
            json.dump(json_report, f, indent=2)

        print(f"[+] Run {run_idx} results exported to: {run_output_path}")

    if args.runs > 1:
        combined_path = resolve_unique_output_path(
            args.output,
            total_runs=args.runs,
            timestamp_str=session_timestamp,
            overwrite=args.overwrite,
            is_combined=True
        )
        combined_report = {
            "benchmarks_evaluated": benchmarks_to_run,
            "total_runs": args.runs,
            "session_timestamp": session_timestamp,
            "runs": all_runs_reports
        }
        with open(combined_path, "w", encoding="utf-8") as f:
            json.dump(combined_report, f, indent=2)
        print(f"[+] Consolidated all {args.runs} runs exported to: {combined_path}")

if __name__ == "__main__":
    main()
