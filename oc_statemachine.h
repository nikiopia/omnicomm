#ifndef OC_STATEMACHINE_H
#define OC_STATEMACHINE_H

// ===== INCLUDES ===== //
// ===== DEFINES ===== //
#define DISPLAY_COLS        (20)
#define OC_NEW_STATE        (0xFF)

// Mode bits: 7 6 5 4 3 2 1 0
//                        B R
#define OC_MASK_ROW             (0x01)
#define OC_MASK_BLANK           (0x02)

#define OC_TOP_ROW              (0x00)
#define OC_BOTTOM_ROW           (0x01)
#define OC_BLANK_OTHER_ROW      (0x02)

// ===== TYPE DEFINES ===== //
enum OC_StateEnum
{
    OC_IDLE,
    OC_BUFFER_RW,
    OC_PROTOCOL_SELECT,
    OC_TYPING,
    OC_TX_RX,
    OC_SYS_UTIL
};
typedef enum OC_StateEnum OC_StateType;

struct OC_SysStruct
{
    char displayMem[2 * DISPLAY_COLS + 1];
    OC_StateType state;
    unsigned char newStateFlag;
};
typedef struct OC_SysStruct OC_SysType;

// ===== FUNCTION PROTOTYPES ===== //

/* @desc    Initialize the state machine structure
 * @param   OC_SysType*     machine structure
 */
int OC_InitMachine(OC_SysType*);

/* @desc    Describes the connections between states
 * @param   OC_SysType*     machine structure
 * @param   char            retrieved keypress
 */
int OC_StateUpdate(OC_SysType*, char);

/* @desc    Perform the current state's action
 * @param   OC_SysType*     machine structure
 */
int OC_DoStateAction(OC_SysType*);

/* @desc    Take an arbitrary length string and process it down into the
 *          display memory for this state machine
 * @param   OC_SysType*     machine structure
 * @param   char*           string to be processed
 * @param   char            mode byte
 */
void OC_DisplayMemWrite(OC_SysType*, char*, char);

// State update functions
int OC_SU_Idle(OC_SysType*, char);
int OC_SU_BufferRW(OC_SysType*, char);

// State action functions
int OC_SA_Idle(OC_SysType*);
int OC_SA_BufferRW(OC_SysType*);

#endif
