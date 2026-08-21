/*
 * microSD card read/write demo for the Waveshare ESP32-P4-WIFI6-Touch-LCD-XC.
 *
 * The microSD slot is wired to the SDIO 3.0 interface:
 *   CLK=GPIO43, CMD=GPIO44, D0=GPIO39, D1=GPIO40, D2=GPIO41, D3=GPIO42
 */
#include <Arduino.h>
#include <SD_MMC.h>
#include <FS.h>
#include "serial_log.h"

#define SD_CLK 43
#define SD_CMD 44
#define SD_D0  39
#define SD_D1  40
#define SD_D2  41
#define SD_D3  42

void setup() {
  serial_log::begin(115200);
  delay(500);

  if (!SD_MMC.setPins(SD_CLK, SD_CMD, SD_D0, SD_D1, SD_D2, SD_D3)) {
    serial_log::println("SD_MMC pin configuration failed");
    return;
  }
  if (!SD_MMC.begin("/sdcard", false /* use D0-D3 in 4-bit mode */)) {
    serial_log::println("Card mount failed - insert a FAT32-formatted microSD card");
    return;
  }

  uint8_t cardType = SD_MMC.cardType();
  char status[96];
  snprintf(status, sizeof(status), "Card type: %s",
    cardType == CARD_MMC ? "MMC" : cardType == CARD_SD ? "SDSC" : cardType == CARD_SDHC ? "SDHC" : "UNKNOWN");
  serial_log::println(status);
  snprintf(status, sizeof(status), "Card size: %llu MB", (unsigned long long)(SD_MMC.cardSize() / (1024 * 1024)));
  serial_log::println(status);
  snprintf(status, sizeof(status), "Total space: %llu MB", (unsigned long long)(SD_MMC.totalBytes() / (1024 * 1024)));
  serial_log::println(status);
  snprintf(status, sizeof(status), "Used space: %llu MB", (unsigned long long)(SD_MMC.usedBytes() / (1024 * 1024)));
  serial_log::println(status);

  const char *path = "/hello_lcd_xc.txt";
  File f = SD_MMC.open(path, FILE_WRITE);
  if (!f) {
    serial_log::println("Failed to open file for writing");
    return;
  }
  f.println("Hello from ESP32-P4-WIFI6-Touch-LCD-XC microSD demo!");
  f.close();
  serial_log::println("Wrote /hello_lcd_xc.txt");

  f = SD_MMC.open(path, FILE_READ);
  if (f) {
    serial_log::println("Read back:");
    char contents[128] = {};
    size_t count = f.readBytes(contents, sizeof(contents) - 1);
    contents[count] = '\0';
    serial_log::println(contents);
    f.close();
  }

  serial_log::println("Listing root directory:");
  File root = SD_MMC.open("/");
  File entry = root.openNextFile();
  while (entry) {
    snprintf(status, sizeof(status), "  %s (%u bytes)", entry.name(), (unsigned)entry.size());
    serial_log::println(status);
    entry = root.openNextFile();
  }
  root.close();
  serial_log::println("SD card demo finished");
}

void loop() {
  delay(1000);
}
