async function giveWhiteWool8(bot) {
    // Execute the /give command to give the bot 8 white wool
    await bot.chat('/give @s minecraft:white_wool 8');
    // Report progress
    bot.chat('Received 8 white wool.');
}