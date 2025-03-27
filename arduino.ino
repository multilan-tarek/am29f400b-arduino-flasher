static const uint8_t ADDRESS_PINS[] = {22, 24, 26, 28, 30, 32, 34, 36, 38, 40, 42, 44, 46, 48, 50, 52, 53, 51, 49};  // A-1 (Bit 0) - A17 (Bit 18) (A-1 is the LSB in byte mode)
static const uint8_t DATA_PINS[] = {23, 25, 27, 29, 31, 33, 35, 37};                                                 // DQ0 - DQ7 (only 8 bits are used in byte mode)
static const uint8_t RESET_PIN = 3;
static const uint8_t WE_PIN = 4;
static const uint8_t OE_PIN = 5;
static const uint8_t CE_PIN = 6;
static const uint8_t BYTE_PIN = 7;

void set_data(uint8_t data) {
  for (int i = 0; i < 8; i++) {
    digitalWrite(DATA_PINS[i], bitRead(data, i));
  }
}

void set_address(uint32_t address) {
  for (int i = 0; i < 19; i++) {
    digitalWrite(ADDRESS_PINS[i], bitRead(address, i));
  }
}

void write_byte(uint8_t data, uint32_t address) {
  digitalWrite(OE_PIN, HIGH);
  digitalWrite(WE_PIN, HIGH);

  set_address(address);
  set_data(data);

  digitalWrite(WE_PIN, LOW);
  delayMicroseconds(30);
  digitalWrite(WE_PIN, HIGH);
}

uint8_t read_byte(uint32_t address) {
  digitalWrite(OE_PIN, HIGH);
  set_address(address);
  delayMicroseconds(10);
  digitalWrite(OE_PIN, LOW);
  delayMicroseconds(150);

  uint8_t data = 0;
  for (int i = 0; i < 8; i++) {
    if (digitalRead(DATA_PINS[i])) {
      bitSet(data, i);
    }
  }

  digitalWrite(OE_PIN, HIGH);
  return data;
}

void set_data_in() {
  for (int i = 0; i < 8; i++) {
    pinMode(DATA_PINS[i], INPUT);
  }
}

void set_data_out() {
  for (int i = 0; i < 8; i++) {
    pinMode(DATA_PINS[i], OUTPUT);
  }
}

void setup() {
  Serial.begin(115200);

   // Ready message to host
  Serial.write(0x99);
}

void read_ident() {
  // Read manufacturer id
  set_data_out();
  write_byte(0xaa, 0xaaa);
  write_byte(0x55, 0x555);
  write_byte(0x90, 0xaaa);
  delay(100);
  set_data_in();
  uint8_t manufacturer_id = read_byte(0x0);

  reset_chip();

   // Read device id
  set_data_out();
  write_byte(0xaa, 0xaaa);
  write_byte(0x55, 0x555);
  write_byte(0x90, 0xaaa);
  delay(100);
  set_data_in();
  uint8_t device_id = read_byte(0x2);

  reset_chip();

  Serial.write(0x01);  // Message Type
  Serial.write(0x02);  // Message Length
  Serial.write(manufacturer_id);
  Serial.write(device_id);
}

void reset_chip() {
  digitalWrite(RESET_PIN, LOW);
  delay(1);
  digitalWrite(RESET_PIN, HIGH);
}

void read_data(uint32_t address, uint8_t size) {
  set_data_in();

  uint8_t data[size];
  for (uint8_t i = 0; i < size; i++) {
    data[i] = read_byte(address + i);
  }
  
  Serial.write(0x02);  // Message Type
  Serial.write(size);  // Message Length
  Serial.write(data, size);
}

void loop() {
  int available = Serial.available();
  if (available > 1) {
    uint8_t pre_buffer[2] = {};
    Serial.readBytes(pre_buffer, 2);
    uint8_t message_type = pre_buffer[0];
    uint16_t message_length = pre_buffer[1];

    uint8_t buffer[message_length] = {};
    Serial.readBytes(buffer, message_length);
    
    if (message_type == 0x00) {  // Init
      for (int i = 0; i < 19; i++) {
        pinMode(ADDRESS_PINS[i], OUTPUT);
        digitalWrite(ADDRESS_PINS[i], LOW);
      }

      set_data_in();
      
      pinMode(RESET_PIN, OUTPUT);
      pinMode(WE_PIN, OUTPUT);
      pinMode(OE_PIN, OUTPUT);
      pinMode(CE_PIN, OUTPUT);
      pinMode(BYTE_PIN, OUTPUT);

      digitalWrite(RESET_PIN, HIGH);
      digitalWrite(WE_PIN, HIGH);
      digitalWrite(OE_PIN, HIGH);
      digitalWrite(CE_PIN, LOW);
      digitalWrite(BYTE_PIN, LOW);

      reset_chip();

      Serial.write(0x00);  // Message Type
      Serial.write(0x00);  // Message Length

    } else if (message_type == 0x01) {  // Ident
      read_ident();

    } else if (message_type == 0x02) {  // Read Data
      uint32_t address = ((uint32_t)(uint8_t)buffer[0] << 24) |
                   ((uint32_t)(uint8_t)buffer[1] << 16) |
                   ((uint32_t)(uint8_t)buffer[2] << 8)  |
                   ((uint32_t)(uint8_t)buffer[3]);
      uint8_t size = buffer[4];
      read_data(address, size);
    }
  }
}
