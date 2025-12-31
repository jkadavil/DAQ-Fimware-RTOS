#ifndef DAQ_CONFIG_H
#define DAQ_CONFIG_H

// Placeholder constants. Must be changed in build
#ifndef CANBUS_CONFIG
#define CAN_BUS_ID  0x04000000
#define DATA_BOX_ID 0x00F00000

#endif

typedef enum daq_can_msg_reason {
  REASON_NULL, // cannot use!!
  REASON_HEARTBEAT,


  // Examples of other stuff to add
//   REASON_TIRE_TEMP,
//   REASON_SHOCK_POT,
//   REASON_RIDE_HEIGHT,
//   REASON_WHEEL_SPEED,
//   REASON_COOLING_FAN_SPEED,

} DAQCANMsgReason;


#endif