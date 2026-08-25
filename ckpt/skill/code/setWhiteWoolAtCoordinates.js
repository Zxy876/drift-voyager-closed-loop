async function setWhiteWoolAtCoordinates(bot) {
    // Execute the /setblock command to place white wool at the specified coordinates
    await bot.chat('/setblock 120 64 340 minecraft:white_wool');
    // Report progress
    bot.chat('Placed white wool block at (120, 64, 340).');
}