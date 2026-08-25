/**
 * Drift 自定义 Mineflayer 控制原语
 * ---------------------------------
 * 这些函数会被 enable_drift_primitives() 注入到 Voyager 的 action agent 上下文与
 * 执行环境，使 Voyager 能在「医院关卡」里学习并使用它们（对话、召唤 NPC、搭建、给物品）。
 *
 * 注意：Director 的世界补丁（world_patch）为了稳妥，默认直接用 bot.chat('/...') 原生命令，
 * 不依赖下面的 drift* 函数；而下面的 drift* 是给 Voyager 在「任务」中学习和复用的技能。
 */

/**
 * 让 bot 在聊天里说一句话（也用于触发 Drift/NPC 的剧情响应）。
 */
async function driftChat(bot, message) {
    bot.chat(message);
    await bot.waitForTicks(20);
}

/**
 * 按名称寻找附近 NPC（村民 / 带 CustomName 的实体 / ArmorStand）。
 */
async function driftFindNpc(bot, npcName) {
    for (const id in bot.entities) {
        const e = bot.entities[id];
        if (!e) continue;
        const name = (e.displayName || e.username || e.name || "").toString();
        if (name.toLowerCase().includes(npcName.toLowerCase())) return e;
        const meta = e.metadata && e.metadata[2];
        if (meta && meta.toString().toLowerCase().includes(npcName.toLowerCase())) return e;
    }
    return null;
}

/**
 * 走到 NPC 面前并说话（任务级：与医生对话）。
 */
async function driftTalkToNpc(bot, npcName, message, maxDistance = 4) {
    const npc = await driftFindNpc(bot, npcName);
    if (!npc) {
        bot.chat(`I cannot find ${npcName}`);
        throw new Error(`NPC ${npcName} not found`);
    }
    const { GoalNear } = require("mineflayer-pathfinder").goals;
    await bot.pathfinder.goto(new GoalNear(npc.position.x, npc.position.y, npc.position.z, 1));
    await driftChat(bot, message);
    return npc;
}

/**
 * 等待聊天里出现匹配正则的消息（如医生的回复）。
 */
async function driftWaitForChat(bot, pattern, timeoutTicks = 100) {
    const regex = new RegExp(pattern, "i");
    return new Promise((resolve, reject) => {
        let elapsed = 0;
        const handler = (username, message) => {
            if (regex.test(message)) {
                bot.removeListener("message", handler);
                resolve(message);
            }
        };
        bot.on("message", handler);
        const timer = setInterval(() => {
            elapsed += 5;
            if (elapsed >= timeoutTicks) {
                clearInterval(timer);
                bot.removeListener("message", handler);
                reject(new Error(`Timeout waiting for chat matching ${pattern}`));
            }
        }, 100);
    });
}

/**
 * 用原生命令召唤一个 NPC（默认村民，命名 Doctor）。
 * 也可被 Director 的世界补丁直接调用。
 */
async function driftSummonNpc(bot, name, kind = "villager", dx = 0, dy = 1, dz = 1) {
    const p = bot.entity.position;
    bot.chat(`/summon ${kind} ${Math.floor(p.x) + dx} ${Math.floor(p.y) + dy} ${Math.floor(p.z) + dz} {CustomName:'"${name}"'}`);
    await bot.waitForTicks(10);
}

/**
 * 用原生命令搭建一组方块（结构化建筑）。
 * spec: { origin?:{x,y,z}, blocks:[{name, dx,dy,dz}] }
 */
async function driftBuildStructure(bot, spec) {
    const p = bot.entity.position;
    const ox = spec.origin ? spec.origin.x : Math.floor(p.x);
    const oy = spec.origin ? spec.origin.y : Math.floor(p.y);
    const oz = spec.origin ? spec.origin.z : Math.floor(p.z);
    for (const b of spec.blocks) {
        bot.chat(`/setblock ${ox + (b.dx || 0)} ${oy + (b.dy || 0)} ${oz + (b.dz || 0)} ${b.name}`);
    }
    await bot.waitForTicks(10);
}

/**
 * 设置天气（clear / rain / thunder）。
 */
async function driftSetWeather(bot, type = "clear") {
    bot.chat(`/weather ${type}`);
    await bot.waitForTicks(5);
}

/**
 * 给 bot 物品（脚手架辅助：当 Voyager 卡在材料不足时由 Director 调用）。
 */
async function driftGive(bot, item, count = 1) {
    bot.chat(`/give @s ${item} ${count}`);
    await bot.waitForTicks(5);
}

if (typeof module !== "undefined" && module.exports) {
    module.exports = {
        driftChat, driftFindNpc, driftTalkToNpc, driftWaitForChat,
        driftSummonNpc, driftBuildStructure, driftSetWeather, driftGive,
    };
}
