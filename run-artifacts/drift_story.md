# Drift 剧情推进（run12 实测）

> 每个子任务对应的世界叙事（`title`/`text`）与世界补丁（`world_patch`）。
> 这正是「回旋镖」循环中 Drift 作为导演子系统对 Voyager 行为的回应与演化。

## 子任务 #1: `bot.chat('/give @s minecraft:white_wool 16')`

- **场景标题**：昆明湖的清晨
- **场景叙事**：你站在昆明湖畔，晨雾如纱，湖面平静如镜。远处十七孔桥的轮廓在薄雾中若隐若现，柳枝轻拂水面，几只水鸟掠过，激起一圈圈涟漪。你深吸一口气，空气中带着湿润的草木香。今天，你打算沿着湖岸探索，寻找传说中的湖心秘境。
- **世界补丁(world_patch)**：`{"variables": {"has_visited_lake": true, "time_of_day": "morning"}, "mc": {"dimension": "overworld", "location": {"x": 100, "y": 64, "z": 200}, "biome": "plains"}}`
- **推进指令**：`[Drift] advance -> patch_keys=['variables', 'mc'] node_keys=['title', 'text']`

## 子任务 #2: `bot.chat('/give @s minecraft:white_concrete 16')`

- **场景标题**：湖心石塔的微光
- **场景叙事**：你沿着湖岸东行，脚下是湿润的青石板。雾气渐散，阳光洒在水面，金光粼粼。行至一处僻静湾角，你发现湖中有一座半没于水的石塔，塔尖上隐隐有微光闪烁。你的目光被吸引，那光芒仿佛在召唤你。你环顾四周，岸边泊着一叶小木舟，桨就搁在船头。你该怎么做？
- **世界补丁(world_patch)**：`{"variables": {"discovered_light_tower": true, "player_has_boat": false}, "mc": {}}`
- **推进指令**：`[Drift] advance -> patch_keys=['variables', 'mc'] node_keys=['title', 'text']`

## 子任务 #3: `bot.chat('/give @s minecraft:white_wool 16')`

- **场景标题**：登上小舟，向石塔划去
- **场景叙事**：你俯身解开系在木桩上的绳索，轻轻跨上小舟。木舟微微晃动，你拿起桨，稳稳划向湖心。水面泛起细碎的波光，石塔的微光越来越近。靠近时，你发现塔基处有一道被水淹没的石门，门缝里透出温暖的光芒。你俯身探头，门内是一条向下延伸的石阶，似乎通往一个隐秘的空间。你将舟靠近，小心地踩着塔基的残石，准备踏入石门。
- **世界补丁(world_patch)**：`{"variables": {"lake_center_reached": true, "stone_tower_entrance_open": true}, "mc": {"players": [{"name": "bot", "position": {"x": 120.5, "y": 63, "z": -45.2}, "rotation": {"yaw": 90, "pitch": 10}}], "blocks": [{"position": {"x": 120, "y": 62, "z": -45}, "block": "minecraft:stone_brick_stairs", "state": {"facing": "east", "half": "bottom"}}, {"position": {"x": 120, "y": 63, "z": -45}, "block": "minecraft:air"}, {"position": {"x": 120, "y": 64, "z": -45}, "block": "minecraft:stone_brick_wall", "state": {"up": true, "north": true, "south": true, "east": false, "west": false}}]}}`
- **推进指令**：`[Drift] advance -> patch_keys=['variables', 'mc'] node_keys=['title', 'text']`

## 子任务 #4: `bot.chat('/setblock 120 65 80 minecraft:white_bed')`

- **场景标题**：踏入石门，石阶向下延伸
- **场景叙事**：你扶着湿滑的塔壁，小心翼翼地踏入那道半没于水的石门。光线从门缝透出，照亮了向下延伸的石阶。你顺着石阶一步步往下走，水声渐远，空气变得温暖而干燥。石壁上刻着古老的纹路，闪烁着幽蓝的光芒。约摸走了二十级台阶，眼前豁然开朗——一个巨大的圆形石室出现在你面前。石室中央有一座祭坛，祭坛上悬浮着一颗发光的蓝色珠子，周围环绕着细密的符文。你感到一股柔和的力量轻轻推动着你，仿佛在引导你走向祭坛。
- **世界补丁(world_patch)**：`{"variables": {"location": "石塔密室", "has_blue_pearl": false}, "mc": {"player": {"position": {"x": 120, "y": 64, "z": 80}}}}`
- **推进指令**：`[Drift] advance -> patch_keys=['variables', 'mc'] node_keys=['title', 'text']`

## 子任务 #5: `bot.chat('/give @s minecraft:white_wool 64')`

- **场景标题**：祭坛前的抉择
- **场景叙事**：你缓缓走向祭坛，脚下的石板传来沉闷的回响。那颗蓝色珠子悬浮在离地三尺处，光芒柔和而脉动，仿佛有生命。当你靠近至三步之遥时，符文骤然亮起，一道半透明的屏障出现在你面前，将你与珠子隔开。屏障上浮现出几行古老的文字，你虽不认识，却莫名能理解其意：

『心有所求，方可入内。』

你环顾四周，发现石室的东墙上刻着一幅壁画：一只凤凰衔着一枚玉佩，飞向云端；西墙上则是一幅苍龙盘踞于山巅的图案。你在思考，这祭坛究竟想要你交出什么，或是证明什么。远处传来水滴落下的声音，时间仿佛在此凝固。
- **世界补丁(world_patch)**：`{"variables": {"tower_room_explored": true, "barrier_active": true, "wall_paintings_discovered": true}, "mc": {"position": {"x": 120, "y": 65, "z": 80}, "biome": "plains", "time": "day", "block_at_feet": "stone", "nearby_entities": []}}`
- **推进指令**：`[Drift] advance -> patch_keys=['variables', 'mc'] node_keys=['title', 'text']`

## 子任务 #6: `bot.chat('/give @s minecraft:white_wool 64')`

- **场景标题**：壁画中的指引
- **场景叙事**：你凝视着墙面上的壁画，凤凰与苍龙的形象栩栩如生。你注意到凤凰衔着的玉佩形状，与祭坛周围的符文有某种呼应。你伸出手，指尖轻触壁画——瞬间，一道光芒从壁画中涌出，化作一道金色丝线，缠绕在你的手腕上。丝线缓缓延伸，指向祭坛的方向。与此同时，屏障上的文字发生了变化：『以诚为钥，以心为锁。』你明白了，这祭坛考验的并不是力量或财富，而是你内心的真实所求。你闭上眼睛，静下心来，脑海中浮现出你此行最渴望得到的东西。当你再次睁开眼时，屏障如薄雾般消散，蓝色珠子散发出更明亮的光芒，似乎正等待着你上前触碰。
- **世界补丁(world_patch)**：`{"variables": {"barrier_down": true, "quest_stage": "touching_orb"}, "mc": {}}`
- **推进指令**：`[Drift] advance -> patch_keys=['variables', 'mc'] node_keys=['title', 'text']`

## 子任务 #7: `bot.chat('/setblock ~ ~1 ~ minecraft:white_wool')`

- **场景标题**：触碰蓝珠，秘境开启
- **场景叙事**：你深吸一口气，缓缓伸出手，指尖触碰到那颗蓝色珠子。刹那间，光芒大盛，将你整个包裹。你感到一阵天旋地转，再睁眼时，已身处一个奇异的空间——头顶是流动的星河，脚下是透明的琉璃地面，而那颗蓝色珠子正悬浮在你面前，化作一个半透明的人形轮廓，声音空灵：『你已通过心之试炼。此珠为昆湖之心，可助你感知此方天地。如今，湖底秘境已为你敞开，但需一件信物才能开启真正的门扉。』说罢，人形消散，一颗温润的蓝色宝石落在你手心，而你的前方出现了一扇刻满水纹的石门，门中央有一个凹槽，形状正与你手中的宝石吻合。
- **世界补丁(world_patch)**：`{"variables": {"kungfu_heart_obtained": true, "location": "lake_bottom_mystic_realm", "door_opened": false, "gem_in_hand": true}, "mc": {"place": {"type": "structure", "id": "kunming_mystic_realm", "position": "player"}, "give": {"item": "minecraft:blue_ice", "count": 1, "name": "昆湖之心"}}}`
- **推进指令**：`[Drift] advance -> patch_keys=['variables', 'mc'] node_keys=['title', 'text']`

## 子任务 #8: `bot.chat('/give @s minecraft:white_wool 16')`

- **场景标题**：嵌入宝石，石门开启
- **场景叙事**：你握紧手中的蓝色宝石，感受着它温润的触感与微微的脉动。你走向那扇刻满水纹的石门，将宝石对准凹槽，轻轻嵌入。刹那间，宝石绽放出湛蓝的光芒，如水波般沿着门上的纹路蔓延开来。石门发出沉闷的轰鸣，缓缓向两侧滑开，露出一个向下的阶梯，通往一片幽蓝的湖底世界。你踏入门内，身后的石门悄然合拢。你发现自己站在一条水晶走廊中，两侧是透明的墙壁，外面是幽深的湖水，各种发光的鱼类游弋其间。走廊尽头，一座宏伟的水下宫殿若隐若现，宫门上方刻着三个大字：『碧波殿』。你感到怀中的昆湖之心微微发烫，仿佛在指引着你前行。
- **世界补丁(world_patch)**：`{"variables": {"has_lake_heart_gem": true, "location": "underwater_crystal_corridor", "visited_bi_bo_dian": false}, "mc": {"biome": "deep_ocean", "block": "minecraft:prismarine", "light_level": 8, "time": "day", "weather": "clear"}}`
- **推进指令**：`[Drift] advance -> patch_keys=['variables', 'mc'] node_keys=['title', 'text']`

## 子任务 #9: `bot.chat('/setblock 120 45 231 minecraft:white_wool')`

- **场景标题**：碧波殿前
- **场景叙事**：你沿着水晶走廊缓步前行，两侧的湖水在透明墙壁外轻轻涌动，发光的鱼群好奇地跟随你的脚步。走廊尽头，碧波殿的宫门近在眼前——门扉由深海珊瑚与珍珠镶嵌而成，门楣上雕着水纹与游龙。你站在门前，怀中的昆湖之心微微震动，仿佛在与殿内的某种力量共鸣。你伸手推开沉重的宫门，一股湿润而古老的气息扑面而来。殿内幽暗，只有几盏鲛人油灯发出幽幽蓝光，照亮中央一座巨大的白玉碑。碑上刻着几行字：『湖心之秘，藏于三问。答对者，得湖神之赐。』你走近白玉碑，碑面如水波般漾开，浮现出第一个问题：『何为湖之魂？』
- **世界补丁(world_patch)**：`{"variables": {"location": "碧波殿内", "riddle_count": 1, "riddle_answers": []}, "mc": {"player": {"position": [120, 45, 230], "dimension": "overworld"}}}`

