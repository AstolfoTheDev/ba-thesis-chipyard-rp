from PIL import Image
import numpy as np

pic = input("Please enter the name of the picture (with ending):")
# 1. load image and convert it to greyscale
#img = Image.open("test.png").convert("L")
img = Image.open(pic).convert("L")

# 2. adjust the size of the image to  64x64
#img = img.resize((64, 64))

# 3. convert into NumPy-Array 
pixel_data = np.array(img, dtype=np.uint8) 

#print(pixel_data) #Just a test

# export it as a C-array
with open("image_data.h", "w") as f:
    f.write("#ifndef IMAGE_DATA_H\n#define IMAGE_DATA_H\n\n")
    f.write("#include <stdint.h>\n\n")
    f.write("const uint8_t image_data[600][600] = {\n") #600 was 64 before changing
    for row in pixel_data:
        line = ", ".join(f"{val:3d}" for val in row)
        f.write(f"    {{{line}}},\n")
    f.write("};\n\n#endif\n")

print("Data written to image_data.h \n \n Completed")
# import matplotlib.pyplot as plt

# fft_result = np.fft.fft2(pixel_data)
# fft_magnitude = np.abs(np.fft.fftshift(fft_result))

# plt.imshow(np.log(fft_magnitude + 1), cmap='gray')
# plt.title("FFT des Bildes")
# plt.colorbar()
# plt.show()
