#ifndef LOG_H
#define LOG_H
#include "stdio.h"
#endif

#define LOG_ERR(msg)   printf("[ERR]  (%s:%d): %s\n\r", __FILE__, __LINE__, msg)
#define LOG_WARN(msg)  printf("[WARN] (%s:%d): %s\n\r", __FILE__, __LINE__, msg)
#define LOG_MSG(msg)   printf("[LOG]  (%s:%d): %s\n\r", __FILE__, __LINE__, msg)

#ifndef RELEASE_BUILD
#define DEBUG_MSG(msg) printf("[DEBUG]  (%s:%d): %s\n\r", __FILE__, __LINE__, msg)
#else
#define DEBUG_MSG(msg) //Debug: msg
#endif