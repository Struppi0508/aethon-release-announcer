"""Public CurseForge release watcher. Requires a separately approved API key.

Never reads local mod builds or uploads binaries. Preserve release-state.json.
"""
import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

import aiohttp
import discord

ROOT = Path(__file__).resolve().parent
STATE = ROOT / 'release-state.json'
AUTHOR = 'Struppi0508'
SEED_PROJECT = 1765530
MOD_ROLE = 1566434415821979730
PACK_ROLE = 1566434417365221456
PROJECT_ROLES = {'creepy-horror':1536117012319830107,
                 'creepy-easy':1536117012319830107,
                 'veritypack-horror':1536118835399098478}
LOG = logging.getLogger('aethon.releases')


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.skip=0
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style'): self.skip+=1
        if tag in ('p','br','li','div','h1','h2','h3'): self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in ('script','style'): self.skip=max(0,self.skip-1)
    def handle_data(self, data):
        if not self.skip: self.parts.append(data)


def clean(value, limit):
    p=PlainText(); p.feed(str(value or ''))
    text=re.sub(r'\n{3,}', '\n\n', ''.join(p.parts)).strip()
    return discord.utils.escape_mentions(discord.utils.escape_markdown(text))[:limit]


def available(f):
    return f.get('isAvailable') is True and f.get('fileStatus') == 4


def roles_for(mod):
    result=[PACK_ROLE if mod.get('classId')==4471 else MOD_ROLE]
    if mod.get('slug') in PROJECT_ROLES: result.append(PROJECT_ROLES[mod['slug']])
    return result


def save(data):
    tmp=STATE.with_suffix('.tmp')
    tmp.write_text(json.dumps(data,indent=2),encoding='utf-8')
    tmp.replace(STATE)


class ReleaseWatcher:
    def __init__(self, bot):
        self.bot=bot
        # Corrupt state fails closed; never silently re-baseline or mass announce.
        self.state=json.loads(STATE.read_text()) if STATE.exists() else {'projects':{}}
        self.reconciled=False

    async def request(self, session, endpoint, **params):
        async with session.get('https://api.curseforge.com/v1/'+endpoint, params=params) as response:
            if response.status!=200:
                raise RuntimeError(f'CurseForge returned HTTP {response.status}')
            return await response.json()

    async def pages(self, session, endpoint, **params):
        rows=[]
        for index in range(0,10000,50):
            result=await self.request(session,endpoint,index=index,pageSize=50,**params)
            batch=result['data']; rows.extend(batch)
            total=result.get('pagination',{}).get('totalCount')
            if len(batch)<50 or (total is not None and len(rows)>=total): return rows
        raise RuntimeError('Pagination limit reached; refusing incomplete baseline')

    async def cycle(self, session):
        if not self.state.get('author_id'):
            seed=(await self.request(session,f'mods/{SEED_PROJECT}'))['data']
            author=next(a for a in seed['authors'] if a['name'].casefold()==AUTHOR.casefold())
            self.state['author_id']=author['id']; save(self.state)
        mods=await self.pages(session,'mods/search',gameId=432,authorId=self.state['author_id'])
        mods=[m for m in mods if any(a['id']==self.state['author_id'] for a in m['authors'])]
        channel=self.bot.channel('releases')
        if not channel: raise RuntimeError('Release channel missing')
        perms=channel.permissions_for(channel.guild.me)
        if not all((perms.view_channel,perms.send_messages,perms.embed_links,perms.read_message_history)):
            raise RuntimeError('Release channel requires view/send/embed/history permissions')
        if not self.reconciled:
            # Recover a successful post followed by a crash before saving its ID.
            after=datetime.fromisoformat(self.state['activated']) if self.state.get('activated') else datetime.now(timezone.utc)
            async for message in channel.history(limit=None,after=after):
                if message.author.id!=self.bot.user.id: continue
                for embed in message.embeds:
                    match=re.fullmatch(r'AETHON · CurseForge (\d+):(\d+)',embed.footer.text or '')
                    if match:
                        pid,fid=match.groups()
                        record=self.state['projects'].setdefault(pid,{'seen':[]})
                        if int(fid) not in record['seen']: record['seen'].append(int(fid))
            self.reconciled=True
        initial=not self.state.get('activated')
        for mod in mods:
            pid=str(mod['id'])
            files=await self.pages(session,f'mods/{pid}/files')
            public=[f for f in files if available(f)]
            record=self.state['projects'].get(pid)
            if initial or record is None:
                # Existing projects baseline without pings. New projects discovered
                # later announce only files dated since monitoring was activated.
                seen=[f['id'] for f in public if initial or datetime.fromisoformat(f['fileDate'].replace('Z','+00:00')) < datetime.fromisoformat(self.state['activated'])]
                record=self.state['projects'].setdefault(pid,{'seen':seen})
                if initial:
                    record['seen']=sorted(set(record['seen']) | set(seen))
                record['name']=mod['name']; save(self.state)
            if initial: continue
            for f in sorted(public,key=lambda f:(f['fileDate'],f['id'])):
                if f['id'] in record['seen']: continue
                roles=[channel.guild.get_role(rid) for rid in roles_for(mod)]
                if any(r is None or r.is_default() for r in roles):
                    raise RuntimeError('Configured release notification role missing')
                if any(not r.mentionable for r in roles) and not perms.mention_everyone:
                    raise RuntimeError('Bot needs Mention All Roles in releases only to notify selected roles')
                changelog=(await self.request(session,f'mods/{pid}/files/{f["id"]}/changelog'))['data']
                url=mod['links']['websiteUrl'].rstrip('/')+'/files/'+str(f['id'])
                if not url.startswith('https://www.curseforge.com/'): raise RuntimeError('Unexpected project URL')
                embed=discord.Embed(title=clean(mod['name'],200)+' · New release',url=url,
                    description=clean(changelog,2500) or clean(mod.get('summary'),1000) or 'A new file is available on CurseForge.',
                    colour=0x79BFFF,timestamp=datetime.fromisoformat(f['fileDate'].replace('Z','+00:00')))
                embed.add_field(name='File',value=clean(f['displayName'],1024),inline=False)
                embed.add_field(name='Minecraft / loader',value=clean(', '.join(f.get('gameVersions',[])),1024) or 'See file page')
                embed.add_field(name='Release type',value={1:'Release',2:'Beta',3:'Alpha'}.get(f['releaseType'],'Other'))
                embed.add_field(name='Download & full changelog',value=f'[Open on CurseForge]({url})',inline=False)
                embed.set_footer(text=f'AETHON · CurseForge {pid}:{f["id"]}')
                await channel.send(' '.join(r.mention for r in roles),embed=embed,
                    allowed_mentions=discord.AllowedMentions(everyone=False,users=False,roles=roles,replied_user=False))
                record['seen'].append(f['id']); save(self.state)
        if initial:
            self.state['activated']=datetime.now(timezone.utc).isoformat()
            save(self.state)
            LOG.info('Release baseline saved for %s projects; historical files were not announced',len(mods))
        LOG.info('CurseForge check completed for %s projects',len(mods))

    async def run(self):
        missing_logged=False
        while not self.bot.is_closed():
            try:
                key=os.environ.get('CURSEFORGE_API_KEY','').strip()
                keyfile=ROOT/'curseforge-api-key.txt'
                if not key and keyfile.exists(): key=keyfile.read_text(encoding='utf-8-sig').strip()
                if not key:
                    if not missing_logged: LOG.warning('Release watcher waiting for approved CurseForge API key'); missing_logged=True
                    await asyncio.sleep(60); continue
                async with aiohttp.ClientSession(headers={'x-api-key':key},timeout=aiohttp.ClientTimeout(total=45)) as session:
                    await self.cycle(session)
            except asyncio.CancelledError: raise
            except Exception as exc:
                # No credentials, response bodies or request headers in logs.
                LOG.error('Release check failed (%s): %s',type(exc).__name__,str(exc) if isinstance(exc,RuntimeError) else 'Will retry')
            await asyncio.sleep(600)
