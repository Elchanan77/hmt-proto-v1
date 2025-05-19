#include "Wire.h"          // Required for I2C communication (used by MPU6050)
#include "I2Cdev.h"        // I2Cdev library simplifies communication with I2C devices
#include "MPU6050.h"       // Library for MPU6050 functions (accelerometer + gyroscope)
#include <SoftwareSerial.h> // Allows serial communication on digital pins (for Bluetooth)

// -------------------- Serial & Bluetooth --------------------
SoftwareSerial btSerial(10, 11);  // Create a software serial port on pins 10 (RX) and 11 (TX)

// -------------------- Sensor --------------------
MPU6050 mpu;  // Create an MPU6050 object to interface with the IMU sensor

// -------------------- Raw Sensor Data --------------------
int16_t ax, ay, az;       // Raw accelerometer values (X, Y, Z)
float axg, ayg, azg;      // Converted accelerometer values in G-units

// -------------------- Setup --------------------
void setup() {
  Serial.begin(115200);     // Start hardware serial communication (for PC) at 115200 baud
  btSerial.begin(115200);   // Start Bluetooth serial communication at 115200 baud
  Wire.begin();             // Initialize I2C bus

  mpu.initialize();         // Initialize MPU6050 sensor (configure I2C, power, ranges, etc.)

  // Check connection with the MPU6050
  if (!mpu.testConnection()) {
    logAll("MPU6050 connection failed!");  // If sensor not detected, print error message
    while (1);  // Halt program if sensor connection fails
  }

  sendInstructions();  // Display initial instruction prompt
}

// -------------------- Main Loop --------------------
void loop() {
  char cmd = 0;  // Variable to hold incoming command character

  // Check if command received via USB serial
  if (Serial.available()) {
    cmd = tolower(Serial.read());  // Read and convert character to lowercase
  }
  // If not from USB, check Bluetooth serial
  else if (btSerial.available()) {
    cmd = tolower(btSerial.read());  // Read and convert character to lowercase
  }

  // Skip processing if no valid character (e.g., newline, carriage return, null)
  if (cmd == '\n' || cmd == '\r' || cmd == 0) return;

  // If user requests recalibration ('r')
  if (cmd == 'r') {
    logAll("Recalibrating...");
    preMove();     // Capture stationary orientation before movement
    postMove();    // Capture stationary orientation after movement
    logAll("Recalibrated.");
    sendInstructions();  // Display instruction prompt again
  } 
  else {
    captureAndClassify(cmd);  // Handle motion classification based on command
  }
}

// -------------------- Movement Handler --------------------
void captureAndClassify(char movement) {
  String msg;

  if (movement == 's' || movement == 'p') {
    preMove();  // Take initial accelerometer reading and average it into axg, ayg, azg

    // Calculate initial roll angle
    float ThumbUp = atan2(ayg, azg) * 180.0 / PI;
    if (ThumbUp < 0) ThumbUp += 360.0;  // Convert angle to 0–360° for consistency

    logAll("Rotate now...");
    for (int i = 5; i >= 1; i--) {
      logAll(String(i) + "...");
      delay(1000);  // Countdown for user to perform supination/pronation
    }

    postMove();  // Take new accelerometer reading

    // Calculate roll angle after movement
    float rollAfter = atan2(ayg, azg) * 180.0 / PI;
    if (rollAfter < 0) rollAfter += 360.0;

    // Calculate relative change in roll
    float rollChange = rollAfter - ThumbUp;

    //  Normalize angle difference to range [-180°, +180°] to correctly handle wrap-around
    if (rollChange > 180) rollChange -= 360;
    if (rollChange < -180) rollChange += 360;

    // 💡 Report the absolute value of rotation, i.e., magnitude of supination/pronation
    msg = "ANGLE:" + String(abs(rollChange), 2);
    logAll(msg);
    return;
  }


  else if (movement == 'z') {
    float yaw = 0.0;  // Initialize cumulative yaw angle (rotation around Z-axis)

    // Timekeeping variables
    unsigned long lastUpdateTime = micros();    // Time of the last loop iteration (microseconds)
    unsigned long startMillis = millis();       // Start time of the measurement loop (milliseconds)
    unsigned long currentMillis = startMillis;  // Current time tracker (milliseconds)
    unsigned long duration = 5000;              // Total duration of measurement: 5000 ms = 5 seconds
    int secondsLeft = 5;                        // Countdown for user feedback

    logAll("Start moving now!");  // Prompt user to begin motion

    // Loop for a fixed duration to accumulate yaw based on gyroscope data
    while (currentMillis - startMillis < duration) {
      int16_t gx, gy, gz;

      // Read accelerometer and gyroscope data (gx, gy, gz are raw angular velocity values)
      mpu.getMotion6(&ax, &ay, &az, &gx, &gy, &gz);

      // Calculate elapsed time since last reading in seconds
      unsigned long now = micros();                   // Get current time in microseconds
      float dt = (now - lastUpdateTime) / 1000000.0;  // Convert microsecond difference to seconds
      lastUpdateTime = now;                           // Update timestamp for next iteration

      // Convert raw gyroscope Z-axis data to degrees per second (scale factor for ±250°/s is 131.0)
      float gyroZ = gz / 131.0;

      // Integrate angular velocity over time to get estimated yaw angle
      yaw += gyroZ * dt;

      // Normalize yaw angle to stay within [-180°, +180°] to handle wrap-around
      if (yaw > 180) yaw -= 360;
      if (yaw < -180) yaw += 360;

      // Display countdown every second for user feedback
      if ((currentMillis - startMillis) >= (5000 - (secondsLeft * 1000))) {
        logAll(String(secondsLeft) + "...");
        secondsLeft--;
      }

      delay(10);                 // Wait 10 ms before next sample (approx. 100 Hz sampling rate)
      currentMillis = millis();  // Update current time (ms) for loop condition and countdown
    }

    // Sampling complete – report final accumulated yaw angle
    logAll("Hold... Sampling now!");
    logAll("ANGLE:" + String(abs(yaw), 2));  // Report absolute value of estimated rotation
    return;
  }



  else if (movement == 'f' || movement == 'x' || movement == 'e' || movement == 'y') {
    preMove();  // Capture and average initial accelerometer readings (axg, ayg, azg)

    logAll("Move now...");  // Prompt user to perform the motion (e.g., flexion or extension)

    // Countdown loop (5 seconds) to give the user time to complete the movement
    for (int i = 5; i >= 1; i--) {
      logAll(String(i) + "...");
      delay(1000);  // 1-second delay between countdown messages
    }

    postMove();  // Capture and average new accelerometer readings after movement

    // Calculate pitch angle using X and Z-axis acceleration
    // Formula estimates tilt around the lateral axis (Y-axis of the device)
    float pitch = atan2(axg, azg) * 180.0 / PI;

    // Take the absolute value to report the magnitude of tilt (ignores direction)
    float PitchAngle = abs(pitch);

    // Report final calculated angle
    logAll("ANGLE:" + String(PitchAngle, 2));
  } 
  else {
    logAll("Invalid command.");  // Catch-all for unknown input commands
  }
}



  // -------------------- Move Calibration Helpers --------------------
  // -------------------- Pre-Movement Sampling --------------------
  void preMove() {
    logAll("Get into position...");  // Prompt user to prepare for sampling
    delay(500);                      // Small delay to allow user to settle into position
    logAll("Ready.");                // Indicate start of sampling

    const int samples = 50;              // Number of samples to average for smoothing
    float sumX = 0, sumY = 0, sumZ = 0;  // Accumulators for accelerometer data

    // Collect 50 samples over 500 ms (10 ms delay per sample)
    for (int i = 0; i < samples; i++) {
      mpu.getAcceleration(&ax, &ay, &az);  // Read raw accelerometer data (X, Y, Z axes)
      sumX += ax;                          // Accumulate X-axis readings
      sumY += ay;                          // Accumulate Y-axis readings
      sumZ += az;                          // Accumulate Z-axis readings
      delay(10);                           // Delay between samples → 100 Hz sampling rate
    }

    // Convert averaged raw values to G-units by dividing by sensitivity factor (16384 for ±2g)
    axg = (sumX / samples) / 16384.0;
    ayg = (sumY / samples) / 16384.0;
    azg = (sumZ / samples) / 16384.0;
  }

  // -------------------- Post-Movement Sampling --------------------
  void postMove() {
    logAll("Hold... Sampling position!");  // Prompt user to hold still for post-movement capture

    const int samples = 50;  // Same sample count as preMove for consistency
    float sumX = 0, sumY = 0, sumZ = 0;

    // Collect 50 samples to average out noise after movement
    for (int i = 0; i < samples; i++) {
      mpu.getAcceleration(&ax, &ay, &az);  // Read raw accelerometer data
      sumX += ax;
      sumY += ay;
      sumZ += az;
      delay(10);  // 10 ms delay → maintains 100 Hz sampling rate
    }

    // Convert raw averaged values to G-units using sensitivity scale (±2g → 16384 LSB/g)
    axg = (sumX / samples) / 16384.0;
    ayg = (sumY / samples) / 16384.0;
    azg = (sumZ / samples) / 16384.0;
  }

  // -------------------- Unified Output Logger --------------------
  void logAll(String msg) {
    // Send message to both Serial Monitor and Bluetooth serial
    Serial.println(msg);
    btSerial.println(msg);
  }

  // -------------------- Instruction Prompt --------------------
  void sendInstructions() {
    // Displays instruction message to user via both serial channels
    logAll("Select Movement");
  }
