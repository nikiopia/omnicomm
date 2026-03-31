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

#define BUTTON_1                (0x00800000UL)
#define BUTTON_UP               (0x00000080UL)
#define BUTTON_DOWN             (0x00000002UL)

#define PROTOCOL_I2C            (0U)
#define PROTOCOL_SPI            (1U)
#define PROTOCOL_UART           (2U)
#define PROTOCOL_RS232          (3U)
#define PROTOCOL_CAN            (4U)

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
    unsigned char protocol;
    unsigned char stateUpdated;
    unsigned char displayUpdated;
    unsigned char menuUpdated;
    unsigned char menuIndex;
    UI_ErrorType errorCode;
    unsigned int buttonEvents;
    char displayRow0[OC_SCREEN_WIDTH + 1];
    char displayRow1[OC_SCREEN_WIDTH + 1];
    unsigned char txBuffer[OC_TX_RX_BUFFER_SIZE];
    unsigned char rxBuffer[OC_TX_RX_BUFFER_SIZE];
} UI_Machine;

// ----- LISTS ----- //

char protocolMenuText[6U][17U] = {
    "Protocol:",
    "I2C",
    "SPI",
    "UART",
    "RS232",
    "CAN"
};

int protocolMenuValues[5U] = {
    PROTOCOL_I2C,
    PROTOCOL_SPI,
    PROTOCOL_UART,
    PROTOCOL_RS232,
    PROTOCOL_CAN
};

char protocolList[5U][6U] = {
    "I2C",
    "SPI",
    "UART",
    "RS232",
    "CAN"
};

unsigned int buttonEvents;

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

/*
 * @param   UI_Machine*    - machine
 * @param   char[][17U]    - menuText
 * @param   int[]          - optionValues
 * @param   unsigned char  - numOptions
 * @param   unsigned char* - currentSelection
 */
int UI_newMenuSetup(UI_Machine*, char[][17U], int[], unsigned char,
    unsigned char*);

/*
 * @param   UI_Machine*    - machine
 * @param   char[][17U]    - menuText
 * @param   int[]          - optionValues
 * @param   unsigned char  - numOptions
 * @param   unsigned char* - currentSelection
 * @param   unsigned char  - incrementMode
 */
int UI_menuChangeOption(UI_Machine*, char[][17U], int[], unsigned char,
    unsigned char*, unsigned char);

// State handling
void UI_stateUpdate(UI_Machine*);
void UI_stateAction(UI_Machine*);

void SACT_startup(UI_Machine*);
void SUPD_startup(UI_Machine*);

void SACT_protocolSelect(UI_Machine*);
void SUPD_protocolSelect(UI_Machine*);

#endif
