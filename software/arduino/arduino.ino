static const uint8_t ADDRESS_PINS[] = {26, 46, 47, 44, 39, 38, 41, 40, 43, 33, 34, 35, 36, 37, 30, 29, 28, 27, 42};  // A-1 (Bit 0) - A17 (Bit 18) (A-1 is the LSB in byte mode)
static const uint8_t DATA_PINS[] = {51, 50, 53, 52, 22, 23, 24, 25};                                                 // DQ0 - DQ7 (only 8 bits are used in byte mode)
static const uint8_t RESET_PIN = 31;
static const uint8_t WE_PIN = 32;
static const uint8_t OE_PIN = 48;
static const uint8_t CE_PIN = 49;
static const uint8_t RY_BY_PIN = 45;

bool is_busy() {
  return digitalRead(RY_BY_PIN) == LOW;
}

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
  delayMicroseconds(10);
  digitalWrite(WE_PIN, HIGH);
}

uint8_t read_byte(uint32_t address) {
  digitalWrite(OE_PIN, HIGH);
  set_address(address);
  delayMicroseconds(10);
  digitalWrite(OE_PIN, LOW);
  delayMicroseconds(50);

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
  delayMicroseconds(10);
  set_data_in();
  uint8_t manufacturer_id = read_byte(0x0);

  reset_chip();

  // Read device id
  set_data_out();
  write_byte(0xaa, 0xaaa);
  write_byte(0x55, 0x555);
  write_byte(0x90, 0xaaa);
  delayMicroseconds(10);
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
  delayMicroseconds(10);
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

void erase_sector(uint32_t address) {
  set_data_out();
  write_byte(0xaa, 0xaaa);
  write_byte(0x55, 0x555);
  write_byte(0x80, 0xaaa);
  write_byte(0xaa, 0xaaa);
  write_byte(0x55, 0x555);
  write_byte(0x30, address);
  delayMicroseconds(1);

  while (is_busy()) {
    delayMicroseconds(1);
  }

  Serial.write(0x03);  // Message Type
  Serial.write(0x00);  // Message Length
}

void write_data(uint32_t address, uint8_t size, uint8_t data[]) {
  set_data_out();

  for (uint8_t i = 0; i < size; i++) {
    write_byte(0xaa, 0xaaa);
    write_byte(0x55, 0x555);
    write_byte(0xa0, 0xaaa);
    write_byte(data[i], address + i);
    delayMicroseconds(100);

    while (is_busy()) {
      delayMicroseconds(1);
    }
  }

  Serial.write(0x04);  // Message Type
  Serial.write(0x00);  // Message Length
}

void check_sector_protection(uint32_t address) {
  set_data_out();
  write_byte(0xaa, 0xaaa);
  write_byte(0x55, 0x555);
  write_byte(0x90, 0xaaa);
  delayMicroseconds(10);

  set_data_in();
  uint8_t result = read_byte(0x4);

  reset_chip();
  delayMicroseconds(10);

  Serial.write(0x05);  // Message Type
  Serial.write(0x01);  // Message Length
  Serial.write(result);
}

void loop() {
  int available = Serial.available();
  if (available > 1) {
    uint8_t pre_buffer[2] = {};
    Serial.readBytes(pre_buffer, 2);
    uint8_t message_type = pre_buffer[0];
    uint8_t message_length = pre_buffer[1];

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
      pinMode(RY_BY_PIN, INPUT);

      digitalWrite(RESET_PIN, HIGH);
      digitalWrite(WE_PIN, HIGH);
      digitalWrite(OE_PIN, LOW);
      digitalWrite(CE_PIN, LOW);

      reset_chip();

      Serial.write(0x00);  // Message Type
      Serial.write(0x00);  // Message Length

    } else if (message_type == 0x01) {  // Ident
      read_ident();

    } else if (message_type == 0x02) {  // Read Data
      uint32_t address = ((uint32_t)(uint8_t)buffer[0] << 24) | ((uint32_t)(uint8_t)buffer[1] << 16) | ((uint32_t)(uint8_t)buffer[2] << 8) | ((uint32_t)(uint8_t)buffer[3]);
      uint8_t size = buffer[4];
      read_data(address, size);

    } else if (message_type == 0x03) {  // Erase Sector
      uint32_t address = ((uint32_t)(uint8_t)buffer[0] << 24) | ((uint32_t)(uint8_t)buffer[1] << 16) | ((uint32_t)(uint8_t)buffer[2] << 8) | ((uint32_t)(uint8_t)buffer[3]); 
      erase_sector(address);

    } else if (message_type == 0x04) {  // Write Data
      uint32_t address = ((uint32_t)(uint8_t)buffer[0] << 24) | ((uint32_t)(uint8_t)buffer[1] << 16) | ((uint32_t)(uint8_t)buffer[2] << 8) | ((uint32_t)(uint8_t)buffer[3]); 
      uint8_t size = buffer[4];
      uint8_t data[size] = {};
      memcpy(data, &buffer[5], sizeof(data));
      write_data(address, size, data);

    } else if (message_type == 0x05) {
      uint32_t address = ((uint32_t)(uint8_t)buffer[0] << 24) | ((uint32_t)(uint8_t)buffer[1] << 16) | ((uint32_t)(uint8_t)buffer[2] << 8) | ((uint32_t)(uint8_t)buffer[3]); 
      check_sector_protection(address);

    }
  }
}