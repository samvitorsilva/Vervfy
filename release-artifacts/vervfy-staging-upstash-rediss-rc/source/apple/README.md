# Vervfy for Apple platforms

This SwiftUI app wraps the existing Vervfy web app in `WKWebView` and replaces
its web navigation rail with a native SwiftUI glass navigation bar. On iOS 26
and macOS 26, the bar uses Apple's Liquid Glass API. Older supported OS versions
use a system material fallback. The web app and its browser glass effect are
unchanged.

## Run

Open `Vervfy.xcodeproj` in Xcode, choose the Vervfy scheme, and select an iPhone,
iPad, or Mac destination. The app opens the Vervfy frontend directly. Use
**More → Change server** to connect to a different self-hosted instance. Plain
HTTP is accepted only for localhost development.

The project supports iOS 18 and macOS 15 or later. Authentic Liquid Glass is
provided by iOS 26 and macOS 26; earlier versions use the platform's standard
translucent material.
