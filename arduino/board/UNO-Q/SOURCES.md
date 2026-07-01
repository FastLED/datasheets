# Arduino UNO Q sources

| Canonical file | Original filename / label | Source URL | Retrieved |
|---|---|---|---|
| `datasheet.pdf` | `ABX00162-datasheet.pdf` — Arduino® UNO Q User Manual (SKU ABX00162-ABX00173, modified 2026-06-17), 109 pages | https://docs.arduino.cc/resources/datasheets/ABX00162-datasheet.pdf | 2026-07-01 |

Notes:
- Arduino publishes this document as "datasheet" in the URL but the cover
  self-titles it "User Manual". Kept as `datasheet.pdf` to match Arduino's
  canonical naming.
- UNO Q is a hybrid board: Qualcomm® Dragonwing™ **QRB2210** MPU
  (quad-core Cortex-A53 running Debian Linux) + STMicroelectronics
  **STM32U585** MCU (Cortex-M33 running Arduino Core on Zephyr). Register
  detail for either silicon lives with the vendor:
  - MCU: filed under `stmicroelectronics/mcu/STM32U585/` when added.
  - MPU: filed under `qualcomm/soc/QRB2210/` when added (new vendor slug).
