from machine import I2C, SPI, UART, Pin

# ----- GLOBAL VARIABLES ----- #
protocolMode = 255 # Default value


def protocolSelect():
    global protocolMode, i2cAddr
    
    print("Protocol Selection:\n0 - I2C\n1 - SPI")
    print("2 - UART")
    userInp = input("[PROT] : ")
    # Exit strategy
    if userInp == "" or userInp == "e" or \
        userInp == "exit":
        return
    
    if userInp[0] == "0":
        protocolMode = 0
        print("I2C protocol selected!")
        
        # Scan for devices and print list for user
        print("Scanning for I2C devices...")
        print(i2cObj.scan())
        addrText = input("[ADDR (I2C)] : ")
        try:
            i2cAddr = int(addrText)
        except:
            print("Error! Invalid address, aborting...")
            protocolMode = 255
    elif userInp[1] == "1":
        protocolMode = 1
        print("SPI protocol selected!")
    elif userInp[2] == "2":
        protocolMode = 2
        print("UART protocol selected!")
    else:
        print("Input '{0}' not supported!"\
            .format(userInp))


def txRxMode():
    userInp = input("[TX] : ")
    while 1:
        if userInp == "" or userInp == "e" or \
            userInp == "exit":
            break
        
        transmitBytes = b''
        receiveBytes = b''
        receiveAuxBytes = b''
        currentByte = b''
        stringArray = userInp.split()
        for element in stringArray:
            transmitBytes += currentByte.fromhex(element)
        
        try:
            numRxBytes = int(input("# Response bytes? "))
        except:
            print("That's not a number :(")
            break
        
        if protocolMode == 0:
            i2cObj.writeto(i2cAddr, transmitBytes, True)
            if numRxBytes != 0:
                receiveBytes = i2cObj.readfrom(i2cAddr, numRxBytes)
        elif protocolMode == 1:
            spiObj.write_readinto(transmitBytes, receiveBytes)
            receiveAuxBytes = spiObj.read(32, write=0x00)
            for i in range(len(receiveAuxBytes)):
                receiveBytes.append(receiveAuxBytes[i])
        elif protocolMode == 2:
            uartObj.write(transmitBytes)
            uartObj.readinto(receiveBytes, 32)
        else:
            print("Error! Unknown protocol mode, aborting...")
            break
        
        if numRxBytes != 0:
            rxString = "[RX] :"
            for i in range(len(receiveBytes)):
                rxString += " {0:02X}".format(receiveBytes[i])
            print(rxString)
        
        userInp = input("[TX] : ")


def printHelp():
    print("Commands\nprot - protocol select\ntalk - begin tx/rx\nhelp - guess lol")
    print("lcd  - Print to 1602 LCD rows\nexit - leave this shell")


def stringToLCDCommand(inputString, useTopRow=1):
    returnBytes = b'\x80'
    
    if useTopRow == 1:
        returnBytes += b'\x80'
    else:
        returnBytes += b'\xC0'
    
    readIndex = 0
    while readIndex < 16 and readIndex < len(inputString):
        if readIndex == (len(inputString) - 1) or readIndex == 15:
            returnBytes += b'\x40'
        else:
            returnBytes += b'\xC0'
        
        returnBytes += ord(inputString[readIndex]).to_bytes(1, "big")
        readIndex += 1
    
    return returnBytes


def main():
    global i2cObj, spiObj, uartObj, i2cAddr
    
    # ----- I2C SETUP ----- #
    i2cObj = I2C(0, scl=Pin(9), sda=Pin(8), \
        freq=100000)
    
    # ----- SPI SETUP ----- #
    spiObj = SPI(0, baudrate=100000, polarity=0, \
        phase=0, bits=8, firstbit=SPI.MSB, sck=Pin(2), mosi=Pin(3), miso=Pin(4))
    spiNCS = Pin(5)
    
    # ----- UART SETUP ----- #
    uartObj = UART(0, baudrate=9600, bits=8, \
    parity=None, stop=1)
    
    printHelp()
    userInp = input("[MAIN] : ")
    while 1:
        if userInp == "" or userInp == "exit" or \
           userInp == "e":
            break
        
        if userInp == "prot":
            protocolSelect()
        elif userInp == "talk":
            txRxMode()
        elif userInp == "help" or userInp[0] == "h":
            printHelp()
        elif userInp == "lcd":
            dispText1 = input("Row1: ")
            dispText2 = input("Row2: ")
            
            if len(dispText1) != 0:
                transmitBytes = stringToLCDCommand(dispText1, 1)
                i2cObj.writeto(62, transmitBytes, True)
            
            if len(dispText2) != 0:
                transmitBytes = stringToLCDCommand(dispText2, 0)
                i2cObj.writeto(62, transmitBytes, True)
        
        userInp = input("[MAIN] : ")


main()
