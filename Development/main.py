# ----- IMPORTS ----- #

from machine import I2C, SPI, UART, Pin
from time import sleep, sleep_ms, ticks_ms, ticks_diff

# ----- CONTROL "DEFINES" ----- #

CIRCULAR_BUFFER_SIZE = 3
KEYPAD_SCAN_MS_PERIOD = 20
DISCO_UPDATE_MS_PERIOD = 500

KEYCODE_1 = 0x00_80_00_00
KEYCODE_2 = 0x00_40_00_00
KEYCODE_3 = 0x00_20_00_00
KEYCODE_A = 0x00_10_00_00
KEYCODE_B = 0x00_08_00_00
KEYCODE_C = 0x00_04_00_00

KEYCODE_4 = 0x00_02_00_00
KEYCODE_5 = 0x00_01_00_00
KEYCODE_6 = 0x00_00_80_00
KEYCODE_D = 0x00_00_40_00
KEYCODE_E = 0x00_00_20_00
KEYCODE_F = 0x00_00_10_00

KEYCODE_7   = 0x00_00_08_00
KEYCODE_8   = 0x00_00_04_00
KEYCODE_9   = 0x00_00_02_00
KEYCODE_MP1 = 0x00_00_01_00
KEYCODE_UP  = 0x00_00_00_80
KEYCODE_MP2 = 0x00_00_00_40

KEYCODE_DEL   = 0x00_00_00_20
KEYCODE_0     = 0x00_00_00_10
KEYCODE_OK    = 0x00_00_00_08
KEYCODE_LEFT  = 0x00_00_00_04
KEYCODE_DOWN  = 0x00_00_00_02
KEYCODE_RIGHT = 0x00_00_00_01

KEYCODE_GROUP_DECIMAL = (KEYCODE_1 | KEYCODE_2 | KEYCODE_3 | KEYCODE_4 | KEYCODE_5 | \
                         KEYCODE_6 | KEYCODE_7 | KEYCODE_8 | KEYCODE_9 | KEYCODE_0)
KEYCODE_GROUP_HEX     = (KEYCODE_GROUP_DECIMAL | KEYCODE_A | KEYCODE_B | KEYCODE_C | \
                         KEYCODE_D | KEYCODE_E | KEYCODE_F)

# ----- GLOBAL VARIABLES ----- #

#   0 - SPI
#   1 - UART
# 255 - Not configured
protocolSelection = [255]

protocolSelectMenuText = [
    "Protocol:",
    "SPI",
    "UART"
]

# Display color mode:
# 0 - Red
# 1 - Yellow
# 2 - Green
# 3 - Cyan
# 4 - Blue
# 5 - Purple
colorMode = 1
discoMode = 0
lastDiscoUpdate = 0

# Debouncing Setup
writeIndex = 0
debouncedStates = 0
buttonFlags = 0
lastbuttonFlags = 0xFFFFFFFF
lastKeypadScan = 0
rawSwitchStates = []
for i in range(CIRCULAR_BUFFER_SIZE):
    rawSwitchStates.append(0)

# ----- MENU HELPER FUNCTIONS ----- #

def newMenuSetup(menuTextArray, menuSelection):
    # Update selection indicator
    menuSelection[0] = 0
    
    # Update screen with title and first option
    updateLCD(menuTextArray[0], menuTextArray[1])


def menuChangeOption(menuTextArray, menuSelection, numOptions,\
                     incrementMode=True):
    # Update selection
    if incrementMode:
        menuSelection[0] += 1
        if menuSelection[0] >= numOptions:
            menuSelection[0] = 0
    else:
        menuSelection[0] -= 1
        # No unsigned bytes so have to check for negativity
        if menuSelection[0] < 0:
            menuSelection[0] = numOptions - 1
    
    # Show newly selected option
    updateLCD(menuTextArray[0], menuTextArray[1 + menuSelection[0]])



# ----- UTILITY FUNCTIONS ----- #

def stringToLCDCommand(inputString, useTopRow=1):
    # Parameter check
    if inputString is None:
        return
    
    # DDRAM address set to high/low row addresses
    returnBytes = b'\x80'
    if useTopRow == 1:
        returnBytes += b'\x80'
    else:
        returnBytes += b'\xC0'
    
    # Input string to DDRAM write byte sequence
    readIndex = 0
    while readIndex < 16 and readIndex < len(inputString):
        if readIndex == (len(inputString) - 1) or readIndex == 15:
            returnBytes += b'\x40'
        else:
            returnBytes += b'\xC0'
        
        returnBytes += ord(inputString[readIndex]).to_bytes(1, "big")
        readIndex += 1
    
    return returnBytes


def columnScanner(scanCode):
    for i in range(6):
        scanCode <<= 1
        scanCode |= (colPins[i].value() & 1)
    
    return scanCode


def doKeypadScan():
    global rawSwitchStates, writeIndex, debouncedStates, lastDebouncedStates, buttonFlags
    
    # ----- SCAN CODE ----- #
    scanCode = 0
    
    # First row
    row0Pin.value(1)
    row1Pin.value(0)
    row2Pin.value(0)
    row3Pin.value(0)
    scanCode = columnScanner(scanCode)
    
    # Second row
    row0Pin.value(0)
    row1Pin.value(1)
    scanCode = columnScanner(scanCode)
    
    # Third row
    row1Pin.value(0)
    row2Pin.value(1)
    scanCode = columnScanner(scanCode)
    
    # Fourth row
    row2Pin.value(0)
    row3Pin.value(1)
    scanCode = columnScanner(scanCode)
    
    # Turn off fourth row
    row3Pin.value(0)
    
    # ----- DEBOUNCING STATE MACHINE ----- #
    
    # Sample inputs
    rawSwitchStates[writeIndex] = (scanCode & 0x00_FF_FF_FF)
    
    # Update write index as circular buffer
    writeIndex += 1
    if writeIndex >= CIRCULAR_BUFFER_SIZE:
        writeIndex = 0
    
    # Compute stableHigh, stableLow
    stableHigh = 0xFFFFFFFF
    stableLow = 0
    for i in range(CIRCULAR_BUFFER_SIZE):
        stableHigh &= rawSwitchStates[i]
        stableLow |= rawSwitchStates[i]
    
    # Determine new debounced states, and rising edge events
    lastDebouncedStates = debouncedStates
    debouncedStates = (debouncedStates & stableLow) | stableHigh
    buttonFlags |= (debouncedStates ^ lastDebouncedStates) & debouncedStates


def addRemoveHexKey(newChar, addMode=True):
    global buttonFlags, userInpTX
    
    lastChar = userInpTX[-1:]
    if addMode:
        if newChar is None:
            return
        if newChar == "":
            return
        
        # Add new character
        userInpTX += newChar
        if lastChar != "" and lastChar != " ":
            userInpTX += " "
    else:
        # Remove a character
        if lastChar == "":
            return
        
        if lastChar == " ":
            userInpTX = userInpTX[:-2]
        else:
            userInpTX = userInpTX[:-1]


def cycleColorMode():
    global colorMode
    
    colorMode += 1
    if colorMode >= 6:
        colorMode = 0
    
    txBytes = b'\x08'
    if colorMode == 0:
        # Red
        txBytes += b'\x10'
    elif colorMode == 1:
        # Yellow
        txBytes += b'\x14'
    elif colorMode == 2:
        # Green
        txBytes += b'\x04'
    elif colorMode == 3:
        # Cyan
        txBytes += b'\x05'
    elif colorMode == 4:
        # Blue
        txBytes += b'\x01'
    elif colorMode == 5:
        # Purple
        txBytes += b'\x11'
    
    i2cObj.writeto(96, txBytes, True)



# ----- HARDWARE DRIVER FUNCTIONS ----- #

def updateLCD(topString, bottomString):
    # Clear display
    i2cObj.writeto(62, b'\x00\x01', True)
    sleep_ms(4)
    
    # Update screen rows
    if topString is not None:
        txBytes = stringToLCDCommand(topString, 1)
        i2cObj.writeto(62, txBytes, True)
    
    if bottomString is not None:
        txBytes = stringToLCDCommand(bottomString, 0)
        i2cObj.writeto(62, txBytes, True)


def HD_SPI(outByte):
    # Check parameter
    if outByte is None:
        return
    
    # Send outByte to SPI bus
    inByte = b''
    spiObj.write_readinto(outByte, inByte)
    if inByte is None:
        inBytes = b''
    
    # Return response
    return inByte


def HD_UART(outBytes):
    # Check parameter
    if outBytes is None:
        return
    
    # Send bytes to UART
    uartObj.write(outBytes)
    
    # Read bytes from UART (If any)
    inBytes = uartObj.read(numRxBytes)
    if inBytes is None:
        inBytes = b''
    
    # Return response
    return inBytes



# ----- SETUP FUNCTIONS ----- #

def setupLCD():
    # LCD Controller init. sequence
    sleep_ms(20)
    i2cObj.writeto(62, b'\x00\x38', True) # Function set select
    sleep_ms(4)
    i2cObj.writeto(62, b'\x00\x0C', True) # Display ON/OFF control
    sleep_ms(4)
    i2cObj.writeto(62, b'\x00\x01', True) # Clear display
    sleep_ms(4)
    i2cObj.writeto(62, b'\x00\x06', True) # Entry mode set
    
    # Backlight controller init. sequence
    sleep_ms(4)
    i2cObj.writeto(96, b'\x00\x01', True) # Set in normal mode
    sleep_ms(4)
    i2cObj.writeto(96, b'\x08\x04', True) # Enable the green LED


def setup():
    global i2cObj, spiObj, uartObj, colPins, row0Pin, row1Pin
    global row2Pin, row3Pin
    
    # LCD Setup
    i2cObj = I2C(0, scl=Pin(9), sda=Pin(8), \
        freq=100000)
    setupLCD()
    
    # SPI Setup
    spiObj = SPI(0, baudrate=10000, polarity=0, \
        phase=0, bits=8, firstbit=SPI.MSB, sck=Pin(2), mosi=Pin(3), miso=Pin(4))
    spiNCS = Pin(5)
    
    # UART Setup
    uartObj = UART(0, baudrate=9600, bits=8, \
    parity=None, stop=1)
    
    # Column Setup
    col0Pin = Pin(13, Pin.IN, Pin.PULL_DOWN)
    col1Pin = Pin(12, Pin.IN, Pin.PULL_DOWN)
    col2Pin = Pin(11, Pin.IN, Pin.PULL_DOWN)
    col3Pin = Pin(10, Pin.IN, Pin.PULL_DOWN)
    col4Pin = Pin(15, Pin.IN, Pin.PULL_DOWN)
    col5Pin = Pin(14, Pin.IN, Pin.PULL_DOWN)
    colPins = [col0Pin, col1Pin, col2Pin, col3Pin, col4Pin, col5Pin]
    
    # Row Setup
    row0Pin = Pin(21, Pin.OUT)
    row1Pin = Pin(20, Pin.OUT)
    row2Pin = Pin(19, Pin.OUT)
    row3Pin = Pin(18, Pin.OUT)



# ----- MAIN LOOP ----- #

def main():
    global lastbuttonFlags, lastKeypadScan, buttonFlags
    global userInpTX, windowOffset, discoMode, lastDiscoUpdate
    
    # Startup configuration
    setup()
    
    # Display splash text
    updateLCD("Project", "OmniComm")
    sleep(5)
    
    bottomRow = "RX:"
    userInpTX = ""
    lastUserInpTX = "0"
    windowOffset = 0
    lastOffset = 1
    while 1:
        # Keypad scanning asynchronous delay
        now = ticks_ms()
        if ticks_diff(now, lastKeypadScan) >= KEYPAD_SCAN_MS_PERIOD:
            lastKeypadScan = now
            
            # Get button inputs
            doKeypadScan()
            
            # Update screen if new event occurs
            #if (buttonFlags ^ lastbuttonFlags) != 0:
            #    updateLCD("buttonFlags:", "0x{0:08X}".format(buttonFlags))
            #
            #lastbuttonFlags = buttonFlags
            
            # Utility key checks
            if (buttonFlags & KEYCODE_MP2) != 0:
                buttonFlags &= ~(KEYCODE_MP2)
                cycleColorMode()
            
            if (buttonFlags & KEYCODE_MP1) != 0:
                buttonFlags &= ~(KEYCODE_MP1)
                discoMode ^= 1
            
            # Key code test
            if (buttonFlags & KEYCODE_0) != 0:
                buttonFlags &= ~(KEYCODE_0)
                addRemoveHexKey("0", True)
            if (buttonFlags & KEYCODE_1) != 0:
                buttonFlags &= ~(KEYCODE_1)
                addRemoveHexKey("1", True)
            if (buttonFlags & KEYCODE_2) != 0:
                buttonFlags &= ~(KEYCODE_2)
                addRemoveHexKey("2", True)
            if (buttonFlags & KEYCODE_3) != 0:
                buttonFlags &= ~(KEYCODE_3)
                addRemoveHexKey("3", True)
            if (buttonFlags & KEYCODE_4) != 0:
                buttonFlags &= ~(KEYCODE_4)
                addRemoveHexKey("4", True)
            if (buttonFlags & KEYCODE_5) != 0:
                buttonFlags &= ~(KEYCODE_5)
                addRemoveHexKey("5", True)
            if (buttonFlags & KEYCODE_6) != 0:
                buttonFlags &= ~(KEYCODE_6)
                addRemoveHexKey("6", True)
            if (buttonFlags & KEYCODE_7) != 0:
                buttonFlags &= ~(KEYCODE_7)
                addRemoveHexKey("7", True)
            if (buttonFlags & KEYCODE_8) != 0:
                buttonFlags &= ~(KEYCODE_8)
                addRemoveHexKey("8", True)
            if (buttonFlags & KEYCODE_9) != 0:
                buttonFlags &= ~(KEYCODE_9)
                addRemoveHexKey("9", True)
            if (buttonFlags & KEYCODE_A) != 0:
                buttonFlags &= ~(KEYCODE_A)
                addRemoveHexKey("A", True)
            if (buttonFlags & KEYCODE_B) != 0:
                buttonFlags &= ~(KEYCODE_B)
                addRemoveHexKey("B", True)
            if (buttonFlags & KEYCODE_C) != 0:
                buttonFlags &= ~(KEYCODE_C)
                addRemoveHexKey("C", True)
            if (buttonFlags & KEYCODE_D) != 0:
                buttonFlags &= ~(KEYCODE_D)
                addRemoveHexKey("D", True)
            if (buttonFlags & KEYCODE_E) != 0:
                buttonFlags &= ~(KEYCODE_E)
                addRemoveHexKey("E", True)
            if (buttonFlags & KEYCODE_F) != 0:
                buttonFlags &= ~(KEYCODE_F)
                addRemoveHexKey("F", True)
            if (buttonFlags & KEYCODE_DEL) != 0:
                buttonFlags &= ~(KEYCODE_DEL)
                addRemoveHexKey(None, False)
            
            if (buttonFlags & KEYCODE_LEFT) != 0:
                buttonFlags &= ~(KEYCODE_LEFT)
                windowOffset += 1
            if (buttonFlags & KEYCODE_RIGHT) != 0:
                buttonFlags &= ~(KEYCODE_RIGHT)
                windowOffset -= 1
            
            txLen = len(userInpTX)
            if txLen <= 12:
                if userInpTX != lastUserInpTX:
                    updateLCD("TX: {0}".format(userInpTX), bottomRow)
                    lastUserInpTX = userInpTX
            else:
                # Always show new content
                if userInpTX != lastUserInpTX:
                    windowOffset = 0
                    updateLCD("TX: {0}".format(userInpTX[(txLen - 12):(txLen)]), bottomRow)
                    lastUserInpTX = userInpTX
                    continue
                
                # Clamp window offset into usable range
                if windowOffset > (txLen - 12):
                    windowOffset = txLen - 12
                elif windowOffset < 0:
                    windowOffset = 0
                
                if windowOffset != lastOffset:
                    updateLCD("TX: {0}".format(userInpTX[(txLen - 12 - windowOffset):(txLen - windowOffset)]), bottomRow)
                    lastOffset = windowOffset
        
        now = ticks_ms()
        if discoMode and ticks_diff(now, lastDiscoUpdate) >= DISCO_UPDATE_MS_PERIOD:
            lastDiscoUpdate = now
            cycleColorMode()


main()