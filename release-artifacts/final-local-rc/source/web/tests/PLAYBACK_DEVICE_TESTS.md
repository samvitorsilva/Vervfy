# Physical-device playback checks

Browser automation cannot reproduce operating-system suspension, audio focus,
or lock-screen media controls. Before release, test the deployed HTTPS app on
physical Android and iOS devices:

1. Start a multi-track queue, lock the screen before a track ends, and confirm
   the next track starts and lock-screen metadata/actions update.
2. Repeat with the browser backgrounded, then return to the app and confirm
   the active track and seek position remain synchronized.
3. During playback, switch Wi-Fi off to force mobile data, then briefly disable
   all network access and restore it. Confirm playback recovers without
   restarting the queue or looping retries.
4. Repeat with the app installed to the home screen and in the regular browser.
   Record browser/OS versions and whether the OS stopped background audio.

Automatic advancement after the operating system fully suspends or terminates
the browser process cannot be guaranteed by ordinary web application code.
