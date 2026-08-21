#pragma once

#include "serial_log.h"

namespace serial_log {

inline int available() {
  return Serial.available();
}

inline int read() {
  return Serial.read();
}

}  // namespace serial_log
