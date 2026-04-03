#!/bin/zsh
source ~/.zshenv
security unlock-keychain -p rentamac ~/Library/Keychains/login.keychain-db 2>/dev/null
cd ~/henry/scripts
exec script -q /dev/null ~/.local/bin/claude --dangerously-skip-permissions --channels plugin:discord@claude-plugins-official
