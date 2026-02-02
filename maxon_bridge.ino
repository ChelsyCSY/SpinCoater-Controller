/* * Spin Coater Bridge (Python -> Maxon EPOS4)
 * * Hardware Connections:
 * - Arduino GND -> Maxon GND
 * - Arduino Pin 9 -> Maxon Analog Input 1+ (Speed)
 * - Arduino Pin 7 -> Maxon Digital Input 1 (Enable)
 * * Maxon Configuration (EPOS Studio):
 * - Mode: Analog Velocity Mode
 * - Scaling: 0V = 0 RPM, 5V = 10,000 RPM (Adjust MAX_RPM below to match)
 */

String inputString = "";
boolean stringComplete = false;

// --- CONFIGURATION ---
const int ENABLE_PIN = 7;   // To Maxon Enable
const int PWM_PIN = 9;      // To Maxon Analog In
const int MAX_RPM = 10000;  // Max RPM when output is 5V (255 PWM)

void setup() {
  Serial.begin(9600);
  pinMode(ENABLE_PIN, OUTPUT);
  pinMode(PWM_PIN, OUTPUT);

  // Safe Start: Disable Motor
  digitalWrite(ENABLE_PIN, LOW);
  analogWrite(PWM_PIN, 0);
}

void loop() {
  if (stringComplete) {
    processCommand(inputString);
    inputString = "";
    stringComplete = false;
  }
}

void processCommand(String cmd) {
  // Expected: "SPEED:3000"

  if (cmd.startsWith("SPEED")) {
    int colonIndex = cmd.indexOf(':');
    String valStr = cmd.substring(colonIndex + 1);
    long targetRPM = valStr.toInt();

    // Safety Limits
    if (targetRPM > MAX_RPM) targetRPM = MAX_RPM;
    if (targetRPM < 0) targetRPM = 0;

    // Convert RPM to PWM (0-255 for 8-bit Arduino)
    // Map(value, fromLow, fromHigh, toLow, toHigh)
    int pwmOutput = map(targetRPM, 0, MAX_RPM, 0, 255);

    if (targetRPM > 0) {
      digitalWrite(ENABLE_PIN, HIGH); // Enable Driver
      analogWrite(PWM_PIN, pwmOutput); // Set Speed
    } else {
      digitalWrite(ENABLE_PIN, LOW);  // Disable Driver
      analogWrite(PWM_PIN, 0);
    }
  }
}

// Serial Event Listener
void serialEvent() {
  while (Serial.available()) {
    char inChar = (char)Serial.read();
    inputString += inChar;
    if (inChar == '\n') {
      stringComplete = true;
    }
  }
}