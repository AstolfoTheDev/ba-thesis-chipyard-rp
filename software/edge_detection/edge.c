// #define STB_IMAGE_WRITE_IMPLEMENTATION
// #include "stb_image_write.h"

// #include <stdio.h>
// #include <stdlib.h>
// #include <math.h>
// #include <stdint.h>
// #include "image_data.h"  

// int main() {
//     const int width = 600;
//     const int height = 600;

//     // Speicher für Eingabe (Graustufen) und Ausgabe (Kanten)
//     uint8_t *gray = malloc(width * height);
//     uint8_t *edges = calloc(width * height, 1);
//     if (!gray || !edges) {
//         printf("Error: Speicher konnte nicht zugewiesen werden!\n");
//         return 1;
//     }

//     // Kopiere Bild aus image_data.h in 1D-Array
//     for (int y = 0; y < height; y++) {
//         for (int x = 0; x < width; x++) {
//             gray[y * width + x] = image_data[y][x];
//         }
//     }

//     // Sobel-Operatoren
//     const int Gx[3][3] = {
//         {-1, 0, 1},
//         {-2, 0, 2},
//         {-1, 0, 1}
//     };
//     const int Gy[3][3] = {
//         {-1, -2, -1},
//         { 0,  0,  0},
//         { 1,  2,  1}
//     };

//     // Sobel-Kantenberechnung
//     for (int y = 1; y < height - 1; y++) {
//         for (int x = 1; x < width - 1; x++) {
//             int sumX = 0;
//             int sumY = 0;

//             for (int ky = -1; ky <= 1; ky++) {
//                 for (int kx = -1; kx <= 1; kx++) {
//                     int pixel = gray[(y + ky) * width + (x + kx)];
//                     sumX += pixel * Gx[ky + 1][kx + 1];
//                     sumY += pixel * Gy[ky + 1][kx + 1];
//                 }
//             }

//             int magnitude = (int)sqrt((double)(sumX * sumX + sumY * sumY));
//             if (magnitude > 255) magnitude = 255;
//             edges[y * width + x] = (uint8_t)magnitude;
//         }
//     }

//     // Ergebnis speichern (nur wenn Dateisystem vorhanden ist)
//     if (stbi_write_png("edges.png", width, height, 1, edges, width)) {
//         printf("result saved in: edges.png\n");
//     } else {
//         printf("Warning: Result could not be saved .\n");
//     }

//     // Überlagerung mit Originalbild erzeugen
//     uint8_t *overlay = malloc(width * height * 3);
//     if (!overlay) {
//         //printf("Error: no memory for the overlay could be assigned\n");
//         free(gray);
//         free(edges);
//         return 1;
//     }

//     for (int i = 0; i < width * height; i++) {
//         uint8_t val = gray[i];
//         overlay[i * 3 + 0] = val;
//         overlay[i * 3 + 1] = val;
//         overlay[i * 3 + 2] = val;

//         if (edges[i] > 100) { // Schwellenwert für sichtbare Kanten
//             overlay[i * 3 + 0] = 255; // Rot
//             overlay[i * 3 + 1] = 0;
//             overlay[i * 3 + 2] = 0;
//         }
//     }

//     // if (stbi_write_png("overlay.png", width, height, 3, overlay, width * 3)) {
//     //     printf("Überlagerung gespeichert: overlay.png\n");
//     // } else {
//     //     printf("Warnung: Overlay-Bild konnte nicht gespeichert werden.\n");
//     // }

//     // Optional: Mittelwert der Kantenintensität zur Kontrolle
//     unsigned long sum = 0;
//     for (int i = 0; i < width * height; i++) sum += edges[i];
//     printf("Kantenberechnung abgeschlossen. Durchschnitt = %lu\n", sum / (width * height));

//     // Aufräumen
//     free(gray);
//     free(edges);
//     free(overlay);
//     return 0;
// }

#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "stb_image_write.h"
#include <stdio.h>
#include <stdint.h>
#include <math.h>
#include "image_data.h"


#define WIDTH  600
#define HEIGHT 600
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

    
    // for (int y = 0; y < HEIGHT; y++) {
    //     for (int x = 0; x < WIDTH; x++) {
    //         //("edges: %i\n", edges[y * WIDTH + x]);
    //         edges_output[y][x] = edges[y * WIDTH + x];
    //         //printf("edges_output: %i\n", edges_output[y][x]);
    //     }
    // }

    if (stbi_write_png("edges.png", WIDTH, HEIGHT, 1, edges, WIDTH)) {
        printf("result saved in: edges.png\n");
    } else {
        printf("Warning: Result could not be saved .\n");
    }

    //memcpy(addr, edges, sizeof(NPIX));

    //----------------------------------------------------------------------
    // 6. Kontrollsumme ausgeben
    //----------------------------------------------------------------------
    // unsigned long sum = 0;
    // for (int i = 0; i < NPIX; i++) sum += edges[i];

    //printf("[INFO] Average edge intensity = %lu\n", sum / NPIX);
    printf("[INFO] edges_export[] is ready for dumping to a .h file.\n");

    return 0;
}
