"""One-time, ID-scoped Aethon branding update; preserves channels and memberships."""
import json
import discord
import bot

def wording(value):
    if isinstance(value,str):
        return (value.replace('Astreon','Aethon').replace('ASTREON','AETHON')
            .replace('Struppi’s Minecraft community','Minecraft Community')
            .replace("Struppi's Minecraft community",'Minecraft Community')
            .replace('Struppi’s Minecraft Community','Minecraft Community')
            .replace('Struppi’s mods','community mods'))
    if isinstance(value,list):return [wording(v) for v in value]
    if isinstance(value,dict):return {k:wording(v) for k,v in value.items()}
    return value

async def apply(client):
    marker=bot.ROOT/'aethon-branding-v2.json'
    if marker.exists():return
    guild=client.get_guild(bot.GUILD_ID)
    if not guild or guild.name!='Aethon':raise RuntimeError('Aethon server name/ID check failed')
    roles={r.id:r for r in await guild.fetch_roles()}
    for key,rid in client.state['roles'].items():
        role=roles[rid]
        if role.name!=bot.ROLE_NAMES[key]:
            await role.edit(name=bot.ROLE_NAMES[key],reason='Requested Aethon rebrand')
    for c in await guild.fetch_channels():
        new_name=c.name.replace('ASTREON','AETHON').replace('astreon','aethon').replace('Astreon','Aethon')
        kwargs={}
        if new_name!=c.name:kwargs['name']=new_name
        if getattr(c,'topic',None) and wording(c.topic)!=c.topic:kwargs['topic']=wording(c.topic)
        if kwargs and c.permissions_for(guild.me).manage_channels:
            await c.edit(**kwargs,reason='Requested Aethon rebrand')
    panel=client.channel('roles')
    message=await panel.fetch_message(client.state['messages']['roles'])
    if message.author.id!=client.user.id:raise RuntimeError('Role-panel author mismatch')
    embeds=[discord.Embed.from_dict(wording(e.to_dict())) for e in message.embeds]
    keys=('mmorpg','smp','soon')
    if len(embeds)!=3:raise RuntimeError('Unexpected server card count')
    files=[]
    for key,e in zip(keys,embeds):
        filename='aethon-'+key+'.gif'
        e.set_image(url='attachment://'+filename)
        e.set_footer(text='AETHON • Minecraft Community')
        files.append(discord.File(bot.ROOT/'assets'/(key+'.gif'),filename=filename))
    view=discord.ui.View(timeout=None)
    for key in keys:view.add_item(bot.RoleButton(key))
    await message.edit(content='## 🌌 Find your next adventure\nExplore our Minecraft servers. Choose a role below to unlock its category—you can join more than one.',embeds=embeds,attachments=files,view=view)
    updates=await panel.fetch_message(client.state['messages']['update_roles'])
    view=discord.ui.View(timeout=None)
    for key in ('mods','packs','events'):view.add_item(bot.RoleButton(key))
    await updates.edit(embeds=[discord.Embed.from_dict(wording(e.to_dict())) for e in updates.embeds],view=view)
    for channel_key,message_key,asset in (('rules','rules_v2','rules'),('socials','links_v2','links')):
        m=await client.channel(channel_key).fetch_message(client.state['messages'][message_key])
        if m.author.id!=client.user.id:raise RuntimeError('Branding message author mismatch')
        embeds=[discord.Embed.from_dict(wording(e.to_dict())) for e in m.embeds]
        embeds[0].set_image(url='attachment://aethon-'+asset+'.gif')
        embeds[0].set_footer(text='AETHON • Minecraft Community')
        await m.edit(content=wording(m.content) or None,embeds=embeds,attachments=[discord.File(bot.ROOT/'assets'/(asset+'.gif'),filename='aethon-'+asset+'.gif')])
    for key in ('mmorpg','smp','soon','events'):
        m=await client.channel(key).fetch_message(client.state['messages'][key])
        if m.author.id!=client.user.id:continue
        await m.edit(content=wording(m.content),embeds=[discord.Embed.from_dict(wording(e.to_dict())) for e in m.embeds])
    async for m in client.channel('welcome').history(limit=100):
        if m.author.id!=client.user.id:continue
        embeds=[discord.Embed.from_dict(wording(e.to_dict())) for e in m.embeds]
        if embeds:
            embeds[0].set_image(url='attachment://aethon-welcome.gif')
            embeds[0].set_footer(text='AETHON • Minecraft Community')
            await m.edit(content=wording(m.content) or None,embeds=embeds,attachments=[discord.File(bot.ROOT/'assets'/'welcome.gif',filename='aethon-welcome.gif')])
        elif m.content:
            await m.edit(content=wording(m.content))
    # Confirm uploaded files are referenced by the three card images, not loose attachments.
    check=await panel.fetch_message(message.id)
    print(f'Verifying {len(check.embeds)} server embeds and {len(check.attachments)} loose attachments.',flush=True)
    if len(check.embeds)!=3:raise RuntimeError('Card embed verification failed')
    for key,e in zip(keys,check.embeds):
        if 'aethon-'+key+'.gif' not in (e.image.url or ''):raise RuntimeError('Card GIF reference mismatch')
    marker.write_text(json.dumps({'guild_id':guild.id,'role_panel_id':message.id,'version':2}),encoding='utf-8')
    print('Aethon branding complete: readable GIFs attached to matching cards.',flush=True)
