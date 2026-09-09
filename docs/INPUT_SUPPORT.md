# ESPLink input support

ESPLink uses one WebRTC data channel for the controls needed by browser clients:

- **Keyboard:** key-down and key-up events using browser `KeyboardEvent.code` and `key` values.
- **Mouse or trackpad:** pointer movement, left/middle/right button presses, releases, and wheel scrolling.
- **Touch:** touchscreens are handled through Pointer Events, including movement, taps, presses, and releases.

The stream page prevents browser scrolling over the video while input is active and releases pressed keys/buttons when the browser loses focus or the input channel closes. Input is sent only while the WebRTC data channel is open.

No gamepad, controller, or other input device support is planned for this version.
