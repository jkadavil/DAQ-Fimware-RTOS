/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * File Name          : freertos.c
  * Description        : Code for freertos applications
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2025 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */

/* Includes ------------------------------------------------------------------*/
#include "FreeRTOS.h"
#include "task.h"
#include "main.h"
#include "cmsis_os.h"
#include "log.h"
#include "daq_config.h"
#include "math.h"
#include "can.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */

/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */
typedef struct can_msg_wrapper {
  uint32_t Reason;
  uint8_t *data;
} CANMsgWrapper;
/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */
#define MS_TO_TICKS(ms) (ms / 1000) * configTICK_RATE_HZ
/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
/* USER CODE BEGIN Variables */
extern CAN_HandleTypeDef hcan1;
/* USER CODE END Variables */
/* Definitions for MainTask */
osThreadId_t MainTaskHandle;
const osThreadAttr_t MainTask_attributes = {
  .name = "MainTask",
  .stack_size = 128 * 4,
  .priority = (osPriority_t) osPriorityNormal,
};
/* Definitions for TxCANTask */
osThreadId_t TxCANTaskHandle;
const osThreadAttr_t TxCANTask_attributes = {
  .name = "TxCANTask",
  .stack_size = 128 * 4,
  .priority = (osPriority_t) osPriorityNormal1,
};
osThreadId_t HeartbeatTaskHandle;
const osThreadAttr_t HeartbeatTaskHandle_attributes = {
  .name = "HeartbeatTask",
  .stack_size = 128 * 4,
  .priority = osPriorityNormal
};

/* Definitions for CANTxQueue */
osMessageQueueId_t CANTxQueueHandle;
const osMessageQueueAttr_t CANTxQueue_attributes = {
  .name = "CANTxQueue"
};

osMutexId_t CANMutexHandle;
const osMutexAttr_t CANMutex_attributes = {
  .name = "CANMutex",
  .attr_bits = osMutexPrioInherit | osMutexRobust
};

/* Private function prototypes -----------------------------------------------*/
/* USER CODE BEGIN FunctionPrototypes */
// void addCANQueue(uint16_t canID, uint8_t* data, uint8_t len);
void sendHeartbeatTask(void *arg);
/* USER CODE END FunctionPrototypes */

void mainTask(void *argument);
void txCANTask(void *argument);

void MX_FREERTOS_Init(void); /* (MISRA C 2004 rule 8.1) */

/**
  * @brief  FreeRTOS initialization
  * @param  None
  * @retval None
  */
void MX_FREERTOS_Init(void) {
  /* USER CODE BEGIN Init */
  /* USER CODE END Init */

  /* USER CODE BEGIN RTOS_MUTEX */
  /* add mutexes, ... */
  CANMutexHandle = osMutexNew(&CANMutex_attributes);
  if (CANMutexHandle == NULL) {
      LOG_ERR("Failed to create CANMutex");
  }
  /* USER CODE END RTOS_MUTEX */

  /* USER CODE BEGIN RTOS_SEMAPHORES */
  /* add semaphores, ... */
  /* USER CODE END RTOS_SEMAPHORES */

  /* USER CODE BEGIN RTOS_TIMERS */
  /* start timers, add new ones, ... */
  /* USER CODE END RTOS_TIMERS */

  /* Create the queue(s) */
  /* creation of CANTxQueue */
  CANTxQueueHandle = osMessageQueueNew (16, sizeof(uint16_t), &CANTxQueue_attributes);

  /* USER CODE BEGIN RTOS_QUEUES */
  /* add queues, ... */
  /* USER CODE END RTOS_QUEUES */

  /* Create the thread(s) */
  /* creation of MainTask */
  MainTaskHandle = osThreadNew(mainTask, NULL, &MainTask_attributes);

  /* creation of TxCANTask */
  TxCANTaskHandle = osThreadNew(txCANTask, NULL, &TxCANTask_attributes);

  /* USER CODE BEGIN RTOS_THREADS */
  HeartbeatTaskHandle = osThreadNew(sendHeartbeatTask, NULL, &HeartbeatTaskHandle_attributes);
  /* USER CODE END RTOS_THREADS */

  /* USER CODE BEGIN RTOS_EVENTS */
  /* add events, ... */
  /* USER CODE END RTOS_EVENTS */

}

/* USER CODE BEGIN Header_mainTask */
/**
  * @brief  Function implementing the MainTask thread.
  * @param  argument: Not used
  * @retval None
  */
/* USER CODE END Header_mainTask */
void mainTask(void *argument)
{
  /* USER CODE BEGIN mainTask */
  if (DATA_BOX_ID == 0x1FFFFFFF) {
    DEBUG_MSG("Data Box ID is 0x1FFFFF00. We are in test mode!");
  }
  /* Infinite loop */
  for(;;)
  {
    osDelay(1);
  }
  /* USER CODE END mainTask */
}

/* USER CODE BEGIN Header_txCANTask */
/**
* @brief Function implementing the TxCANTask thread.
* @param argument: Not used
* @retval None
*/
/* USER CODE END Header_txCANTask */
void txCANTask(void *argument)
{
  /* USER CODE BEGIN txCANTask */
  CAN_TxHeaderTypeDef tx_header = {
    .StdId = 0,
    .IDE = CAN_ID_EXT,
    .RTR = 0,
    .DLC = 8, // 8 bytes data important
    .TransmitGlobalTime = DISABLE // worthless
  };
  /* Infinite loop */
  for(;;)
  {
    if (osMutexAcquire(CANMutexHandle, osWaitForever) == osOK) {
      CANMsgWrapper msg;
      osMessageQueueGet(CANTxQueueHandle, &msg, NULL, osWaitForever);
      // Construct header according to CAN ID spec
      tx_header.ExtId = CAN_BUS_ID | DATA_BOX_ID | msg.Reason;
      HAL_CAN_AddTxMessage(&hcan1, &tx_header, msg.data, NULL);
      osMutexRelease(CANMutexHandle);
    }
    osDelay(1);
  }
  /* USER CODE END txCANTask */
}

/* Private application code --------------------------------------------------*/
/* USER CODE BEGIN Application */
// void addCANQueue(uint16_t canID, uint8_t* data, uint8_t len) {

// }

void sendHeartbeatTask(void *arg) {
  uint8_t data[8];
  
  CANMsgWrapper msg = {
    .Reason = REASON_HEARTBEAT,
  };

  uint32_t last_tick = 0;

  for (;;) {

    uint32_t ticks = osKernelGetTickCount(); 

    // Bits 0-3 have tick count
    data[0] = ticks & 0x000000FF;
    data[1] = (ticks & 0x0000FF00) >> 4;
    data[2] = (ticks & 0x00FF0000) >> 12;
    data[3] = (ticks & 0xFF000000) >> 28;
    
    last_tick = ticks - last_tick;
    
    // Bits 4-7 have ticks since last heartbeat
    data[4] = last_tick & 0x000000FF;
    data[5] = (last_tick & 0x0000FF00) >> 4;
    data[6] = (last_tick & 0x00FF0000) >> 12;
    data[7] = (last_tick & 0xFF000000) >> 28;
    
    osMessageQueuePut(CANTxQueueHandle, &msg, 5, osWaitForever); // is &msg a no no?
    
    msg.data = data;
    
    last_tick = ticks;

    osDelayUntil(osKernelGetTickCount() + MS_TO_TICKS(5000)); // Send heartbeat every 5 sec
  }
}
/* USER CODE END Application */

