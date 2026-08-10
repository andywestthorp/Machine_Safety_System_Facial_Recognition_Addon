/* This contains all of the code for the Master Key operations

    Writing the passcode
    Reading the passcode
    Checking that a key is a master key

*/
void check_master_key() {

  Serial.println("**********************");
  Serial.println("* Master Key Overide *");
  Serial.println("**********************");
  Serial.println("");
  Serial.println("Checking that the tag / card is a master key");


  /* The method is as follows:

      Display a message to say that as we have problems reaching the server, we are in Master Overide Mode
      so please tap your master key.

  */

  /* Prepare the ksy for authentication */
  /* All keys are set to FFFFFFFFFFFFh at chip delivery from the factory */
  for (byte i = 0; i < 6; i++)
  {
    key.keyByte[i] = 0xFF;
  }

  /* Read data from the same block */
  Serial.print("\n");
  Serial.println("Hold your tag on the scanner");
  Serial.print("\n");


  Serial.print(F("Card UID:"));
  for (byte i = 0; i < rfid.uid.size; i++)
  {
    Serial.print(rfid.uid.uidByte[i] < 0x10 ? " 0" : " ");
    Serial.print(rfid.uid.uidByte[i], HEX);
  }
  Serial.print("\n");
  Serial.println("Reading from Data Block...");
  ReadDataFromBlock(blockNum, readBlockData);
  /* If you want to print the full memory dump, uncomment the next line */
  //rfid.PICC_DumpToSerial(&(rfid.uid));

  /* Print the data read from block */
  Serial.print("\n");
  Serial.print("Data in Block:");
  Serial.print(blockNum);
  Serial.print(" --> ");
  for (int j = 0 ; j < 16 ; j++)
  {
    Serial.write(readBlockData[j]);
  }
  Serial.print("\n");
  Serial.print("\n");
  Serial.println("You can now remove your card");
  Serial.print("\n");

  String PassString = String((char *)readBlockData);

  Serial.println(PassString);

  if (PassString == "DTSafety-Master") {
    Serial.println("Master card");
    display_ppe();
    start_machinery();

  }
  else
  {
    Serial.println("Not a master card");
    display_no_entry();
    delay(2000);
  }

  RFID_Initialised = false;

  Serial.println("Return");
}


void display_card_reading()
{
  // This displays a nice picture and a message to say please leave the card / tag on the scanner!
}

/* The following code was obtained from https://gist.github.com/elktros/4dffa379ca3ef340961e464a1f59e0b2
   The accomanying article at https://www.electronicshub.org/write-data-to-rfid-card-using-rc522-rfid/
   is very useful...
*/


void make_master_key()
{

  /*  Plan of action:

       1. Display a message to say hold your card against the scanner
       2. Wait until they do this or else time runs out
       3. Write the code to the card
       4. Read the code back
       5. Verify that it is correct.


  */

  tft.fillScreen(RED);
  tft.setTextColor(WHITE);
  tft.setCursor(8, 12);
  tft.println("Making Master Key");
  tft.setCursor(10, 34);
  tft.println("Please, keep your");
  tft.setCursor(10, 48);
  tft.println("key on the scanner");

  tft.drawBitmap(40, 49, Scan, 120, 82, 0xffff);

  bleep(2000, 100);

  delay(3000);

  /* Prepare the ksy for authentication */
  /* All keys are set to FFFFFFFFFFFFh at chip delivery from the factory */
  for (byte i = 0; i < 6; i++)
  {
    key.keyByte[i] = 0xFF;
  }

  Serial.print("\n");
  Serial.println("**Card Detected**");
  /* Print UID of the Card */
  Serial.print(F("Card UID:"));
  for (byte i = 0; i < rfid.uid.size; i++)
  {
    Serial.print(rfid.uid.uidByte[i] < 0x10 ? " 0" : " ");
    Serial.print(rfid.uid.uidByte[i], HEX);
  }
  Serial.print("\n");
  /* Print type of card (for example, MIFARE 1K) */
  Serial.print(F("PICC type: "));
  MFRC522::PICC_Type piccType = rfid.PICC_GetType(rfid.uid.sak);
  Serial.println(rfid.PICC_GetTypeName(piccType));

  /* Call 'WriteDataToBlock' function, which will write data to the block */
  Serial.print("\n");
  Serial.println("Writing to Data Block...");
  WriteDataToBlock(blockNum, blockData);

  /* Read data from the same block */
  Serial.print("\n");
  Serial.println("Reading from Data Block...");
  ReadDataFromBlock(blockNum, readBlockData);
  /* If you want to print the full memory dump, uncomment the next line */
  //mfrc522.PICC_DumpToSerial(&(mfrc522.uid));

  /* Print the data read from block */
  Serial.print("\n");
  Serial.print("Data in Block:");
  Serial.print(blockNum);
  Serial.print(" --> ");
  for (int j = 0 ; j < 16 ; j++)
  {
    Serial.write(readBlockData[j]);
  }


  // Verify that the card has been coded correctly

  String PassString = String((char *)readBlockData);

  Serial.println(PassString);

  if (PassString == "DTSafety-Master") {
    Serial.print("Card is now a Master key! \n");
    tft.fillScreen(RED);
    tft.setTextColor(WHITE);
    tft.setCursor(10, 16);
    tft.println("Master Key Made");
    tft.setCursor(10, 32);
    tft.println("Thank you!");
    tft.setCursor(10, 46);
    tft.println("");

    tft.drawBitmap(40, 49, Scan, 120, 82, 0xffff);

    delay(3000);
    bleep(2000, 100);
   // Replace line 232 (and its immediate call) with:
bool success = server_acknowledged("MasterKeyCreated", User_Key_Value);
Serial.print("Server Acknowledge Status: ");
Serial.println(success ? "SUCCESS" : "FAILED");


  }
  else
  {
    Serial.print("Something went wrong, please try again. \n");

  }
}





void WriteDataToBlock(int blockNum, byte blockData[])
{
  /* Authenticating the desired data block for write access using Key A */
  status = rfid.PCD_Authenticate(MFRC522::PICC_CMD_MF_AUTH_KEY_A, blockNum, &key, &(rfid.uid));
  if (status != MFRC522::STATUS_OK)
  {
    Serial.print("Authentication failed for Write: ");
    Serial.println(rfid.GetStatusCodeName(status));
    return;
  }
  else
  {
    Serial.println("Authentication success");
  }


  /* Write data to the block */
  status = rfid.MIFARE_Write(blockNum, blockData, 16);
  if (status != MFRC522::STATUS_OK)
  {
    Serial.print("Writing to Block failed: ");
    Serial.println(rfid.GetStatusCodeName(status));
    return;
  }
  else
  {
    Serial.println("Data was written into Block successfully");
  }

}

void ReadDataFromBlock(int blockNum, byte readBlockData[])
{
  /* Authenticating the desired data block for Read access using Key A */
  byte status = rfid.PCD_Authenticate(MFRC522::PICC_CMD_MF_AUTH_KEY_A, blockNum, &key, &(rfid.uid));

  if (status != MFRC522::STATUS_OK)
  {
    Serial.print("Authentication failed for Read: ");
    Serial.println(rfid.GetStatusCodeName((MFRC522::StatusCode)status));
    return;
  }
  else
  {
    Serial.println("Authentication success");
  }

  /* Reading data from the Block */
  status = rfid.MIFARE_Read(blockNum, readBlockData, &bufferLen);
  if (status != MFRC522::STATUS_OK)
  {
    Serial.print("Reading failed: ");
    Serial.println(rfid.GetStatusCodeName((MFRC522::StatusCode)status));
    return;
  }
  else
  {
    Serial.println("Block was read successfully");
  }

}

void display_scan_Master_Key()
{

  tft.fillScreen(RED);
  tft.setTextColor(WHITE);
  tft.setCursor(10, 16);
  tft.println("Please, hold your");
  tft.setCursor(10, 32);
  tft.println("master key against");
  tft.setCursor(10, 46);
  tft.println("the scanner");

  tft.drawBitmap(40, 49, Scan, 120, 82, 0xffff);

  bleep(2000, 100);

}
