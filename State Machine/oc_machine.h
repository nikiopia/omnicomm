#ifndef OC_MACHINE_H
#define OC_MACHINE_H

// ----- INCLUDES ----- //
#include <stdio.h>              // DEV

// ----- DEFINES ----- //

#define OC_TRUE                 0xFF
#define OC_FALSE                0

#define OC_SCREEN_HEIGHT        2
#define OC_SCREEN_WIDTH         20

#define OC_TX_RX_BUFFER_SIZE    16

// ----- ENUMERATIONS ----- //

typedef enum UI_stateEnum {
    UI_STARTUP,
    UI_ERROR,
    UI_PROTOCOL_SELECT,
    UI_I2C_CONFIG,
    UI_SPI_CONFIG,
    UI_UART_CONFIG,
    UI_RS232_CONFIG,
    UI_CAN_CONFIG,
    UI_TX_RX
} UI_StateType;

typedef enum UI_protocolEnum {
    PROTOCOL_NONE,
    PROTOCOL_I2C,
    PROTOCOL_SPI,
    PROTOCOL_UART,
    PROTOCOL_RS232,
    PROTOCOL_CAN
} UI_ProtocolType;

typedef enum UI_errorEnum {
    EC_OK,
    EC_INIT,
    EC_DISPLAY,
    EC_MEM_WRITE,
    EC_PROTOCOL
} UI_ErrorType;

typedef enum UI_displayWriteEnum {
    MODE_TOP,
    MODE_BOTTOM
} UI_displayWriteMode;

// ----- STRUCTURES ----- //

typedef struct UI_machineStruct {
    UI_StateType state;
    UI_ProtocolType protocol;
    unsigned char stateUpdated;
    unsigned char displayUpdated;
    UI_ErrorType errorCode;
    unsigned int buttonEvents;
    char displayRow0[OC_SCREEN_WIDTH];
    char displayRow1[OC_SCREEN_WIDTH];
    unsigned char txBuffer[OC_TX_RX_BUFFER_SIZE];
    unsigned char rxBuffer[OC_TX_RX_BUFFER_SIZE];
} UI_Machine;

// ----- PROTOTYPES ----- //

// Developer Functions
void UI_printCommBuffers(UI_Machine*);

// Firmware Driver Functions
int FD_I2C1(unsigned char[], unsigned char);     // LCD
//int FD_I2C2(UI_Machine*);
//int FD_SPI(UI_Machine*);
//int FD_UART(UI_Machine*);
//int FD_RS232(UI_Machine*);
//int FD_CAN(UI_Machine*);

// Configuration Functions
int UI_init(UI_Machine*);
int UI_displayInit(void);

// Utility Functions
int UI_displayMemWrite(UI_Machine*, UI_displayWriteMode, char[]);
int UI_updateScreen(UI_Machine*);
void UI_Error(UI_Machine*, UI_ErrorType);

// State handling
void UI_stateUpdate(UI_Machine*);
void UI_stateAction(UI_Machine*);

void SACT_startup(UI_Machine*);
void SUPD_startup(UI_Machine*);

void SACT_protocolSelect(UI_Machine*);

#endif
