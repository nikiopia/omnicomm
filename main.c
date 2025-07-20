#include "oc_statemachine.c"
#include <stdio.h>

int renderDisplay(OC_SysType *machine)
{
    if (!machine) { return 1; }

    char topRow[DISPLAY_COLS + 1];
    char bottomRow[DISPLAY_COLS + 1];
    for (int i = 0; i < DISPLAY_COLS; i++)
    {
        topRow[i] = machine->displayMem[i];
        bottomRow[i] = machine->displayMem[DISPLAY_COLS + i];
    }
    topRow[DISPLAY_COLS] = 0;
    bottomRow[DISPLAY_COLS] = 0;

    printf("'%s'\n'%s'\n",topRow,bottomRow);
    
    return 0;
}

int main(int argc, char **argv)
{
    int returnValue;

    OC_SysType machine;
    returnValue = OC_InitMachine(&machine);
    if (returnValue) { return returnValue; }

    while (1)
    {
        // Show display
        returnValue = renderDisplay(&machine);
        if (returnValue) { return returnValue; }

        // Get keypress
        char temp;
        char lastChar = 0;
        char keypress = 0;
        while ((temp = (char)(fgetc(stdin))))
        {
            if (temp == 0x0a)
            {
                keypress = lastChar;
                break;
            }
            
            lastChar = temp;
        }
        printf("keypress = '%c'\n",keypress);

        returnValue = OC_StateUpdate(&machine, keypress);
        if (returnValue) { return returnValue; }

        returnValue = OC_DoStateAction(&machine);
        if (returnValue) { return returnValue; }
    }

    return 0;
}
