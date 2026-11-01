"""Hosted runtime only: never applies or recreates Discord resources."""
import logging
import os
from pathlib import Path
import bot

token = os.environ.get('DISCORD_BOT_TOKEN', '').strip()
token_file = Path(__file__).with_name('token.txt')
if not token and token_file.exists():
    token = token_file.read_text(encoding='utf-8-sig').strip()
if not token:
    raise SystemExit('Setup needed: save the setup bot token in token.txt, then start the server. Never paste it into the console.')
class HostedBot(bot.Astreon):
    async def on_ready(self):
        if self.user.id != 1565136736135159918:
            self.failed = True
            print('Wrong bot identity: use the newer Astreon setup bot token.', flush=True)
            await self.close()
            return
        first_start = not self.started
        if first_start:
            import rebrand
            await rebrand.apply(self)
        await super().on_ready()
        if first_start and not getattr(self, 'failed', False) and not self.is_closed():
            # Readiness marker required by the generic Python hosting preset.
            # Hosting preset readiness detection is managed by Kinetic.
            print('Aethon is online on Kinetic. Your PC and browser can be closed.', flush=True)

client = HostedBot('run')
client.run(token, log_level=logging.INFO)
if getattr(client, 'failed', False):
    raise SystemExit(1)
