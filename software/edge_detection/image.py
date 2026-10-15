import os
import sys
import urllib.request
from PIL import Image
import numpy as np

MIDDLEBURY_BASE_URL = "https://vision.middlebury.edu/stereo/data/scenes2021"
MIDDLEBURY_SCENES = [
    "artroom1", "artroom2", "bandsaw1", "bandsaw2",
    "chess1", "chess2", "chess3", "curule1",
    "curule2", "curule3", "ladder1", "ladder2",
    "octogons1", "octogons2", "pendulum1", "pendulum2",
    "podium1", "skates1", "skates2", "skiboots1",
    "skiboots2", "skiboots3", "traproom1", "traproom2"
]

def download_middlebury_scene(scene_name, cache_dir="middlebury_images"):
    scene_dir = os.path.join(cache_dir, scene_name)
    os.makedirs(scene_dir, exist_ok=True)
    p0 = os.path.join(scene_dir, "im0.png")
    p1 = os.path.join(scene_dir, "im1.png")
    for p, name in [(p0, "im0.png"), (p1, "im1.png")]:
        if not os.path.exists(p) or os.path.getsize(p) == 0:
            url = f"{MIDDLEBURY_BASE_URL}/data/{scene_name}/{name}"
            print(f"Downloading {url}...")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r, open(p, "wb") as f:
                f.write(r.read())
    return p0, p1

if len(sys.argv) > 1:
    pic = sys.argv[1].strip()
else:
    pic = input("Please enter the name of the picture or Middlebury scene (e.g. 'artroom1' or 'test.jpg'): ").strip()

# Check if input corresponds to a Middlebury scene
scene_match = None
clean_pic = pic.rstrip("/").split("/")[-1].lower()
for s in MIDDLEBURY_SCENES:
    if s.lower() == clean_pic:
        scene_match = s
        break

if scene_match:
    print(f"[+] Processing Middlebury 2021 stereo scene '{scene_match}'...")
    p0, p1 = download_middlebury_scene(scene_match)

    # 1. Generate optical_flow_data.h for optical flow algorithm (32x32)
    img0 = Image.open(p0).convert("L").resize((32, 32), Image.Resampling.BILINEAR)
    img1 = Image.open(p1).convert("L").resize((32, 32), Image.Resampling.BILINEAR)
    frame1 = list(img0.tobytes())
    frame2 = list(img1.tobytes())
    npix = 32 * 32

    with open("optical_flow_data.h", "w") as f:
        f.write("/* Auto-generated header containing Middlebury stereo frames for Optical Flow Benchmark */\n")
        f.write("#ifndef OPTICAL_FLOW_DATA_H\n#define OPTICAL_FLOW_DATA_H\n\n#include <stdint.h>\n\n")
        f.write("#define USE_KODAK_DATA 1\n")
        f.write(f'#define OPTICAL_FLOW_DATASET_NAME "Middlebury 2021 ({scene_match})"\n')
        f.write("#define KODAK_IMG_WIDTH  32\n#define KODAK_IMG_HEIGHT 32\n#define KODAK_NPIX       1024\n\n")
        f.write("static const uint8_t kodak_frame1[KODAK_NPIX] = {\n")
        for idx in range(0, npix, 16):
            f.write("    " + ", ".join(f"{val:3d}" for val in frame1[idx:idx+16]) + ",\n")
        f.write("};\n\nstatic const uint8_t kodak_frame2[KODAK_NPIX] = {\n")
        for idx in range(0, npix, 16):
            f.write("    " + ", ".join(f"{val:3d}" for val in frame2[idx:idx+16]) + ",\n")
        f.write("};\n\n#endif\n")
    print(f"Optical flow dataset written to optical_flow_data.h (32x32)")

    # 2. Also export image_data.h using im0
    img = Image.open(p0).convert("L").resize((64, 64), Image.Resampling.BILINEAR)
    pixel_data = np.array(img, dtype=np.uint8)
    h, w = pixel_data.shape
    with open("image_data.h", "w") as f:
        f.write("#ifndef IMAGE_DATA_H\n#define IMAGE_DATA_H\n\n#include <stdint.h>\n\n")
        f.write(f"const uint8_t image_data[{h}][{w}] = {{\n")
        for row in pixel_data:
            line = ", ".join(f"{val:3d}" for val in row)
            f.write(f"    {{{line}}},\n")
        f.write("};\n\n#endif\n")
    print(f"Data written to image_data.h ({w}x{h}) \n \n Completed")

else:
    # 1. load image and convert it to greyscale
    img = Image.open(pic).convert("L")

    # 2. adjust the size of the image to 64x64 if necessary or keep
    # 3. convert into NumPy-Array 
    pixel_data = np.array(img, dtype=np.uint8) 
    h, w = pixel_data.shape

    # export it as a C-array
    with open("image_data.h", "w") as f:
        f.write("#ifndef IMAGE_DATA_H\n#define IMAGE_DATA_H\n\n#include <stdint.h>\n\n")
        f.write(f"const uint8_t image_data[{h}][{w}] = {{\n")
        for row in pixel_data:
            line = ", ".join(f"{val:3d}" for val in row)
            f.write(f"    {{{line}}},\n")
        f.write("};\n\n#endif\n")

    print(f"Data written to image_data.h ({w}x{h}) \n \n Completed")
# import matplotlib.pyplot as plt

# fft_result = np.fft.fft2(pixel_data)
# fft_magnitude = np.abs(np.fft.fftshift(fft_result))

# plt.imshow(np.log(fft_magnitude + 1), cmap='gray')
# plt.title("FFT des Bildes")
# plt.colorbar()
# plt.show()
