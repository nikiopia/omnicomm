#ifndef OC_MACHINE_C
#define OC_MACHINE_C

// ----- INCLUDES ----- //
#include "oc_machine.h"

/*
 * Developer Functions
 */

void UI_printCommBuffers(UI_Machine *machine)
{
    // DEV
    if (!machine) { return; }

    printf("txBuffer:\n");
    for (unsigned char i = 0; i < OC_TX_RX_BUFFER_SIZE; i++)
    {
        printf(" %02X", machine->txBuffer[i]);
    }
    printf("\nrxBuffer:\n");
    for (unsigned char i = 0; i < OC_TX_RX_BUFFER_SIZE; i++)
    {
        printf(" %02X", machine->rxBuffer[i]);
    }
    printf("\n\n");
}

/*
 * Firmware Driver Functions
 */

int FD_I2C1(unsigned char outBytes[], unsigned char length)
{
    // DEV
    for (unsigned char i = 0; i < length; i++)
    {
        printf("I2C1: TX %02X\n", outBytes[i]);
    }
    printf("\n");
    
    return 0;
}

/*
 * Configuration Functions
 */

int UI_init(UI_Machine *machine)
{
    if (!machine) { return 1; }

    // Machine flags
    machine->state = UI_STARTUP;
    machine->stateUpdated = OC_TRUE;
    machine->protocol = PROTOCOL_NONE;
    machine->displayUpdated = OC_FALSE;
    machine->errorCode = EC_OK;
    machine->buttonEvents = 0;

    // Fill display memory with blank characters
    for (unsigned char i = 0; i < OC_SCREEN_WIDTH; i++)
    {
        machine->displayRow0[i] = ' ';
        machine->displayRow1[i] = ' ';
    }

    // Empty the TX/RX buffers
    for (unsigned char i = 0; i < OC_TX_RX_BUFFER_SIZE; i++)
    {
        machine->txBuffer[i] = 0;
        machine->rxBuffer[i] = 0;
    }

    return 0;
}

int UI_displayInit(void)
{
    // DEV
    unsigned char configBytes[] = {
        '\x00','\x20','\x30','\x69'
    };

    if (FD_I2C1(configBytes, 4)) { return 1; }

    return 0;
}

/*
 * Utility Functions
 */

int UI_displayMemWrite(UI_Machine *machine, UI_displayWriteMode mode,
    char str[])
{
    if (!machine) { return 1; }

    char *writeIndex;
    switch (mode)
    {
        case MODE_TOP:
            writeIndex = &(machine->displayRow0[0]);
            break;
        case MODE_BOTTOM:
            writeIndex = &(machine->displayRow1[0]);
            break;
        default:
            return 1;
    }

    unsigned char keepReading = OC_TRUE;
    for (unsigned char i = 0; i < OC_SCREEN_WIDTH; i++)
    {
        if (keepReading && str[i] == 0)
        {
            keepReading = OC_FALSE;
        }

        if (keepReading)
        {
            *writeIndex = str[i];
        }
        else
        {
            *writeIndex = ' ';
        }
        writeIndex++;
    }

    return 0;
}

int UI_updateScreen(UI_Machine *machine)
{
    if (!machine) { return 1; }

    printf("displayRow0:\n");
    for (unsigned char i = 0; i < OC_SCREEN_WIDTH; i++)
    {
        printf(" %02X'%c'", machine->displayRow0[i], machine->displayRow0[i]);
    }
    printf("\ndisplayRow1:\n");
    for (unsigned char i = 0; i < OC_SCREEN_WIDTH; i++)
    {
        printf(" %02X'%c'", machine->displayRow1[i], machine->displayRow1[i]);
    }
    printf("\n\n");
    
    return 0;
}

void UI_Error(UI_Machine *machine, UI_ErrorType code)
{
    if (!machine) { return; }

    machine->state = UI_ERROR;
    machine->stateUpdated = OC_TRUE;
    machine->errorCode = code;
}

/*
 * State handling
 */

void UI_stateAction(UI_Machine *machine)
{
    if (!machine) { return; }

    switch (machine->state)
    {
        case UI_STARTUP:
            SACT_startup(machine);
            break;
        case UI_PROTOCOL_SELECT:
            SACT_protocolSelect(machine);
            break;
        default:
            break;
    }
}

void UI_stateUpdate(UI_Machine *machine)
{
    if (!machine) { return; }

    // DEV
    printf("Enter button events (hex): ");
    scanf("%X", &(machine->buttonEvents));

    switch (machine->state)
    {
        case UI_STARTUP:
            SUPD_startup(machine);
            break;
        default:
            break;
    }
}

void SACT_startup(UI_Machine *machine)
{
    if (!machine) { return; }

    if (machine->stateUpdated)
    {
        machine->stateUpdated = OC_FALSE;

        // Initialize display
        if (UI_displayInit())
        {
            UI_Error(machine, EC_DISPLAY);
            return;
        }

        // Put startup text on display
        char topString[] = "Project";
        char bottomString[] = "OmniComm";
        if (UI_displayMemWrite(machine, MODE_TOP, topString) ||
            UI_displayMemWrite(machine, MODE_BOTTOM, bottomString))
        {
            UI_Error(machine, EC_MEM_WRITE);
            return;
        }

        machine->displayUpdated = OC_TRUE;
    }
}

void SUPD_startup(UI_Machine *machine)
{
    if (!machine) { return; }

    if (machine->buttonEvents)
    {
        machine->state = UI_PROTOCOL_SELECT;
        machine->stateUpdated = OC_TRUE;
    }
}

void SACT_protocolSelect(UI_Machine *machine)
{
    if (!machine) { return; }

    if (machine->stateUpdated)
    {
        machine->stateUpdated = OC_FALSE;

        char str1[] = "Protocol:";
        char str2[] = "I2C";
        if (UI_displayMemWrite(machine, MODE_TOP, str1) ||
            UI_displayMemWrite(machine, MODE_BOTTOM, str2))
        {
            UI_Error(machine, EC_MEM_WRITE);
            return;
        }

        machine->displayUpdated = OC_TRUE;
    }
}

int main(int argc, char **argv)
{
    UI_Machine machine;

    // Configuration
    if (UI_init(&machine))
    {
        UI_Error(&machine, EC_INIT);
    }

    // Hand control over to the state machine
    while (1)
    {
        UI_stateAction(&machine);
        UI_stateUpdate(&machine);

        if (machine.displayUpdated && machine.state != UI_ERROR)
        {
            machine.displayUpdated = OC_FALSE;
            if (UI_updateScreen(&machine))
            {
                UI_Error(&machine, EC_DISPLAY);
            }
        }
    }

    return 0;
}

#endif
