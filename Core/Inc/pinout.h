#ifndef PINOUT_H
#define PINOUT_H
#include "stm32l432xx.h"
#include "stm32l4xx_hal_gpio.h"
#endif

#define ADC1 GPIOA, GPIO_PIN_1
#define ADC2 GPIOA, GPIO_PIN_2
#define ADC3 GPIOA, GPIO_PIN_3
#define ADC4 GPIOA, GPIO_PIN_4
#define ADC5 GPIOA, GPIO_PIN_5
#define ADC6 GPIOA, GPIO_PIN_6
#define ADC7 GPIOB, GPIO_PIN_0

#define GP1 GPIOC, GPIO_PIN_14
#define GP2 GPIOC, GPIO_PIN_15
#define GP3 GPIOB, GPIO_PIN_0
#define GP4 GPIOA, GPIO_PIN_8

#define TogglePin(gpio) HAL_GPIO_TogglePin(gpio)
#define SetPin(gpio) HAL_GPIO_WritePin(gpio, GPIO_PIN_SET)
#define ResetPin(gpio) HAL_GPIO_WritePin(gpio, GPIO_PIN_RESET)  
#define WritePin(gpio, state) HAL_GPIO_WritePin(gpio, state)
#define ReadDigitalPin(gpio) HAL_GPIO_ReadPin(gpio)