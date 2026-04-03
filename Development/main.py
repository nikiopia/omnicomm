# ----- IMPORTS ----- #

from machine import I2C, SPI, UART, Pin
from time import sleep, sleep_ms, ticks_ms, ticks_diff

# ----- CONTROL "DEFINES" ----- #

CIRCULAR_BUFFER_SIZE = 3
KEYPAD_SCAN_MS_PERIOD = 20

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

lastbuttonFlags = 0xFFFFFFFF
lastKeypadScan = 0

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
    rawSwitchStates[writeIndex] = scanCode
    
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
    
    global rawSwitchStates, writeIndex, debouncedStates, buttonFlags
    
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
    
    # Debouncing Setup
    writeIndex = 0
    debouncedStates = 0
    buttonFlags = 0
    rawSwitchStates = []
    for i in range(CIRCULAR_BUFFER_SIZE):
        rawSwitchStates.append(0)



# ----- MAIN LOOP ----- #

def main():
    global lastbuttonFlags, lastKeypadScan
    
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
            if (buttonFlags ^ lastbuttonFlags) != 0:
                updateLCD("buttonFlags:", "0x{0:08X}".format(buttonFlags))
            
            lastbuttonFlags = buttonFlags
        
        # State machine -- TODO


main()