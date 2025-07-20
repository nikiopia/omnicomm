#ifndef OC_STATEMACHINE_C
#define OC_STATEMACHINE_C

// ===== INCLUDES ===== //
#include "oc_statemachine.h"

// ===== FUNCTIONS ===== //

// Machine constructor
int OC_InitMachine(OC_SysType *machine)
{
    if (!machine) { return 1; }

    // Step 1 -- Display memory
    char *title1 = "Project Omnicomm";
    char *title2 = "I2C SPI UART RS232";
    OC_DisplayMemWrite(machine, title1, OC_TOP_ROW);
    OC_DisplayMemWrite(machine, title2, OC_BOTTOM_ROW);

    // Step 2 -- State variable
    machine->state = OC_IDLE;

    // Step 3 -- New state flag
    machine->newStateFlag = OC_NEW_STATE;

    // Step 4 -- Blank out the TX/RX buffers
    // TODO

    return 0;
}

// State machine core functions
int OC_StateUpdate(OC_SysType *machine, char lastKeypress)
{
    // Check machine param
    if (!machine) { return 1; }

    OC_StateType currentState;
    currentState = machine->state;
    if (currentState > OC_SYS_UTIL) { return 1; }

    int returnValue = 1;
    switch (currentState)
    {
        case OC_IDLE:
            returnValue = OC_SU_Idle(machine, lastKeypress);
            break;
        case OC_BUFFER_RW:
            returnValue = OC_SU_BufferRW(machine, lastKeypress);
            break;
        case OC_PROTOCOL_SELECT:
            break;
        case OC_TYPING:
            break;
        case OC_TX_RX:
            break;
        case OC_SYS_UTIL:
            break;
        default:
            returnValue = 1;
    }

    return returnValue;
}

int OC_DoStateAction(OC_SysType *machine)
{
    if (!machine) { return 1; }

    OC_StateType currentState;
    currentState = machine->state;
    if (currentState > OC_SYS_UTIL) { return 1; }

    int returnValue = 1;
    switch (currentState)
    {
        case OC_IDLE:
            returnValue = OC_SA_Idle(machine);
            break;
        case OC_BUFFER_RW:
            returnValue = OC_SA_BufferRW(machine);
            break;
        case OC_PROTOCOL_SELECT:
            break;
        case OC_TYPING:
            break;
        case OC_TX_RX:
            break;
        case OC_SYS_UTIL:
            break;
        default:
            returnValue = 1;
    }

    return returnValue;
}

//
void OC_DisplayMemWrite(OC_SysType *machine, char *input, char mode)
{
    if (!machine || !input) { return; }

    // Get mode options
    int rowIndex = (int)(mode & OC_MASK_ROW);
    int blankOtherRow = (int)(mode & OC_MASK_BLANK);
    
    // Determine row offsets
    int activeRowOffset, otherRowOffset;
    if (rowIndex)
    {
        activeRowOffset = DISPLAY_COLS;
        otherRowOffset = 0;
    }
    else
    {
        activeRowOffset = 0;
        otherRowOffset = DISPLAY_COLS;
    }

    // Begin reading from input and blanking other row if needed
    int readingString = 1;
    char writeChar;
    for (int i = 0; i < DISPLAY_COLS; i++)
    {
        writeChar = ' ';
        if (readingString)
        {
            if (*(input + i) == 0)
            {
                readingString = 0;
            }
            else
            {
                writeChar = *(input + i);
            }
        }
        machine->displayMem[activeRowOffset + i] = writeChar;

        if (blankOtherRow)
        {
            machine->displayMem[otherRowOffset + i] = ' ';
        }
    }
    machine->displayMem[2 * DISPLAY_COLS] = 0;
}
//

// State-unique update functions
int OC_SU_Idle(OC_SysType *machine, char keypress)
{
    if (!machine) { return 1; }

    if (keypress == 's')
    {
        machine->state = OC_BUFFER_RW;
        machine->newStateFlag = OC_NEW_STATE;
    }

    return 0;
}

int OC_SU_BufferRW(OC_SysType *machine, char keypress)
{
    if (!machine) { return 1; }

    if (keypress == 'b')
    {
        machine->state = OC_IDLE;
        machine->newStateFlag = OC_NEW_STATE;
    }

    return 0;
}

// State-unique action functions
int OC_SA_Idle(OC_SysType *machine)
{
    if (!machine) { return 1; }

    if (machine->newStateFlag == OC_NEW_STATE)
    {
        machine->newStateFlag = 0;

        char *menu1 = "(S)end (U)tility";
        char *menu2 = "(P)rotocol";

        OC_DisplayMemWrite(machine, menu1, OC_TOP_ROW);
        OC_DisplayMemWrite(machine, menu2, OC_BOTTOM_ROW);
    }

    return 0;
}

int OC_SA_BufferRW(OC_SysType *machine)
{
    if (!machine) { return 1; }

    if (machine->newStateFlag == OC_NEW_STATE)
    {
        machine->newStateFlag = 0;

        char *topRow = "TX: XX";
        char *bottomRow = "RX:";

        OC_DisplayMemWrite(machine, topRow, OC_TOP_ROW);
        OC_DisplayMemWrite(machine, bottomRow, OC_BOTTOM_ROW);
    }

    return 0;
}

#endif
