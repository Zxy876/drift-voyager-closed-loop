async function giveWhiteConcrete(bot) {
    // Execute the /give command to give the bot 16 white concrete
    await bot.chat('/give @s minecraft:white_concrete 16');
    // Report progress
    bot.chat('Received 16 white concrete.');
}