# Aethon Release Announcer

Source for the Aethon Minecraft community Discord bot, maintained for Struppi0508.

## Current features

- Persistent opt-in role buttons.
- Welcome messages in general with randomized happy-cat GIFs.
- Staff activity logging and server-specific branding.
- Animated banner generation source.

## CurseForge release watcher — prepared, not enabled

`releases.py` is a prepared extension that polls the official CurseForge API every ten minutes. It discovers projects associated with Struppi0508, baselines existing public files without historical pings, and prepares new-file announcements containing versions, changelogs, and original CurseForge links. Explicit role allowlists restrict notifications to Mod Updates, Modpack Updates, and the configured Creepy/Verity roles.

The watcher is not yet started by `app.py`. Activation requires an approved CurseForge API key, integration into the runtime lifecycle, and live validation of channel permissions and API responses. Local mock tests covered baseline behavior, new releases, duplicate suppression, unavailable-file exclusion, role mapping, and mention restrictions. This is not evidence of a live API integration.

No mod files are hosted or redistributed by this bot.

## Runtime

Python 3.12 with the packages in `requirements.txt`. The deployed application runs on Kinetic. This source snapshot does not change that deployment.

This is a server-specific application, not a ready-to-install public bot. Deployment also needs the private `config.json`, existing `state.json`, generated assets, and the correct bot identity. Do not run historical setup modes against an existing Discord server without reviewing their behavior.

`build_aethon.py` additionally requires Pillow to generate the branding assets. `rebrand.py` performs a versioned migration using the private state file.

## Credentials and private state

The Discord token is supplied through `DISCORD_BOT_TOKEN` or a private `token.txt` on the host. The prepared watcher reads `CURSEFORGE_API_KEY` or a private `curseforge-api-key.txt`. Never commit either credential.

Server configuration, member data, audit exports, message history, runtime state, and credentials are deliberately excluded. Preserve the deployed state files when updating code, especially `state.json` and `release-state.json`.

The identifiers in source are public Discord resource IDs and CurseForge project IDs, not credentials. No GitHub repository should contain a Discord token or a CurseForge API key.
