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

# Disco mode setup, aka cycle through colors
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

# TX/RX state variables
txScrolling = True
topRow = "~TX"
bottomRow = " RX"
txString = ""
rxString = ""
lastTxString = "0"
lastRxString = "0"

updateTopRow = False
forceTopRowUpdate = False
updateBottomRow = False
forceBottomRowUpdate = False

txWindowOffset = 0
rxWindowOffset = 0
lastTxOffset = 1
lastRxOffset = 1

displayUpdated = True


# ----- MENU HELPER FUNCTIONS ----- #

def newMenuSetup(menuTextArray, menuSelection):
    global topRow, bottomRow, displayUpdated
    
    # Update selection indicator
    menuSelection[0] = 0
    
    # Update screen with title and first option
    topRow = menuTextArray[0]
    bottomRow = menuTextArray[1]
    displayUpdated = True


def menuChangeOption(menuTextArray, menuSelection, numOptions,\
                     incrementMode=True):
    global topRow, bottomRow, displayUpdated
    
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
    #topRow = menuTextArray[0]
    bottomRow = menuTextArray[1 + menuSelection[0]]
    displayUpdated = True



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
    global buttonFlags, txString, updateTopRow
    
    # Get last two characters
    secondToLastChar = txString[-2:-1]
    lastChar = txString[-1:]
    
    # Make comparisons easy
    if secondToLastChar == "":
        secondToLastChar = " "
    if lastChar == "":
        lastChar = " "
    
    if addMode:
        if newChar is None:
            return
        if newChar == "":
            return
        
        # Add new character
        if lastChar != " " and secondToLastChar != " ":
            txString += " "
        
        txString += newChar
    else:
        if lastChar == " " and secondToLastChar == " ":
            return
        
        # Remove a character
        if secondToLastChar == " " and len(txString) > 1:
            txString = txString[:-2]
        else:
            txString = txString[:-1]
    
    # Mark topRow for update
    updateTopRow = True


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


def updateTopRowString():
    global topRow, updateTopRow, lastTxString, displayUpdated
    global txWindowOffset, lastTxOffset, forceTopRowUpdate
    
    updateTopRow = False
    tempTopRow = ""
    if txScrolling:
        tempTopRow = "~TX "
    else:
        tempTopRow = " TX "
    
    txLen = len(txString)
    if txLen <= 12:
        if txString != lastTxString or forceTopRowUpdate:
            forceTopRowUpdate = False
            
            # Full string can fit on screen
            tempTopRow += txString
            lastTxString = txString
            
            topRow = tempTopRow
            displayUpdated = True
    else:
        # Always show new content
        if txString != lastTxString:
            txWindowOffset = 0
            tempTopRow += txString[(txLen - 12):(txLen)]
            lastTxString = txString
            
            topRow = tempTopRow
            displayUpdated = True
        else:
            # Clamp window offset into usable range
            if txWindowOffset > (txLen - 12):
                txWindowOffset = txLen - 12
            elif txWindowOffset < 0:
                txWindowOffset = 0
            
            if txWindowOffset != lastTxOffset or forceTopRowUpdate:
                forceTopRowUpdate = False
                
                tempTopRow += txString[(txLen - 12 - txWindowOffset):(txLen - txWindowOffset)]
                lastTxOffset = txWindowOffset
                
                topRow = tempTopRow
                displayUpdated = True


def updateBottomRowString():
    global bottomRow, updateBottomRow, lastRxString, displayUpdated
    global rxWindowOffset, lastRxOffset, forceBottomRowUpdate
    
    updateBottomRow = False
    tempBottomRow = ""
    if txScrolling:
        tempBottomRow = " RX "
    else:
        tempBottomRow = "~RX "
    
    rxLen = len(rxString)
    if rxLen <= 12:
        if rxString != lastRxString or forceBottomRowUpdate:
            forceBottomRowUpdate = False
            
            # Full string can fit on screen
            tempBottomRow += rxString
            lastRxString = rxString
            
            bottomRow = tempBottomRow
            displayUpdated = True
    else:
        # Always show new content
        if rxString != lastRxString:
            rxWindowOffset = 0
            tempBottomRow += rxString[(rxLen - 12):(rxLen)]
            lastRxString = rxString
            
            bottomRow = tempBottomRow
            displayUpdated = True
        else:
            # Clamp window offset into usable range
            if rxWindowOffset > (rxLen - 12):
                rxWindowOffset = rxLen - 12
            elif rxWindowOffset < 0:
                rxWindowOffset = 0
            
            if rxWindowOffset != lastRxOffset or forceBottomRowUpdate:
                forceBottomRowUpdate = False
                
                tempBottomRow += rxString[(rxLen - 12 - rxWindowOffset):(rxLen - rxWindowOffset)]
                lastRxOffset = rxWindowOffset
                
                bottomRow = tempBottomRow
                displayUpdated = True


def sendAndListen():
    global rxString, updateBottomRow
    
    if txString == "":
        return
    
    # TX String (From user) to bytes
    txBytes = b''
    currentByte = b''
    txStrings = txString.split()
    for element in txStrings:
        if len(element) == 1:
            txBytes += currentByte.fromhex("0" + element)
        else:
            txBytes += currentByte.fromhex(element)
    
    # Do the TX/RX maamajamma
    if protocolSelect == 0:
        rxBytes = HD_SPI(txBytes)
    elif protocolSelect == 1:
        rxBytes = HD_UART(txBytes)
    
    # RX bytes to RX string for display
    rxString = ""
    for i in range(len(rxBytes)):
        rxString += " {0:02X}".format(rxBytes[i])
    if rxString != "":
        rxString = rxString[1:]
    
    # Please update bottom row now :3
    updateBottomRow = True



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


def HD_SPI(outBytes):
    # Check parameter
    if outBytes is None:
        return
    
    # Pull down NCS pin
    spiNCS.value(0)
    
    # Send outByte to SPI bus
    inBytes = b''
    spiObj.write_readinto(outBytes, inBytes)
    if inBytes is None:
        inBytes = b''
    
    # Return NCS to high state
    spiNCS.value(1)
    
    # Return response
    return inBytes


def HD_UART(outBytes):
    # Check parameter
    if outBytes is None:
        return
    
    # Send bytes to UART
    uartObj.write(outBytes)
    
    # Read bytes from UART (If any)
    inBytes = uartObj.read()
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
    global i2cObj, colPins, row0Pin, row1Pin
    global row2Pin, row3Pin
    
    # LCD Setup
    i2cObj = I2C(0, scl=Pin(9), sda=Pin(8), \
        freq=100000)
    setupLCD()
    
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


def initTXRX_device():
    global uartObj, spiObj, spiNCS
    
    if protocolSelect == 0:
        # SPI Setup
        spiObj = SPI(0, baudrate=SPI_baudrate, polarity=SPI_polarity, \
            phase=SPI_phase, bits=SPI_dataBits, firstbit=SPI.MSB, sck=Pin(2), mosi=Pin(3), miso=Pin(4))
        spiNCS = Pin(5)
        spiNCS.value(1)
    elif protocolSelect == 1:
        # UART Setup
        uartObj = UART(0, baudrate=UART_baudrate, bits=UART_dataBits, \
        parity=UART_parity, stop=UART_stopBits)



# ----- STATE INFORMATION ----- #

# General state variables
# state:
# 0 - protocolSelect (SPI / UART)
# 1 - UART baud (9600* / 115200)
# 2 - UART data bits (8* / 9)
# 3 - UART parity (None* / Even / Odd)
# 4 - UART stop bits (1* / 2)
# 5 - SPI baud (10000*, 100000)
# 6 - SPI data bits (8*)
# 7 - SPI polarity (0* / 1)
# 8 - SPI phase (0* / 1)
# 9 - TX/RX
state = 0
stateUpdated = True

# Protocol Select
protocolSelect_menuText = [
    "Protocol:",
    "SPI",
    "UART"
]
protocolSelect_numOptions = len(protocolSelect_menuText) - 1
protocolSelect_mode = [0]
protocolSelect = 0

# UART baud
UART_baud_menuText = [
    "UART Baudrate:",
    "9600",
    "115200"
]
UART_baud_numOptions = len(UART_baud_menuText) - 1
UART_baud_mode = [0]
UART_baudrate = 9600

# UART data bits
UART_dataBits_menuText = [
    "UART Data Bits:",
    "7 bits",
    "8 bits"
]
UART_dataBits_numOptions = len(UART_dataBits_menuText) - 1
UART_dataBits_mode = [0]
UART_dataBits = 7

# UART parity
UART_parity_menuText = [
    "UART Parity:",
    "None",
    "Even",
    "Odd"
]
UART_parity_numOptions = len(UART_parity_menuText) - 1
UART_parity_mode = [0]
UART_parity = None

# UART stop bits
UART_stopBits_menuText = [
    "UART Stop Bits:",
    "1 bit",
    "2 bits"
]
UART_stopBits_numOptions = len(UART_stopBits_menuText) - 1
UART_stopBits_mode = [0]
UART_stopBits = 1

# SPI baud
SPI_baud_menuText = [
    "SPI Baudrate:",
    "10 kHz",
    "100 kHz"
]
SPI_baud_numOptions = len(SPI_baud_menuText) - 1
SPI_baud_mode = [0]
SPI_baudrate = 10000

# SPI data bits
SPI_dataBits_menuText = [
    "SPI Data Bits:",
    "8 bits"
]
SPI_dataBits_numOptions = len(SPI_dataBits_menuText) - 1
SPI_dataBits_mode = [0]
SPI_dataBits = 8

# SPI polarity
SPI_polarity_menuText = [
    "SPI Clock Idle:",
    "Low Idle",
    "High Idle"
]
SPI_polarity_numOptions = len(SPI_polarity_menuText) - 1
SPI_polarity_mode = [0]
SPI_polarity = 0

# SPI phase
SPI_phase_menuText = [
    "SPI Phase:",
    "0: Sample, Setup",
    "1: Setup, Sample"
]
SPI_phase_numOptions = len(SPI_phase_menuText) - 1
SPI_phase_mode = [0]
SPI_phase = 0

doAnotherCheck = False
protocolConfigDone = False


# ----- STATE FUNCTIONS ----- #

def stateTick_TXRX():
    global buttonFlags, txScrolling, forceTopRowUpdate, forceBottomRowUpdate
    global txWindowOffset, rxWindowOffset, updateTopRow, updateBottomRow
    
    # OK (Send) key
    if (buttonFlags & KEYCODE_OK) != 0:
        buttonFlags &= ~(KEYCODE_OK)
        sendAndListen()
    
    # Hexadecimal keys
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
    
    # Arrow keys
    if (buttonFlags & (KEYCODE_UP | KEYCODE_DOWN)) != 0:
        buttonFlags &= ~(KEYCODE_UP | KEYCODE_DOWN)
        txScrolling = not(txScrolling)
        forceTopRowUpdate = True
        forceBottomRowUpdate = True
    if (buttonFlags & KEYCODE_LEFT) != 0:
        buttonFlags &= ~(KEYCODE_LEFT)
        if txScrolling:
            txWindowOffset += 1
            updateTopRow = True
        else:
            rxWindowOffset += 1
            updateBottomRow = True
    if (buttonFlags & KEYCODE_RIGHT) != 0:
        buttonFlags &= ~(KEYCODE_RIGHT)
        if txScrolling:
            txWindowOffset -= 1
            updateTopRow = True
        else:
            rxWindowOffset -= 1
            updateBottomRow = True
    
    # Update top/bottom rows
    if updateTopRow or forceTopRowUpdate:
        updateTopRow = False
        updateTopRowString()
    if updateBottomRow or forceBottomRowUpdate:
        updateBottomRow = False
        updateBottomRowString()


def stateTick():
    global state, stateUpdated, buttonFlags, doAnotherCheck, protocolConfigDone
    
    # Return parameters
    global protocolSelect, UART_baudrate, UART_dataBits, UART_parity, UART_stopBits
    global SPI_baudrate, SPI_dataBits, SPI_polarity, SPI_phase
    global forceTopRowUpdate, forceBottomRowUpdate
    
    if state == 0:
        # Protocol Select
        if stateUpdated:
            stateUpdated = False
            newMenuSetup(protocolSelect_menuText, protocolSelect_mode)
        else:
            if (buttonFlags & KEYCODE_RIGHT) != 0:
                buttonFlags &= ~(KEYCODE_RIGHT)
                stateUpdated = True
                if protocolSelect_mode[0] == 0:
                    # SPI selected
                    protocolSelect = 0
                    stateUpdated = True
                    state = 5
                elif protocolSelect_mode[0] == 1:
                    # UART selected
                    protocolSelect = 1
                    stateUpdated = True
                    state = 1
            if (buttonFlags & KEYCODE_UP) != 0:
                buttonFlags &= ~(KEYCODE_UP)
                menuChangeOption(protocolSelect_menuText, protocolSelect_mode,\
                                 protocolSelect_numOptions, incrementMode=False)
            if (buttonFlags & KEYCODE_DOWN) != 0:
                buttonFlags &= ~(KEYCODE_DOWN)
                menuChangeOption(protocolSelect_menuText, protocolSelect_mode,\
                                 protocolSelect_numOptions, incrementMode=True)
    elif state == 1:
        # UART baud
        if stateUpdated:
            stateUpdated = False
            newMenuSetup(UART_baud_menuText, UART_baud_mode)
        else:
            if (buttonFlags & KEYCODE_LEFT) != 0:
                buttonFlags &= ~(KEYCODE_LEFT)
                stateUpdated = True
                state = 0
            if (buttonFlags & KEYCODE_RIGHT) != 0:
                buttonFlags &= ~(KEYCODE_RIGHT)
                stateUpdated = True
                if UART_baud_mode[0] == 0:
                    UART_baudrate = 9600
                elif UART_baud_mode[0] == 1:
                    UART_baudrate = 115200
                state = 2
            if (buttonFlags & KEYCODE_UP) != 0:
                buttonFlags &= ~(KEYCODE_UP)
                menuChangeOption(UART_baud_menuText, UART_baud_mode,\
                                 UART_baud_numOptions, incrementMode=False)
            if (buttonFlags & KEYCODE_DOWN) != 0:
                buttonFlags &= ~(KEYCODE_DOWN)
                menuChangeOption(UART_baud_menuText, UART_baud_mode,\
                                 UART_baud_numOptions, incrementMode=True)
    elif state == 2:
        # UART data bits
        if stateUpdated:
            stateUpdated = False
            newMenuSetup(UART_dataBits_menuText, UART_dataBits_mode)
        else:
            if (buttonFlags & KEYCODE_LEFT) != 0:
                buttonFlags &= ~(KEYCODE_LEFT)
                stateUpdated = True
                state = 1
            if (buttonFlags & KEYCODE_RIGHT) != 0:
                buttonFlags &= ~(KEYCODE_RIGHT)
                stateUpdated = True
                if UART_dataBits_mode[0] == 0:
                    UART_dataBits = 7
                elif UART_dataBits_mode[0] == 1:
                    UART_dataBits = 8
                state = 3
            if (buttonFlags & KEYCODE_UP) != 0:
                buttonFlags &= ~(KEYCODE_UP)
                menuChangeOption(UART_dataBits_menuText, UART_dataBits_mode,\
                                 UART_dataBits_numOptions, incrementMode=False)
            if (buttonFlags & KEYCODE_DOWN) != 0:
                buttonFlags &= ~(KEYCODE_DOWN)
                menuChangeOption(UART_dataBits_menuText, UART_dataBits_mode,\
                                 UART_dataBits_numOptions, incrementMode=True)
    elif state == 3:
        # UART parity
        if stateUpdated:
            stateUpdated = False
            newMenuSetup(UART_parity_menuText, UART_parity_mode)
        else:
            if (buttonFlags & KEYCODE_LEFT) != 0:
                buttonFlags &= ~(KEYCODE_LEFT)
                stateUpdated = True
                state = 2
            if (buttonFlags & KEYCODE_RIGHT) != 0:
                buttonFlags &= ~(KEYCODE_RIGHT)
                stateUpdated = True
                if UART_parity_mode[0] == 0:
                    UART_parity = None
                elif UART_parity_mode[0] == 1:
                    UART_parity = 0
                elif UART_parity_mode[0] == 2:
                    UART_parity = 1
                state = 4
            if (buttonFlags & KEYCODE_UP) != 0:
                buttonFlags &= ~(KEYCODE_UP)
                menuChangeOption(UART_parity_menuText, UART_parity_mode,\
                                 UART_parity_numOptions, incrementMode=False)
            if (buttonFlags & KEYCODE_DOWN) != 0:
                buttonFlags &= ~(KEYCODE_DOWN)
                menuChangeOption(UART_parity_menuText, UART_parity_mode,\
                                 UART_parity_numOptions, incrementMode=True)
    elif state == 4:
        # UART stop bits
        if stateUpdated:
            stateUpdated = False
            newMenuSetup(UART_stopBits_menuText, UART_stopBits_mode)
        else:
            if (buttonFlags & KEYCODE_LEFT) != 0:
                buttonFlags &= ~(KEYCODE_LEFT)
                stateUpdated = True
                state = 3
            if (buttonFlags & KEYCODE_RIGHT) != 0:
                buttonFlags &= ~(KEYCODE_RIGHT)
                stateUpdated = True
                if UART_stopBits_mode[0] == 0:
                    UART_stopBits = 1
                elif UART_stopBits_mode[0] == 1:
                    UART_stopBits = 2
                
                forceTopRowUpdate = True
                forceBottomRowUpdate = True
                protocolConfigDone = True
                state = 9
            if (buttonFlags & KEYCODE_UP) != 0:
                buttonFlags &= ~(KEYCODE_UP)
                menuChangeOption(UART_stopBits_menuText, UART_stopBits_mode,\
                                 UART_stopBits_numOptions, incrementMode=False)
            if (buttonFlags & KEYCODE_DOWN) != 0:
                buttonFlags &= ~(KEYCODE_DOWN)
                menuChangeOption(UART_stopBits_menuText, UART_stopBits_mode,\
                                 UART_stopBits_numOptions, incrementMode=True)
    elif state == 5:
        # SPI baud
        if stateUpdated:
            stateUpdated = False
            newMenuSetup(SPI_baud_menuText, SPI_baud_mode)
        else:
            if (buttonFlags & KEYCODE_LEFT) != 0:
                buttonFlags &= ~(KEYCODE_LEFT)
                stateUpdated = True
                state = 0
            if (buttonFlags & KEYCODE_RIGHT) != 0:
                buttonFlags &= ~(KEYCODE_RIGHT)
                stateUpdated = True
                if SPI_baud_mode[0] == 0:
                    SPI_baudrate = 10000
                elif SPI_baud_mode[0] == 1:
                    SPI_baudrate = 100000
                
                state = 6
            if (buttonFlags & KEYCODE_UP) != 0:
                buttonFlags &= ~(KEYCODE_UP)
                menuChangeOption(SPI_baud_menuText, SPI_baud_mode,\
                                 SPI_baud_numOptions, incrementMode=False)
            if (buttonFlags & KEYCODE_DOWN) != 0:
                buttonFlags &= ~(KEYCODE_DOWN)
                menuChangeOption(SPI_baud_menuText, SPI_baud_mode,\
                                 SPI_baud_numOptions, incrementMode=True)
    elif state == 6:
        # SPI data bits
        if stateUpdated:
            stateUpdated = False
            newMenuSetup(SPI_dataBits_menuText, SPI_dataBits_mode)
        else:
            if (buttonFlags & KEYCODE_LEFT) != 0:
                buttonFlags &= ~(KEYCODE_LEFT)
                stateUpdated = True
                state = 5
            if (buttonFlags & KEYCODE_RIGHT) != 0:
                buttonFlags &= ~(KEYCODE_RIGHT)
                stateUpdated = True
                if SPI_dataBits_mode[0] == 0:
                    SPI_dataBits = 8
                
                state = 7
            if (buttonFlags & KEYCODE_UP) != 0:
                buttonFlags &= ~(KEYCODE_UP)
                menuChangeOption(SPI_dataBits_menuText, SPI_dataBits_mode,\
                                 SPI_dataBits_numOptions, incrementMode=False)
            if (buttonFlags & KEYCODE_DOWN) != 0:
                buttonFlags &= ~(KEYCODE_DOWN)
                menuChangeOption(SPI_dataBits_menuText, SPI_dataBits_mode,\
                                 SPI_dataBits_numOptions, incrementMode=True)
    elif state == 7:
        # SPI polarity
        if stateUpdated:
            stateUpdated = False
            newMenuSetup(SPI_polarity_menuText, SPI_polarity_mode)
        else:
            if (buttonFlags & KEYCODE_LEFT) != 0:
                buttonFlags &= ~(KEYCODE_LEFT)
                stateUpdated = True
                state = 6
            if (buttonFlags & KEYCODE_RIGHT) != 0:
                buttonFlags &= ~(KEYCODE_RIGHT)
                stateUpdated = True
                if SPI_polarity_mode[0] == 0:
                    SPI_polarity = 0
                elif SPI_polarity_mode[0] == 1:
                    SPI_polarity = 1
                
                state = 8
            if (buttonFlags & KEYCODE_UP) != 0:
                buttonFlags &= ~(KEYCODE_UP)
                menuChangeOption(SPI_polarity_menuText, SPI_polarity_mode,\
                                 SPI_polarity_numOptions, incrementMode=False)
            if (buttonFlags & KEYCODE_DOWN) != 0:
                buttonFlags &= ~(KEYCODE_DOWN)
                menuChangeOption(SPI_polarity_menuText, SPI_polarity_mode,\
                                 SPI_polarity_numOptions, incrementMode=True)
    elif state == 8:
        # SPI phase
        if stateUpdated:
            stateUpdated = False
            newMenuSetup(SPI_phase_menuText, SPI_phase_mode)
        else:
            if (buttonFlags & KEYCODE_LEFT) != 0:
                buttonFlags &= ~(KEYCODE_LEFT)
                stateUpdated = True
                state = 7
            if (buttonFlags & KEYCODE_RIGHT) != 0:
                buttonFlags &= ~(KEYCODE_RIGHT)
                stateUpdated = True
                if SPI_phase_mode[0] == 0:
                    SPI_phase = 0
                elif SPI_phase_mode[0] == 1:
                    SPI_phase = 1
                
                forceTopRowUpdate = True
                forceBottomRowUpdate = True
                protocolConfigDone = True
                state = 9
            if (buttonFlags & KEYCODE_UP) != 0:
                buttonFlags &= ~(KEYCODE_UP)
                menuChangeOption(SPI_phase_menuText, SPI_phase_mode,\
                                 SPI_phase_numOptions, incrementMode=False)
            if (buttonFlags & KEYCODE_DOWN) != 0:
                buttonFlags &= ~(KEYCODE_DOWN)
                menuChangeOption(SPI_phase_menuText, SPI_phase_mode,\
                                 SPI_phase_numOptions, incrementMode=True)
    elif state == 9:
        if (buttonFlags & KEYCODE_MP2) != 0:
            buttonFlags &= ~(KEYCODE_MP2)
            stateUpdated = True
            state = 0
            doAnotherCheck = True
            return
        
        if protocolConfigDone:
            protocolConfigDone = False
            initTXRX_device()
        
        stateTick_TXRX()



# ----- MAIN LOOP ----- #

def main():
    global lastbuttonFlags, lastKeypadScan, buttonFlags, doAnotherCheck
    global displayUpdated, discoMode, lastDiscoUpdate
    
    # Startup configuration
    setup()
    
    # Display splash text
    updateLCD("Project", "OmniComm")
    sleep(5)
    
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
            
            # Disco mode check
            if (buttonFlags & KEYCODE_MP1) != 0:
                buttonFlags &= ~(KEYCODE_MP1)
                discoMode ^= 1
            
            stateTick()
            
            if doAnotherCheck:
                doAnotherCheck = False
                stateTick()
            
            # Update display if necessary
            if displayUpdated:
                displayUpdated = False
                updateLCD(topRow, bottomRow)
        
        # Asynchronous delay for disco mode
        now = ticks_ms()
        if discoMode and ticks_diff(now, lastDiscoUpdate) >= DISCO_UPDATE_MS_PERIOD:
            lastDiscoUpdate = now
            cycleColorMode()


main()