// #include <stdio.h>
// #include <stdint.h>
// #include <math.h>

// #include <string.h>
// #include <stdlib.h>
// #include <riscv-pk/encoding.h>

// #include "image_data.h"  

// // Scratchpad-Adresse MUSS mit deiner Chipyard-Konfiguration übereinstimmen
// #define SPAD_BASE  0x08000000UL
// #define WIDTH      600
// #define HEIGHT     600
// #define NPIX       (WIDTH * HEIGHT)

// // Layout im Scratchpad
// #define SPAD_GRAY   ((volatile uint8_t*)(SPAD_BASE))
// #define SPAD_EDGES  ((volatile uint8_t*)(SPAD_BASE + NPIX))

// // Lokaler Speicher im DRAM zum Exportieren
// static uint8_t edges_export[NPIX];

// //static uint8_t image_data[600][600];

// //uint8_t* dataAddr = &image_data; //??




// int main() {
//     //printf("[INFO] Using scratchpad at 0x%08lx\n", (unsigned long)SPAD_BASE);
//     printf("[INFO] Writing input image into scratchpad...\n");
//     //printf("Addr:%p\n ",dataAddr );

//     // ----------------------------------------------------------------------
//     // 1. Graubild ins Scratchpad kopieren
//     // ----------------------------------------------------------------------
//     for (int y = 0; y < HEIGHT; y++) {
//         for (int x = 0; x < WIDTH; x++) {
//             SPAD_GRAY[y * WIDTH + x] = image_data[y][x];
//         }
//     }

//     //----------------------------------------------------------------------
//     // 2. Sobel-Matrizen
//     //----------------------------------------------------------------------
//     const int Gx[3][3] = {
//         { -1, 0, 1 },
//         { -2, 0, 2 },
//         { -1, 0, 1 }
//     };
//     const int Gy[3][3] = {
//         { -1, -2, -1 },
//         {  0,  0,  0 },
//         {  1,  2,  1 }
//     };

//     //printf("[INFO] Running Sobel operator...\n");

//     //----------------------------------------------------------------------
//     // 3. Sobel-Kanten direkt im Scratchpad berechnen
//     //----------------------------------------------------------------------
//     for (int y = 1; y < HEIGHT - 1; y++) {
//         for (int x = 1; x < WIDTH - 1; x++) {

//             int sumX = 0;
//             int sumY = 0;

//             for (int ky = -1; ky <= 1; ky++) {
//                 for (int kx = -1; kx <= 1; kx++) {
//                     int pixel = SPAD_GRAY[(y + ky) * WIDTH + (x + kx)];
//                     sumX += pixel * Gx[ky + 1][kx + 1];
//                     sumY += pixel * Gy[ky + 1][kx + 1];
//                 }
//             }

//             int magnitude = (int)sqrt((double)(sumX * sumX + sumY * sumY));
//             if (magnitude > 255) magnitude = 255;

//             SPAD_EDGES[y * WIDTH + x] = (uint8_t)magnitude;
//         }
//     }

//     //printf("[INFO] Copying edge data from scratchpad to local buffer...\n");

//     //----------------------------------------------------------------------
//     // 4. Ergebnis in lokales Array kopieren (Verilator-kompatibel)
//     //----------------------------------------------------------------------
//     for (int i = 0; i < NPIX; i++)
//         edges_export[i] = SPAD_EDGES[i];

//     //----------------------------------------------------------------------
//     // 5. Debug-Ausgabe / Kontrollsumme
//     //----------------------------------------------------------------------
//     unsigned long sum = 0;
//     for (int i = 0; i < NPIX; i++)
//         sum += edges_export[i];

//     printf("[INFO] Edge detection completed.\n");
//     //printf("[INFO] Average edge intensity = %lu\n", sum / NPIX);

//     //----------------------------------------------------------------------
//     // 6. Daten für Host bereitstellen
//     //----------------------------------------------------------------------
//     printf("[INFO] Edge result is now in edges_export[]\n");
//     //printf("[INFO] You can dump it to a .h file on the host side.\n");

//     return 0;
// }


#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#include "image_data.h"
#include "sim_data.h"
//#include "edges_output.h" // Warum existiert diese Datei nicht?

#define WIDTH  133
#define HEIGHT 100
#define NPIX   (WIDTH * HEIGHT)

// Statische Arrays (liegen im DRAM bzw. im simulierten RAM)
static uint8_t gray[NPIX];
static uint8_t edges[NPIX];
static uint8_t overlay[NPIX * 3];   // RGB Overlay
//static uint8_t edges_export[NPIX];
//uint8_t edges_output[5][5];



int main() {

    printf("[INFO] Starting edge detection...\n");

    //----------------------------------------------------------------------
    // 1. Bild in eindimensionales Array kopieren
    //----------------------------------------------------------------------
    for (int y = 0; y < HEIGHT; y++) {
        for (int x = 0; x < WIDTH; x++) {
            //gray[y * WIDTH + x] = image_data[y][x];
            gray[y * WIDTH + x] = image_data[y][x];
        }
    }

    //----------------------------------------------------------------------
    // 2. Sobel-Kernel definieren
    //----------------------------------------------------------------------
    const int Gx[3][3] = {
        {-1, 0, 1},
        {-2, 0, 2},
        {-1, 0, 1}
    };
    const int Gy[3][3] = {
        {-1, -2, -1},
         {0,  0,  0},
         {1,  2,  1}
    };

    //----------------------------------------------------------------------
    // 3. Sobel-Kantenberechnung
    //----------------------------------------------------------------------
    for (int y = 1; y < HEIGHT - 1; y++) {
        for (int x = 1; x < WIDTH - 1; x++) {

            int sumX = 0;
            int sumY = 0;

            for (int ky = -1; ky <= 1; ky++) {
                for (int kx = -1; kx <= 1; kx++) {
                    int pixel = gray[(y + ky) * WIDTH + (x + kx)];
                    sumX += pixel * Gx[ky + 1][kx + 1];
                    sumY += pixel * Gy[ky + 1][kx + 1];
                }
            }

            int magnitude = (int)sqrt((double)(sumX * sumX + sumY * sumY));
            if (magnitude > 255) magnitude = 255;

            edges[y * WIDTH + x] = (uint8_t)magnitude;
        }
    }

    //----------------------------------------------------------------------
    // 4. Overlay-Bild erzeugen (reines RGB-Array)
    //----------------------------------------------------------------------
    for (int i = 0; i < NPIX; i++) {
        uint8_t v = gray[i];

        overlay[3*i + 0] = v;
        overlay[3*i + 1] = v;
        overlay[3*i + 2] = v;

        if (edges[i] > 100) {
            overlay[3*i + 0] = 255; // rot
            overlay[3*i + 1] = 0;
            overlay[3*i + 2] = 0;
        }
    }

    //----------------------------------------------------------------------
    // 5. Ergebnis in export-Array kopieren (für Host)
    //----------------------------------------------------------------------
    // for (int i = 0; i < NPIX; i++)
    //     edges_export[i] = edges[i];

    
    for (int y = 0; y < HEIGHT; y++) {
        for (int x = 0; x < WIDTH; x++) {
            //("edges: %i\n", edges[y * WIDTH + x]);
            //edges_output[y][x] = edges[y * WIDTH + x];
            printf("%i\n", edges[y * WIDTH + x]);
        }
    }

    //----------------------------------------------------------------------
    // 6. Kontrollsumme ausgeben
    //----------------------------------------------------------------------
    // unsigned long sum = 0;
    // for (int i = 0; i < NPIX; i++) sum += edges[i];

    //printf("[INFO] Average edge intensity = %lu\n", sum / NPIX);
    printf("[INFO] Done.\n");

    return 0;
}



