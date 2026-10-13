#!/usr/bin/env python3
"""
Chipyard Processor Configs Benchmark Script

This script:
1. Discovers available Scala processor configs from Chipyard's config directory.
2. Compiles specified benchmark C programs (Edge Detection, FFTW FFT Benchmark, etc.).
3. Executes benchmark binaries across specified processor configs (using Verilator or Spike).
4. Captures cycle count, instruction count, IPC, host wall-clock execution time, HPM metrics, and verification checksum.
5. Saves results as CSV benchmark reports (a separate CSV file per algorithm), placed in a dedicated folder per run, with the input image name added as the first column on the left side.
"""

import argparse
import csv
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

DEFAULT_OUTPUT_DIR = os.path.join(SUBMODULE_DIR, "results")
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

def get_simulator_threads(binary_path):
    """
    Inspect the compiled Verilator simulator binary to determine the thread count
    it was compiled with by checking VTestDriver::threads() const disassembly.
    Returns thread count (int), or None if detection fails.
    """
    if not os.path.exists(binary_path):
        return None
    try:
        proc = subprocess.Popen(
            ["objdump", "-d", "-C", binary_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True
        )
        found_func = False
        for line in proc.stdout:
            if "<VTestDriver::threads() const>:" in line or "<_ZNK11VTestDriver7threadsEv>:" in line:
                found_func = True
                continue
            if found_func:
                m = re.search(r"mov\s+\$0x([0-9a-fA-F]+),%eax", line)
                if m:
                    proc.kill()
                    return int(m.group(1), 16)
                if "ret" in line:
                    break
        proc.stdout.close()
        proc.wait()
    except Exception:
        pass
    return None


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

def generate_optical_flow_header(width=32, height=32, kodak_id=1, shift_x=1, shift_y=1, pair=None, dest_header=None, image_path=None):
    """
    Generate optical_flow_data.h from Kodak image(s) or custom image.
    If pair is given (e.g. [1, 2]), frame1 comes from kodim01 and frame2 from kodim02.
    Otherwise, frame1 is a center crop and frame2 is shifted by (shift_x, shift_y).
    """
    if not PIL_AVAILABLE:
        raise RuntimeError("Pillow (PIL) is not installed. Please install pillow (`pip install pillow`) or use `--synthetic-frames`.")

    if dest_header is None:
        dest_header = os.path.join(BENCHMARKS_DIR, "edge_detection", "optical_flow_data.h")

    if image_path:
        img = Image.open(image_path).convert("L")
        orig_w, orig_h = img.size
        cx, cy = orig_w // 2, orig_h // 2
        x0 = max(0, min(orig_w - width - abs(shift_x), cx - width // 2))
        y0 = max(0, min(orig_h - height - abs(shift_y), cy - height // 2))
        crop1 = img.crop((x0, y0, x0 + width, y0 + height))
        crop2 = img.crop((x0 + shift_x, y0 + shift_y, x0 + shift_x + width, y0 + shift_y + height))
        frame1_bytes = list(crop1.tobytes())
        frame2_bytes = list(crop2.tobytes())
        desc = f"Input image {os.path.basename(image_path)} (dx={shift_x}, dy={shift_y})"
    elif pair:
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
        f.write("/* Auto-generated header containing image frames for Optical Flow Benchmark */\n")
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

def generate_edge_detection_header(width=32, height=32, kodak_id=1, image_path=None, dest_header=None):
    """
    Generate edge_detection_data.h from Kodak image or custom input image.
    """
    if not PIL_AVAILABLE:
        raise RuntimeError("Pillow (PIL) is not installed. Please install pillow (`pip install pillow`) or use `--synthetic-frames`.")

    if dest_header is None:
        dest_header = os.path.join(BENCHMARKS_DIR, "edge_detection", "edge_detection_data.h")

    if image_path:
        img = Image.open(image_path).convert("L").resize((width, height), Image.Resampling.BILINEAR)
        desc = f"Input image {os.path.basename(image_path)}"
    else:
        p = download_kodak_image(kodak_id)
        img = Image.open(p).convert("L").resize((width, height), Image.Resampling.BILINEAR)
        desc = f"Kodak image #{kodak_id:02d}"

    frame_bytes = list(img.tobytes())
    npix = width * height

    print(f"[+] Generating edge detection dataset header ({width}x{height}) using {desc}...")
    with open(dest_header, "w", encoding="utf-8") as f:
        f.write("/* Auto-generated header containing image pixels for Edge Detection Benchmark */\n")
        f.write("#ifndef EDGE_DETECTION_DATA_H\n")
        f.write("#define EDGE_DETECTION_DATA_H\n\n")
        f.write("#include <stdint.h>\n\n")
        f.write("#define USE_KODAK_DATA 1\n")
        f.write(f"#define KODAK_IMG_WIDTH  {width}\n")
        f.write(f"#define KODAK_IMG_HEIGHT {height}\n")
        f.write(f"#define KODAK_NPIX       ({npix})\n\n")
        f.write(f"/* Image: {desc} */\n")
        f.write("static const uint8_t kodak_image[KODAK_NPIX] = {\n")
        for idx in range(0, npix, 16):
            chunk = frame_bytes[idx:idx+16]
            f.write("    " + ", ".join(f"{val:3d}" for val in chunk) + ",\n")
        f.write("};\n\n")
        f.write("#endif /* EDGE_DETECTION_DATA_H */\n")

    print(f"[+] Header written to: {dest_header}")
    return dest_header

IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.bmp', '.ppm', '.pgm', '.tif', '.tiff', '.webp')

def natural_sort_key(s):
    """Sort strings containing numbers in natural numeric order."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

def find_images_in_dir(directory):
    """Find all image files in a directory sorted naturally."""
    if not os.path.exists(directory) or not os.path.isdir(directory):
        return []
    files = []
    for f in os.listdir(directory):
        if f.lower().endswith(IMAGE_EXTENSIONS):
            files.append(os.path.join(directory, f))
    files.sort(key=lambda p: natural_sort_key(os.path.basename(p)))
    return files

def parse_range_spec(spec, allow_single_as_range=False):
    """
    Parses range specification from CLI args into (start_idx, end_idx) 1-based integers.
    Accepts:
      ['1', '5']                 -> (1, 5)
      ['1-5'] / ['1..5'] / ['1:5'] -> (1, 5)
      ['kodim01', 'kodim05']     -> (1, 5)
      ['kodim01..kodim05']       -> (1, 5)
      ['5']                      -> (1, 5) if allow_single_as_range else None
    """
    if not spec:
        return None
    if isinstance(spec, (list, tuple)):
        if len(spec) == 2:
            s1 = re.sub(r'^[^\d]*', '', str(spec[0]))
            s2 = re.sub(r'^[^\d]*', '', str(spec[1]))
            if s1.isdigit() and s2.isdigit():
                start, end = int(s1), int(s2)
                return (min(start, end), max(start, end))
        raw = " ".join(str(x) for x in spec)
    else:
        raw = str(spec)

    raw = raw.strip()
    m = re.match(r'^(?:kodim)?(\d+)\s*(?:-|\.\.|\:|\s+)\s*(?:kodim)?(\d+)$', raw, re.IGNORECASE)
    if m:
        start, end = int(m.group(1)), int(m.group(2))
        return (min(start, end), max(start, end))

    if allow_single_as_range:
        m_single = re.match(r'^(?:kodim)?(\d+)$', raw, re.IGNORECASE)
        if m_single and int(m_single.group(1)) > 1:
            return (1, int(m_single.group(1)))
    return None

def resolve_single_image(item, image_dir=None):
    """Resolve a single image specification to (image_path, display_name, kodak_id)"""
    if not item:
        return None, None, None

    if os.path.exists(item) and not os.path.isdir(item):
        return os.path.abspath(item), os.path.basename(item), None

    if image_dir and os.path.exists(os.path.join(image_dir, item)) and not os.path.isdir(os.path.join(image_dir, item)):
        p = os.path.abspath(os.path.join(image_dir, item))
        return p, os.path.basename(p), None

    if os.path.exists(os.path.join(KODAK_CACHE_DIR, item)) and not os.path.isdir(os.path.join(KODAK_CACHE_DIR, item)):
        p = os.path.abspath(os.path.join(KODAK_CACHE_DIR, item))
        m = re.match(r"^kodim(\d+)\.png$", item, re.IGNORECASE)
        kid = int(m.group(1)) if m else None
        return p, item, kid

    if os.path.exists(os.path.join(BENCHMARKS_DIR, "edge_detection", item)) and not os.path.isdir(os.path.join(BENCHMARKS_DIR, "edge_detection", item)):
        p = os.path.abspath(os.path.join(BENCHMARKS_DIR, "edge_detection", item))
        return p, item, None

    m = re.match(r"^kodim(\d+)(?:\.png)?$", item, re.IGNORECASE)
    if m:
        kid = int(m.group(1))
        p = download_kodak_image(kid)
        return p, f"kodim{kid:02d}.png", kid

    if item.isdigit():
        kid = int(item)
        p = download_kodak_image(kid)
        return p, f"kodim{kid:02d}.png", kid

    print(f"[!] Warning: Specified image file '{item}' not found! Falling back to Kodak image #01")
    p = download_kodak_image(1)
    return p, "kodim01.png", 1

def resolve_edge_detection_images(args):
    """
    Resolve the sequence of images to be used for the edge detection benchmark.
    Returns a list of dicts: [{'path': ..., 'display_name': ..., 'kodak_id': ...}, ...]
    """
    if getattr(args, "synthetic_frames", False):
        return [{"path": None, "display_name": "synthetic", "kodak_id": None}]

    img_dir = None
    input_image = getattr(args, "image", None)

    if getattr(args, "image_dir", None):
        if os.path.exists(args.image_dir) and os.path.isdir(args.image_dir):
            img_dir = os.path.abspath(args.image_dir)
        elif os.path.exists(os.path.join(BENCHMARKS_DIR, "edge_detection", args.image_dir)) and os.path.isdir(os.path.join(BENCHMARKS_DIR, "edge_detection", args.image_dir)):
            img_dir = os.path.abspath(os.path.join(BENCHMARKS_DIR, "edge_detection", args.image_dir))
        else:
            print(f"[!] Warning: Specified --image-dir '{args.image_dir}' does not exist or is not a directory!")
    elif input_image and os.path.isdir(input_image):
        img_dir = os.path.abspath(input_image)
        input_image = None
    elif input_image and os.path.isdir(os.path.join(BENCHMARKS_DIR, "edge_detection", input_image)):
        img_dir = os.path.abspath(os.path.join(BENCHMARKS_DIR, "edge_detection", input_image))
        input_image = None

    range_spec = None
    if getattr(args, "image_range", None):
        range_spec = parse_range_spec(args.image_range, allow_single_as_range=True)
    elif getattr(args, "kodak_range", None):
        range_spec = parse_range_spec(args.kodak_range, allow_single_as_range=True)
    elif input_image:
        range_spec = parse_range_spec(input_image, allow_single_as_range=False)

    # 1. Range specified
    if range_spec:
        start_val, end_val = range_spec

        # Custom folder specified
        if img_dir:
            folder_imgs = find_images_in_dir(img_dir)
            if not folder_imgs and os.path.abspath(img_dir) == os.path.abspath(KODAK_CACHE_DIR):
                # Empty Kodak cache dir, download Kodak range
                start_id = max(1, min(24, start_val))
                end_id = max(1, min(24, end_val))
                print(f"[+] Selected Kodak suite image range [kodim{start_id:02d}..kodim{end_id:02d}] ({end_id - start_id + 1} image(s))")
                results = []
                for kid in range(start_id, end_id + 1):
                    p = download_kodak_image(kid)
                    results.append({"path": p, "display_name": f"kodim{kid:02d}.png", "kodak_id": kid})
                return results

            if not folder_imgs:
                raise RuntimeError(f"No image files found in specified directory: {img_dir}")
            start_idx = max(1, start_val) - 1
            end_idx = min(len(folder_imgs), end_val)
            if start_idx >= len(folder_imgs):
                print(f"[!] Warning: Range start {start_val} exceeds number of images ({len(folder_imgs)}) in {img_dir}. Using last image.")
                selected = [folder_imgs[-1]]
            else:
                selected = folder_imgs[start_idx:end_idx]

            print(f"[+] Selected image range [{start_val}..{end_val}] from folder '{img_dir}' ({len(selected)} image(s))")
            results = []
            for p in selected:
                m = re.match(r"^kodim(\d+)\.png$", os.path.basename(p), re.IGNORECASE)
                kid = int(m.group(1)) if m else None
                results.append({"path": p, "display_name": os.path.basename(p), "kodak_id": kid})
            return results

        # Kodak suite range (default)
        start_id = max(1, min(24, start_val))
        end_id = max(1, min(24, end_val))
        print(f"[+] Selected Kodak suite image range [kodim{start_id:02d}..kodim{end_id:02d}] ({end_id - start_id + 1} image(s))")
        results = []
        for kid in range(start_id, end_id + 1):
            p = download_kodak_image(kid)
            results.append({"path": p, "display_name": f"kodim{kid:02d}.png", "kodak_id": kid})
        return results

    # 2. Explicit list of images via --images
    if getattr(args, "images", None):
        results = []
        for item in args.images:
            p, disp, kid = resolve_single_image(item, image_dir=img_dir)
            results.append({"path": p, "display_name": disp, "kodak_id": kid})
        return results

    # 3. Comma-separated or single image in --image
    if input_image:
        if "," in input_image:
            parts = [x.strip() for x in input_image.split(",") if x.strip()]
            results = []
            for item in parts:
                p, disp, kid = resolve_single_image(item, image_dir=img_dir)
                results.append({"path": p, "display_name": disp, "kodak_id": kid})
            return results
        p, disp, kid = resolve_single_image(input_image, image_dir=img_dir)
        return [{"path": p, "display_name": disp, "kodak_id": kid}]

    # 4. Image directory provided without range: evaluate all images in directory
    if img_dir:
        folder_imgs = find_images_in_dir(img_dir)
        if folder_imgs:
            print(f"[+] Discovered {len(folder_imgs)} image(s) in image folder '{img_dir}'")
            results = []
            for p in folder_imgs:
                m = re.match(r"^kodim(\d+)\.png$", os.path.basename(p), re.IGNORECASE)
                kid = int(m.group(1)) if m else None
                results.append({"path": p, "display_name": os.path.basename(p), "kodak_id": kid})
            return results

    # 5. Default: Kodak image specified by --kodak-id (default: 1)
    kid = getattr(args, "kodak_id", 1)
    p = download_kodak_image(kid)
    return [{"path": p, "display_name": f"kodim{kid:02d}.png", "kodak_id": kid}]

def get_benchmark_image_name(bench_type, args, resolved_image_name=None):
    """
    Determine the image name/identifier to be recorded in the CSV for a given benchmark.
    """
    if bench_type in ["fft", "fft_benchmark"]:
        return "N/A"

    if getattr(args, "synthetic_frames", False):
        return "synthetic"

    if resolved_image_name:
        return resolved_image_name

    if getattr(args, "image", None):
        return os.path.basename(args.image)

    if bench_type in ["optical_flow", "optflow", "optical_flow_benchmark"] and getattr(args, "kodak_pair", None):
        id1, id2 = args.kodak_pair
        return f"kodim{id1:02d}.png, kodim{id2:02d}.png"

    kodak_id = getattr(args, "kodak_id", 1)
    return f"kodim{kodak_id:02d}.png"

CSV_FIELDNAMES = [
    "image",
    "config",
    "benchmark",
    "simulator",
    "threads",
    "status",
    "cycles",
    "instructions",
    "ipc",
    "branches",
    "br_misses",
    "br_miss_rate_pct",
    "ic_misses",
    "dc_accesses",
    "dc_misses",
    "dc_miss_rate_pct",
    "cache_miss_rate_pct",
    "cache_hit_rate_pct",
    "wall_clock_time_sec",
    "checksum",
    "return_code",
    "run_iteration",
    "error"
]

def export_algorithm_csv(csv_path, results_list, image_name):
    """
    Export benchmark results for a single algorithm to a CSV file.
    The image used is added as the first value on the left side.
    """
    dir_name = os.path.dirname(os.path.abspath(csv_path))
    os.makedirs(dir_name, exist_ok=True)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for r in results_list:
            row = dict(r)
            if not row.get("image"):
                row["image"] = image_name
            for k in CSV_FIELDNAMES:
                if k not in row or row[k] is None:
                    row[k] = ""
            writer.writerow(row)

def resolve_run_dir(base_output, run_idx=1, total_runs=1, timestamp_str=None, overwrite=False):
    """
    Resolve a unique folder path for a benchmark run iteration.
    """
    if base_output.endswith(".json") or base_output.endswith(".csv"):
        base_dir = os.path.dirname(os.path.abspath(base_output))
    else:
        base_dir = os.path.abspath(base_output)

    os.makedirs(base_dir, exist_ok=True)

    if timestamp_str is None:
        timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    if total_runs > 1:
        folder_name = f"run{run_idx}_{timestamp_str}"
    else:
        folder_name = f"run_{timestamp_str}"

    target_dir = os.path.join(base_dir, folder_name)

    if overwrite and total_runs == 1:
        os.makedirs(target_dir, exist_ok=True)
        return target_dir

    counter = 1
    while os.path.exists(target_dir):
        target_dir = os.path.join(base_dir, f"{folder_name}_{counter}")
        counter += 1

    os.makedirs(target_dir, exist_ok=True)
    return target_dir

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

def compile_edge_detection(env, width=32, height=32, kernel_iterations=1,
                           use_kodak=True, kodak_id=1, image_path=None,
                           flush_cache=True, flush_size_kb=256,
                           output_elf=None, image_display_name=None):
    src = os.path.join(BENCHMARKS_DIR, "edge_detection", "edge_detection_benchmark.c")
    elf = output_elf if output_elf else os.path.join(BENCHMARKS_DIR, "edge_detection", "edge_detection_benchmark.riscv")
    edge_dir = os.path.join(BENCHMARKS_DIR, "edge_detection")
    gcc_path = get_gcc_path(env)

    iter_tag = f", {kernel_iterations} iter" if kernel_iterations > 1 else ""
    flush_tag = f", cache-flush={flush_size_kb}KB" if flush_cache else ", no-flush"

    cmd = [
        gcc_path,
        "-O3",
        "-funroll-loops",
        f"-DIMG_WIDTH={width}",
        f"-DIMG_HEIGHT={height}",
        f"-DKERNEL_ITERATIONS={kernel_iterations}",
        f"-DENABLE_CACHE_FLUSH={1 if flush_cache else 0}",
        f"-DFLUSH_CACHE_SIZE_KB={flush_size_kb}",
        "-march=rv64gc",
        "-mabi=lp64d",
        "-mcmodel=medany",
        "-specs=htif_nano.specs",
        "-T", os.path.join(TESTS_DIR, "htif.ld"),
        f"-I{edge_dir}"
    ]

    if use_kodak:
        generate_edge_detection_header(width=width, height=height, kodak_id=kodak_id, image_path=image_path)
        cmd.append("-DUSE_KODAK_DATA")
        disp_name = image_display_name or (os.path.basename(image_path) if image_path else f"kodim{kodak_id:02d}.png")
        print(f"[+] Compiling Edge Detection with dataset image '{disp_name}' ({width}x{height}{iter_tag}{flush_tag}): {src}")
    else:
        print(f"[+] Compiling Edge Detection benchmark with synthetic pattern ({width}x{height}{iter_tag}{flush_tag}): {src}")

    cmd.extend([
        src,
    ]
    if atexit_src:
        cmd.extend([atexit_src, "-Wl,--wrap=atexit"])
    cmd.extend([
        "-o", elf,
        "-lm"
    ])

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

    libfftw_candidates = [
        os.path.join(fft_sw_dir, "libfftw3.a"),
        os.path.join(TESTS_DIR, "libfftw3.a")
    ]
    libfftw = next((p for p in libfftw_candidates if os.path.exists(p)), None)
    if not libfftw:
        print(f"[!] Warning: libfftw3.a not found in {fft_sw_dir} or {TESTS_DIR}. FFT compilation might fail if FFTW is not installed.")

    print(f"[+] Compiling FFTW benchmark source: {src}")
    atexit_candidates = [
        os.path.join(TESTS_DIR, "atexit-workaround.c"),
        os.path.join(BENCHMARKS_DIR, "common", "atexit-workaround.c")
    ]
    atexit_src = next((p for p in atexit_candidates if os.path.exists(p)), None)
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
    ]
    if atexit_src:
        cmd.extend([atexit_src, "-Wl,--wrap=atexit"])
    cmd.extend([
        "-o", elf,
        f"-L{fft_sw_dir}",
        f"-L{TESTS_DIR}",
        "-lfftw3",
        "-lm"
    ])

    res = subprocess.run(cmd, cwd=CHIPYARD_DIR, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        print(f"[-] Compilation failed for fft_benchmark:\n{res.stderr}")
        sys.exit(1)
    print(f"[+] Successfully compiled: {elf}")
    return elf

def compile_optical_flow(env, width=32, height=32, use_kodak=True, kodak_id=1, shift_x=1, shift_y=1, kodak_pair=None, image_path=None):
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
        generate_optical_flow_header(width=width, height=height, kodak_id=kodak_id, shift_x=shift_x, shift_y=shift_y, pair=kodak_pair, image_path=image_path)
        cmd.append("-DUSE_KODAK_DATA")
        print(f"[+] Compiling Optical Flow with Kodak dataset ({width}x{height}): {src}")
    else:
        print(f"[+] Compiling Optical Flow benchmark with synthetic frames ({width}x{height}): {src}")

    atexit_candidates = [
        os.path.join(TESTS_DIR, "atexit-workaround.c"),
        os.path.join(BENCHMARKS_DIR, "common", "atexit-workaround.c")
    ]
    atexit_src = next((p for p in atexit_candidates if os.path.exists(p)), None)
    cmd.append(src)
    if atexit_src:
        cmd.extend([atexit_src, "-Wl,--wrap=atexit"])
    cmd.extend([
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
                      shift_x=1, shift_y=1, kodak_pair=None, image_path=None,
                      flush_cache=True, flush_size_kb=256,
                      output_elf=None, image_display_name=None):
    if bench_type in ["fft", "fft_benchmark"]:
        return compile_fft_benchmark(env)
    elif bench_type in ["optical_flow", "optflow", "optical_flow_benchmark"]:
        return compile_optical_flow(env, width=width, height=height, use_kodak=use_kodak,
                                    kodak_id=kodak_id, shift_x=shift_x, shift_y=shift_y,
                                    kodak_pair=kodak_pair, image_path=image_path)
    else:
        return compile_edge_detection(env, width=width, height=height,
                                      kernel_iterations=kernel_iterations,
                                      use_kodak=use_kodak,
                                      kodak_id=kodak_id,
                                      image_path=image_path,
                                      flush_cache=flush_cache,
                                      flush_size_kb=flush_size_kb,
                                      output_elf=output_elf,
                                      image_display_name=image_display_name)

def run_verilator_sim(config_name, bench_name, elf_path, env, build_missing=False, timeout=1800, threads=1, rebuild=False):
    """Run benchmark binary on Verilator simulator for given config"""
    sim_binary = os.path.join(VERILATOR_DIR, f"simulator-chipyard.harness-{config_name}")

    # Check existing binary threads if it exists
    compiled_threads = get_simulator_threads(sim_binary) if os.path.exists(sim_binary) else None
    threads_mismatch = (compiled_threads is not None and compiled_threads != threads)
    needs_build = not os.path.exists(sim_binary) or rebuild or (build_missing and threads_mismatch)

    if needs_build:
        if build_missing or rebuild:
            rebuild_msg = "Rebuilding" if os.path.exists(sim_binary) else "Building"
            thread_reason = f" (thread count mismatch: compiled={compiled_threads}, requested={threads})" if threads_mismatch and not rebuild else ""
            print(f"[+] {rebuild_msg} Verilator simulator for {config_name} with {threads} thread(s){thread_reason} (this may take several minutes)...")
            
            if os.path.exists(sim_binary):
                clean_cmd = ["make", "-C", VERILATOR_DIR, "clean-sim", f"CONFIG={config_name}"]
                subprocess.run(clean_cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            build_cmd = [
                "make", "-C", VERILATOR_DIR,
                f"CONFIG={config_name}",
                f"VERILATOR_THREADS={threads}",
                f"-j{threads}"
            ]
            b_res = subprocess.run(build_cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if b_res.returncode != 0 or not os.path.exists(sim_binary):
                return {
                    "config": config_name,
                    "benchmark": bench_name,
                    "simulator": "verilator",
                    "threads": threads,
                    "status": "BUILD_FAILED",
                    "error": b_res.stderr[-500:] if b_res.stderr else "Build returned error code"
                }
            compiled_threads = get_simulator_threads(sim_binary)
        else:
            return {
                "config": config_name,
                "benchmark": bench_name,
                "simulator": "verilator",
                "threads": threads,
                "status": "NOT_COMPILED",
                "error": f"Verilator executable {os.path.basename(sim_binary)} does not exist. Use --build-missing to compile."
            }
    elif threads_mismatch:
        print(f"[!] Warning: {os.path.basename(sim_binary)} was compiled with {compiled_threads} thread(s), but --threads {threads} was requested.")
        print(f"[!] Simulation will run with {compiled_threads} thread(s). Use --rebuild or --build-missing to recompile with {threads} threads.")

    active_threads = compiled_threads if compiled_threads is not None else threads
    thread_str = f" ({active_threads} thread{'s' if active_threads > 1 else ''})"
    print(f"[+] Running {bench_name} on {config_name} via Verilator{thread_str}...")
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
            "threads": active_threads,
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
            "threads": active_threads,
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
            "threads": 1,
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
            "threads": 1,
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
            
            # D-Cache miss rate
            if dc_accesses > 0:
                dc_miss_rate = round(dc_misses / dc_accesses * 100, 2)
            else:
                dc_miss_rate = round(dc_misses / instret * 100, 4) if instret > 0 else 0.0

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
                "dc_miss_rate_pct": dc_miss_rate,
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
    has_image = any("image" in r and r.get("image") for r in results)
    max_img_len = max([len(str(r.get("image", ""))) for r in results] + [5]) if has_image else 0
    img_col_w = max(max_img_len, 12)

    base_w = 144
    total_w = base_w + (img_col_w + 3 if has_image else 0)

    print("\n" + "=" * total_w)
    print("BENCHMARK RESULTS SUMMARY")
    print("=" * total_w)
    if has_image:
        header = f"{'Config':<30} | {'Benchmark':<14} | {'Image':<{img_col_w}} | {'Simulator':<14} | {'Status':<7} | {'Cycles':<10} | {'IPC':<6} | {'Br Mispred':<10} | {'D$ Misses':<10} | {'I$ Misses':<9} | {'Time (s)':<8}"
    else:
        header = f"{'Config':<32} | {'Benchmark':<14} | {'Simulator':<14} | {'Status':<7} | {'Cycles':<10} | {'IPC':<6} | {'Br Mispred':<10} | {'D$ Misses':<10} | {'I$ Misses':<9} | {'Time (s)':<8}"
    print(header)
    print("-" * total_w)

    for r in results:
        cfg = r.get("config", "N/A")
        bench = r.get("benchmark", "N/A")
        sim_raw = r.get("simulator", "N/A")
        th = r.get("threads")
        if sim_raw == "verilator" and th is not None:
            sim = f"verilator({th}T)"
        else:
            sim = sim_raw
        status = r.get("status", "N/A")
        cycles = str(r.get("cycles")) if r.get("cycles") is not None else "N/A"
        ipc = str(r.get("ipc")) if r.get("ipc") is not None else "N/A"
        wtime = str(r.get("wall_clock_time_sec")) if r.get("wall_clock_time_sec") is not None else "N/A"
        
        br_miss = f"{r.get('br_miss_rate_pct', 0.0)}%" if "br_miss_rate_pct" in r else "N/A"
        dc_misses = str(r.get('dc_misses', 'N/A'))
        ic_misses = str(r.get('ic_misses', 'N/A'))

        if has_image:
            img_val = str(r.get("image", "N/A"))
            print(f"{cfg:<30} | {bench:<14} | {img_val:<{img_col_w}} | {sim:<14} | {status:<7} | {cycles:<10} | {ipc:<6} | {br_miss:<10} | {dc_misses:<10} | {ic_misses:<9} | {wtime:<8}")
        else:
            print(f"{cfg:<32} | {bench:<14} | {sim:<14} | {status:<7} | {cycles:<10} | {ipc:<6} | {br_miss:<10} | {dc_misses:<10} | {ic_misses:<9} | {wtime:<8}")

    print("=" * total_w + "\n")

def main():
    parser = argparse.ArgumentParser(description="Run benchmark suite across Chipyard processor configs.")
    parser.add_argument("--benchmark", "--algorithm", choices=["edge_detection", "fft", "fft_benchmark", "optical_flow", "optical_flow_benchmark", "all"], dest="benchmark", default="all", help="Benchmark/algorithm to run (default: all)")
    parser.add_argument("-n", "--runs", "--iterations", dest="runs", type=int, default=1, help="Number of benchmark evaluation runs to perform (default: 1)")
    parser.add_argument("--kernel-iterations", type=int, default=1, help="Sobel edge detection inner loop iterations per run (default: 1)")
    parser.add_argument("--configs", nargs="+", help="Processor configs to benchmark (default: pre-compiled verilator configs or RocketConfig)")
    parser.add_argument("--simulator", choices=["verilator", "spike", "auto"], default="auto", help="Simulation backend to use")
    parser.add_argument("-t", "--threads", "--verilator-threads", dest="threads", type=int, default=1, help="Number of threads for Verilator simulation (enables multi-core execution via `--threads N` / VERILATOR_THREADS=N)")
    parser.add_argument("--rebuild", action="store_true", help="Force rebuild of Verilator simulator binaries (e.g., when changing thread count)")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_DIR, help=f"Output directory for benchmark results (default: {DEFAULT_OUTPUT_DIR})")
    parser.add_argument("--overwrite", action="store_true", help="Allow overwriting target output directory if it exists (default: False, generates unique name)")
    parser.add_argument("--image", "--image-name", dest="image", default=None, help="Input image file path, range, or Kodak image name (e.g. 'kodim01.png', 'test.jpg', '1-5')")
    parser.add_argument("--image-range", nargs="+", default=None, help="Image range to benchmark (e.g., '1 5', '1-5', '1..5') from Kodak suite or --image-dir")
    parser.add_argument("--kodak-range", nargs="+", default=None, help="Kodak suite image range (1-24) to benchmark (e.g., '1 5', '1-5', '1..5')")
    parser.add_argument("--image-dir", "--images-dir", dest="image_dir", default=None, help="Directory containing images to benchmark")
    parser.add_argument("--images", nargs="+", default=None, help="List of image files, paths, or Kodak IDs/names to benchmark")
    parser.add_argument("--img-width", type=int, default=32, help="Image width for benchmark (default: 32)")
    parser.add_argument("--img-height", type=int, default=32, help="Image height for benchmark (default: 32)")
    parser.add_argument("--kodak-id", type=int, default=1, help="Kodak suite image ID (1-24) to use for dataset frames (default: 1)")
    parser.add_argument("--kodak-pair", type=int, nargs=2, default=None, help="Pair of Kodak image IDs (e.g. 1 2) for optical flow frames")
    parser.add_argument("--shift-x", type=int, default=1, help="Horizontal pixel shift for optical flow frame motion (default: 1)")
    parser.add_argument("--shift-y", type=int, default=1, help="Vertical pixel shift for optical flow frame motion (default: 1)")
    parser.add_argument("--synthetic-frames", action="store_true", help="Force synthetic checkerboard frames instead of Kodak/input images")
    parser.add_argument("--no-cache-flush", action="store_true", help="Disable cache flush before benchmarking (default: False, cache is flushed)")
    parser.add_argument("--flush-size-kb", type=int, default=256, help="Cache flush buffer size in KB (default: 256)")
    parser.add_argument("--build-missing", action="store_true", help="Automatically build missing Verilator binaries")
    parser.add_argument("--timeout", type=int, default=300, help="Per-run timeout in seconds (default: 300)")
    parser.add_argument("--json", action="store_true", help="Also export JSON reports alongside CSV files")
    parser.add_argument("--list-configs", action="store_true", help="List available Scala processor configs")
    args = parser.parse_args()

    if args.threads < 1:
        parser.error("--threads must be at least 1")

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

    # Resolve images for edge detection
    edge_images = []
    if "edge_detection" in benchmarks_to_run:
        edge_images = resolve_edge_detection_images(args)

    # For optical flow / single image fallback
    single_image_path = None
    resolved_image_name = None
    if getattr(args, "image", None) and not os.path.isdir(args.image) and not parse_range_spec(args.image) and "," not in args.image:
        single_image_path, resolved_image_name, _ = resolve_single_image(args.image)
    elif edge_images and len(edge_images) == 1:
        single_image_path = edge_images[0]["path"]
        resolved_image_name = edge_images[0]["display_name"]
    elif not args.synthetic_frames:
        resolved_image_name = f"kodim{args.kodak_id:02d}.png"

    # Pre-compile edge detection benchmark for each target image
    compiled_edge_elfs = []
    if "edge_detection" in benchmarks_to_run:
        num_imgs = len(edge_images)
        if num_imgs > 1:
            print(f"[+] Compiling Edge Detection benchmark for {num_imgs} target image(s)...")
        for img_info in edge_images:
            p = img_info["path"]
            disp = img_info["display_name"]
            kid = img_info["kodak_id"]
            if num_imgs > 1:
                safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', os.path.splitext(disp)[0])
                elf_target = os.path.join(BENCHMARKS_DIR, "edge_detection", f"edge_detection_benchmark_{safe_name}.riscv")
            else:
                elf_target = os.path.join(BENCHMARKS_DIR, "edge_detection", "edge_detection_benchmark.riscv")

            elf = compile_edge_detection(
                env,
                width=args.img_width,
                height=args.img_height,
                kernel_iterations=args.kernel_iterations,
                use_kodak=(not args.synthetic_frames),
                kodak_id=kid if kid is not None else args.kodak_id,
                image_path=p,
                flush_cache=(not args.no_cache_flush),
                flush_size_kb=args.flush_size_kb,
                output_elf=elf_target,
                image_display_name=disp
            )
            compiled_edge_elfs.append((img_info, elf))

    # Pre-compile other benchmarks if requested
    compiled_other_elfs = {}
    for bench in benchmarks_to_run:
        if bench == "edge_detection":
            continue
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
            kodak_pair=args.kodak_pair,
            image_path=single_image_path,
            flush_cache=(not args.no_cache_flush),
            flush_size_kb=args.flush_size_kb
        )
        compiled_other_elfs[bench] = elf

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
            if bench == "edge_detection":
                for img_info, elf_path in compiled_edge_elfs:
                    img_disp = img_info["display_name"]
                    for config in target_configs:
                        if args.simulator == "spike":
                            res = run_spike_sim(config, bench, elf_path, env, timeout=args.timeout)
                        elif args.simulator == "verilator":
                            res = run_verilator_sim(config, bench, elf_path, env, build_missing=args.build_missing, timeout=args.timeout, threads=args.threads, rebuild=args.rebuild)
                        else: # auto
                            if config in compiled_verilator or args.build_missing or args.rebuild:
                                res = run_verilator_sim(config, bench, elf_path, env, build_missing=args.build_missing, timeout=args.timeout, threads=args.threads, rebuild=args.rebuild)
                            else:
                                print(f"[!] Verilator binary not compiled for {config}. Falling back to Spike...")
                                res = run_spike_sim(config, bench, elf_path, env, timeout=args.timeout)

                        res["image"] = img_disp
                        res["run_iteration"] = run_idx
                        benchmark_results.append(res)
            else:
                elf_path = compiled_other_elfs[bench]
                img_disp = get_benchmark_image_name(bench, args, resolved_image_name)
                for config in target_configs:
                    if args.simulator == "spike":
                        res = run_spike_sim(config, bench, elf_path, env, timeout=args.timeout)
                    elif args.simulator == "verilator":
                        res = run_verilator_sim(config, bench, elf_path, env, build_missing=args.build_missing, timeout=args.timeout, threads=args.threads, rebuild=args.rebuild)
                    else: # auto
                        if config in compiled_verilator or args.build_missing or args.rebuild:
                            res = run_verilator_sim(config, bench, elf_path, env, build_missing=args.build_missing, timeout=args.timeout, threads=args.threads, rebuild=args.rebuild)
                        else:
                            print(f"[!] Verilator binary not compiled for {config}. Falling back to Spike...")
                            res = run_spike_sim(config, bench, elf_path, env, timeout=args.timeout)

                    res["image"] = img_disp
                    res["run_iteration"] = run_idx
                    benchmark_results.append(res)

        print_summary_table(benchmark_results)

        # Resolve dedicated folder for this run
        run_dir = resolve_run_dir(
            args.output,
            run_idx=run_idx,
            total_runs=args.runs,
            timestamp_str=session_timestamp,
            overwrite=args.overwrite
        )

        # Export a separate CSV file per algorithm into the run folder
        for bench in benchmarks_to_run:
            bench_results = [r for r in benchmark_results if r.get("benchmark") == bench]
            bench_img = get_benchmark_image_name(bench, args, resolved_image_name)
            csv_path = os.path.join(run_dir, f"{bench}.csv")
            export_algorithm_csv(csv_path, bench_results, bench_img)

        json_report = {
            "benchmarks_evaluated": benchmarks_to_run,
            "timestamp": run_start_timestamp,
            "run_iteration": run_idx,
            "total_runs": args.runs,
            "configs_evaluated": len(target_configs),
            "threads": args.threads,
            "results": benchmark_results
        }
        all_runs_reports.append(json_report)

        if args.json:
            json_path = os.path.join(run_dir, "benchmark_report.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(json_report, f, indent=2)

        print(f"[+] Run {run_idx} CSV results exported to folder: {run_dir}")
        for bench in benchmarks_to_run:
            print(f"    - {bench}: {os.path.join(run_dir, f'{bench}.csv')}")

    if args.runs > 1:
        if args.output.endswith(".json") or args.output.endswith(".csv"):
            base_dir = os.path.dirname(os.path.abspath(args.output))
        else:
            base_dir = os.path.abspath(args.output)

        consolidated_dir = os.path.join(base_dir, f"all_runs_{session_timestamp}")
        os.makedirs(consolidated_dir, exist_ok=True)

        for bench in benchmarks_to_run:
            all_bench_results = [
                r for rep in all_runs_reports
                for r in rep["results"]
                if r.get("benchmark") == bench
            ]
            bench_img = get_benchmark_image_name(bench, args, resolved_image_name)
            csv_path = os.path.join(consolidated_dir, f"{bench}.csv")
            export_algorithm_csv(csv_path, all_bench_results, bench_img)

        if args.json:
            combined_report = {
                "benchmarks_evaluated": benchmarks_to_run,
                "total_runs": args.runs,
                "threads": args.threads,
                "session_timestamp": session_timestamp,
                "runs": all_runs_reports
            }
            json_path = os.path.join(consolidated_dir, "benchmark_report_all_runs.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(combined_report, f, indent=2)

        print(f"[+] Consolidated all {args.runs} runs exported to folder: {consolidated_dir}")
        for bench in benchmarks_to_run:
            print(f"    - {bench}: {os.path.join(consolidated_dir, f'{bench}.csv')}")

if __name__ == "__main__":
    main()
